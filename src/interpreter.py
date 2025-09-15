"""Loom Interpreter aligned with SPEC-001, extended for SPEC-002 fetch + allowlist.

- Verb synonyms (Make, Show, Return, Ask, Choose, Repeat, Call).
- Make accepts LHS: name/target/var/id/key/binding/lhs; RHS: expr/value/to/rhs/with/is/equals.
- Choose supports branches with {"when": <expr>} and {"otherwise": true}.
- Evaluator supports: Identifier, String, Number, Bool, Binary/BinaryExpr.
- Receipts: ask, callGraph, engine, env, logs, steps. Deterministic content.
- SPEC-002: Call can fetch with args.url / args.http.
  * args.url may be an expression OR a string with {name} placeholders.
  * Enforcement ON: block fixture://; http(s) only if domain allowlisted.
  * Built-in non-network op: args.op == "xml.firstTitle" parses first Atom <entry><title>.
"""

from typing import Any, Dict, List, Optional, Tuple
import re
from urllib.parse import urlparse
import xml.etree.ElementTree as ET

from .names import normalize_module_slug
from .http_client import DEFAULT_TIMEOUT, DEFAULT_MAX_BYTES
from .fetchers import real_fetcher


class RuntimeErrorLoom(Exception):
    pass


VERB_ALIASES = {
    "make": "Make", "set": "Make", "let": "Make", "assign": "Make", "define": "Make",
    "show": "Show", "print": "Show", "log": "Show", "echo": "Show",
    "return": "Return", "yield": "Return",
    "ask": "Ask", "prompt": "Ask", "input": "Ask",
    "choose": "Choose", "if": "Choose",
    "repeat": "Repeat", "for": "Repeat", "foreach": "Repeat", "loop": "Repeat",
    "call": "Call", "invoke": "Call", "run": "Call", "use": "Call",
    # SPEC-002 aliases:
    "fetch": "Call", "query": "Call",
}


def normalize_verb_and_args(step: Dict[str, Any]) -> Tuple[str, Dict[str, Any], Optional[str]]:
    raw = (step.get("verb") or "").strip()
    canon = VERB_ALIASES.get(raw.lower(), raw)
    args = dict(step.get("args") or {})

    if canon == "Make":
        if "name" not in args:
            for k in ("target", "var", "id", "key", "binding", "lhs"):
                if k in args:
                    args["name"] = args.pop(k)
                    break
        if "expr" not in args:
            for k in ("value", "to", "rhs", "with", "is", "equals"):
                if k in args:
                    args["expr"] = args.pop(k)
                    break

    elif canon == "Show":
        if "expr" not in args:
            if "text" in args:
                args["expr"] = args.get("text")
            elif "value" in args:
                args["expr"] = args.get("value")

    elif canon == "Ask":
        if "text" not in args and "prompt" in args:
            args["text"] = args.get("prompt")
        if "store" not in args:
            for k in ("name", "var", "target", "lhs", "key"):
                if k in args:
                    args["store"] = args.pop(k)
                    break

    elif canon == "Repeat":
        if "iterator" not in args:
            if "var" in args:
                args["iterator"] = args.pop("var")
            elif "it" in args:
                args["iterator"] = args.pop("it")
        if "iterable" not in args and "in" in args:
            args["iterable"] = args.pop("in")
        if "block" not in args and "steps" not in args and "body" in args:
            args["block"] = {"steps": args.pop("body")}
        if "block" not in args and isinstance(args.get("steps"), list):
            args["block"] = {"steps": args.pop("steps")}

    elif canon == "Call":
        if "module" not in args and "target" in args:
            args["module"] = args.pop("target")

    return canon, args, raw or None


class Evaluator:
    """Tiny expression evaluator for Loom-ish AST nodes."""
    def __init__(self, env: Dict[str, Any]):
        self.env = env

    def eval(self, node: Any) -> Any:
        if node is None:
            return None
        if not isinstance(node, dict):
            return node
        typ = node.get("type")
        if typ == "Identifier":
            return self.env.get(node.get("name"))
        if typ == "String":
            return node.get("value", "")
        if typ == "Number":
            return node.get("value", 0)
        if typ == "Bool":
            return bool(node.get("value"))
        if typ in ("Binary", "BinaryExpr"):
            op = node.get("op")
            L = self.eval(node.get("left"))
            R = self.eval(node.get("right"))
            if op == "+": return L + R
            if op == "-": return L - R
            if op == "*": return L * R
            if op == "/": return L / R
            if op in ("==", "equals"): return L == R
            if op in ("!=", "notEquals"): return L != R
            if op in ("<", "lt"): return L < R
            if op in ("<=", "lte"): return L <= R
            if op in (">", "gt"): return L > R
            if op in (">=", "gte"): return L >= R
            raise RuntimeErrorLoom(f"Unsupported binary op: {op}")
        return node


class Interpreter:
    def __init__(self, *, enforce_capabilities: bool = False, fetcher=None, capabilities: Optional[Dict[str, Any]] = None):
        self._enforce_default = bool(enforce_capabilities)
        self._fetcher = fetcher or real_fetcher
        self._caps = capabilities or {}
        self.env: Dict[str, Any] = {}
        self.receipt: Dict[str, Any] = {
            "ask": [],
            "callGraph": [],
            "engine": "interpreter",
            "env": {},
            "logs": [],
            "steps": [],
        }

    # ---------- helpers
    def _unwrap_module(self, module_obj: Dict[str, Any]) -> Dict[str, Any]:
        return module_obj.get("module") if isinstance(module_obj.get("module"), dict) else module_obj

    def _extract_flow(self, m: Dict[str, Any]) -> List[Dict[str, Any]]:
        return m.get("flow") or m.get("steps") or m.get("block", {}).get("steps") or []

    def _get_expr(self, args: Dict[str, Any], *keys: str) -> Optional[Dict[str, Any]]:
        for k in keys:
            if k in args and args[k] is not None:
                return args[k]
        return None

    def _append_step(self, entry: Dict[str, Any]) -> None:
        if "rawVerb" not in entry:
            entry["rawVerb"] = None
        self.receipt["steps"].append(entry)

    _brace_rx = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}")

    def _interpolate(self, s: str) -> str:
        """Replace {name} with str(env.get(name,'')) safely."""
        def repl(m):
            name = m.group(1)
            val = self.env.get(name)
            return "" if val is None else str(val)
        return self._brace_rx.sub(repl, s)

    def _url_value(self, node_or_str: Any) -> str:
        """Return final URL string from an AST node or a literal with {vars}."""
        if isinstance(node_or_str, dict):
            val = self.evaluator.eval(node_or_str)
            return "" if val is None else str(val)
        if isinstance(node_or_str, str):
            return self._interpolate(node_or_str)
        return ""

    # ---- capability helpers
    def _caps_root(self) -> Dict[str, Any]:
        # accept either {"capabilities": {...}} or direct mapping
        if "capabilities" in self._caps and isinstance(self._caps["capabilities"], dict):
            return self._caps["capabilities"]
        return self._caps if isinstance(self._caps, dict) else {}

    def _allowed_domains(self) -> List[str]:
        caps = self._caps_root().get("network:fetch")
        if isinstance(caps, dict):
            doms = caps.get("domains")
            if isinstance(doms, list):
                return [str(d).lower() for d in doms]
        return []

    @staticmethod
    def _is_http(url: str) -> bool:
        scheme = (urlparse(url).scheme or "").lower()
        return scheme in ("http", "https")

    @staticmethod
    def _domain(url: str) -> str:
        netloc = urlparse(url).netloc.split("@")[-1]  # strip userinfo
        return netloc.split(":")[0].lower()

    # ---------- execution
    def exec_step(self, step: Dict[str, Any]) -> Tuple[Any, bool]:
        canon_verb, args, raw_verb = normalize_verb_and_args(step)

        if canon_verb == "Make":
            name = args.get("name")
            if not isinstance(name, str) or not name:
                raise RuntimeErrorLoom("Make: missing 'name'")
            val_node = self._get_expr(args, "expr", "value")
            value = self.evaluator.eval(val_node) if isinstance(val_node, dict) else val_node
            self.env[name] = value
            self._append_step({"event": "make", "name": name, "value": value, "verb": "Make"})
            return None, False

        if canon_verb == "Show":
            expr = self._get_expr(args, "expr", "value", "text")
            value = self.evaluator.eval(expr) if isinstance(expr, dict) else expr
            self._append_step({"event": "show", "value": value, "verb": "Show"})
            print(value)
            return None, False

        if canon_verb == "Return":
            expr = self._get_expr(args, "expr", "value")
            value = self.evaluator.eval(expr) if isinstance(expr, dict) else expr
            self._append_step({"event": "return", "value": value, "verb": "Return"})
            return value, True

        if canon_verb == "Ask":
            prompt = (args.get("text") or "")
            store = args.get("store")
            default = args.get("default", "")
            answer = None
            if isinstance(store, str) and store:
                if store in self.env and self.env[store] not in (None, ""):
                    answer = self.env[store]
                else:
                    answer = default
                    self.env[store] = answer
            self.receipt["ask"].append({"prompt": prompt, "store": store, "value": answer})
            return None, False

        if canon_verb == "Choose":
            branches: List[Dict[str, Any]] = list(args.get("branches") or [])
            for idx, br in enumerate(branches):
                if "when" in br:
                    cond_expr = br.get("when")
                    ok = self.evaluator.eval(cond_expr)
                    choose_entry = {
                        "event": "choose",
                        "predicateTrace": [{"expr": cond_expr, "value": bool(ok)}],
                        "verb": "Choose",
                        "rawVerb": None,
                        "selected": None,
                    }
                    if ok:
                        choose_entry["selected"] = {"branch": idx, "kind": "when"}
                        self.receipt["steps"].append(choose_entry)
                        res, did_return = self.exec_block({"steps": br.get("steps") or []})
                        if did_return:
                            return res, True
                        return res, False
                    else:
                        self.receipt["steps"].append(choose_entry)
                        continue
                elif br.get("otherwise"):
                    res, did_return = self.exec_block({"steps": br.get("steps") or []})
                    self._append_step({
                        "event": "choose",
                        "predicateTrace": [],
                        "selected": {"branch": idx, "kind": "otherwise"},
                        "verb": "Choose",
                    })
                    if did_return:
                        return res, True
                    return res, False
            return None, False

        if canon_verb == "Repeat":
            iterator = args.get("iterator")
            iterable = args.get("iterable")
            rng = args.get("range")
            block = args.get("block") or {"steps": []}

            if isinstance(rng, dict) and rng.get("type") in ("Range",):
                start = rng.get("start", 0); end = rng.get("end", 0); step_v = rng.get("step", 1)
                it = range(int(start), int(end), int(step_v))
            elif isinstance(iterable, list):
                it = iterable
            else:
                it = []

            for item in it:
                if iterator: self.env[iterator] = item
                res, did_return = self.exec_block(block)
                if did_return:
                    return res, True
            return None, False

        if canon_verb == "Call":
            # Built-in, non-network op: XML first title extraction
            if isinstance(args.get("op"), str) and args.get("op") == "xml.firstTitle":
                # source may be provided as an Identifier node via args.fromExpr or a var name via args.from
                src_text = None
                if "fromExpr" in args and isinstance(args["fromExpr"], dict):
                    src_text = self.evaluator.eval(args["fromExpr"])
                elif "from" in args:
                    name = args["from"]
                    if isinstance(name, str):
                        src_text = self.env.get(name)
                if not isinstance(src_text, str):
                    src_text = "" if src_text is None else str(src_text)

                title = ""
                try:
                    # Try Atom namespace; fallback to no namespace
                    ns = {"atom": "http://www.w3.org/2005/Atom"}
                    root = ET.fromstring(src_text)
                    node = root.find(".//atom:entry/atom:title", ns) or root.find(".//entry/title")
                    if node is not None and node.text is not None:
                        title = node.text.strip()
                except Exception:
                    title = ""

                if isinstance(args.get("into"), str):
                    self.env[args["into"]] = title
                self._append_step({"event": "parse", "op": "xml.firstTitle", "verb": "Call"})
                return None, False

            # Path A: module-to-module bookkeeping
            if "module" in args and "url" not in args and "http" not in args and "op" not in args:
                target_raw = args.get("module")
                target_norm = normalize_module_slug(target_raw or "")
                self.receipt["callGraph"].append({"from": None, "to": target_raw})
                return None, False

            # Path B: URL fetch (SPEC-002)
            url_node = args.get("url") or args.get("http")
            if url_node is not None:
                url = self._url_value(url_node)

                # Capability enforcement
                if self._enforce_default:
                    if url.startswith("fixture://"):
                        self.receipt["logs"].append({
                            "level": "error", "event": "capability",
                            "cap": "network:fetch", "action": "blocked-fixture", "url": url
                        })
                        raise RuntimeErrorLoom("network fetch disallowed under capability enforcement")
                    if self._is_http(url):
                        domain = self._domain(url)
                        allowed = domain in set(self._allowed_domains())
                        if not allowed:
                            self.receipt["logs"].append({
                                "level": "error", "event": "capability",
                                "cap": "network:fetch", "action": "blocked-domain",
                                "domain": domain, "url": url
                            })
                            raise RuntimeErrorLoom("network fetch disallowed under capability enforcement")
                    else:
                        self.receipt["logs"].append({
                            "level": "error", "event": "capability",
                            "cap": "network:fetch", "action": "blocked-scheme", "url": url
                        })
                        raise RuntimeErrorLoom("network fetch disallowed under capability enforcement")

                timeout = float(args.get("timeout") or DEFAULT_TIMEOUT)
                max_bytes = int(args.get("maxBytes") or DEFAULT_MAX_BYTES)
                result = self._fetcher(url, timeout=timeout, max_bytes=max_bytes)

                # optional sinks
                if isinstance(args.get("into"), str):
                    text = (result.get("body") or b"").decode("utf-8", errors="replace")
                    self.env[args["into"]] = text
                if isinstance(args.get("intoBytes"), str):
                    self.env[args["intoBytes"]] = int(len(result.get("body") or b""))
                if isinstance(args.get("intoStatus"), str):
                    self.env[args["intoStatus"]] = int(result.get("status", 0))
                if isinstance(args.get("intoType"), str):
                    self.env[args["intoType"]] = result.get("content_type", "")

                self._append_step({
                    "event": "fetch",
                    "url": result.get("url"),
                    "status": int(result.get("status", 0)),
                    "bytes": int(len(result.get("body") or b"")),
                    "truncated": bool(result.get("truncated")),
                    "verb": "Call",
                })
                return None, False

            # Unknown Call shape
            return None, False

        raise RuntimeErrorLoom(f"Unsupported verb: {canon_verb}")

    def exec_block(self, block: Dict[str, Any]) -> Tuple[Any, bool]:
        for step in list(block.get("steps") or []):
            res, returned = self.exec_step(step)
            if returned:
                return res, True
        return None, False

    def run(
        self,
        module: Dict[str, Any],
        inputs: Optional[Dict[str, Any]] = None,
        *,
        enforce_capabilities: Optional[bool] = None,
        capabilities: Optional[Dict[str, Any]] = None,
    ) -> Any:
        m = self._unwrap_module(module)
        if capabilities is not None:
            self._caps = capabilities
        enforced = self._enforce_default if enforce_capabilities is None else bool(enforce_capabilities)
        self._enforce_default = enforced  # update

        self.env = dict(inputs or {})
        self.evaluator = Evaluator(self.env)
        self.receipt.update({
            "engine": "interpreter",
            "ask": [],
            "logs": [],
            "callGraph": [],
            "steps": [],
        })
        res, did_return = self.exec_block({"steps": self._extract_flow(m)})
        self.receipt["env"] = dict(self.env)
        return res
