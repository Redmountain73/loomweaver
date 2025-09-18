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

import copy
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse
import xml.etree.ElementTree as ET

from .tokenizer import tokenize
from .parser import parse
from .ast_builder import build_ast
from .overlays import load_overlays, ExpandOptions, OverlayMapping, expand_module_ast
from .names import normalize_module_slug
from .http_client import DEFAULT_TIMEOUT, DEFAULT_MAX_BYTES
from .fetchers import real_fetcher, fixture_fetcher  # <-- include fixture fetcher

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

    elif canon == "Choose":
        if "branches" not in args and isinstance(step.get("branches"), list):
            args["branches"] = copy.deepcopy(step.get("branches"))

    elif canon == "Repeat":
        if "iterator" not in args:
            if "iter" in args:
                args["iterator"] = args.pop("iter")
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
        if "block" not in args and isinstance(step.get("block"), dict):
            args["block"] = {"steps": copy.deepcopy(step.get("block", {}).get("steps", []))}
        if "block" not in args and isinstance(step.get("block"), list):
            args["block"] = {"steps": copy.deepcopy(step.get("block"))}
        if "block" not in args and isinstance(step.get("steps"), list):
            args["block"] = {"steps": copy.deepcopy(step.get("steps"))}

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
        if typ in ("Bool", "Boolean"):
            return bool(node.get("value"))
        if typ in ("Binary", "BinaryExpr"):
            op = node.get("op")
            left_node = node.get("left")
            right_node = node.get("right")
            if op in ("and", "&&"):
                left_val = self.eval(left_node)
                if not isinstance(left_val, bool):
                    raise RuntimeErrorLoom("Boolean 'and' requires boolean operands")
                if not left_val:
                    return False
                right_val = self.eval(right_node)
                if not isinstance(right_val, bool):
                    raise RuntimeErrorLoom("Boolean 'and' requires boolean operands")
                return left_val and right_val
            if op in ("or", "||"):
                left_val = self.eval(left_node)
                if not isinstance(left_val, bool):
                    raise RuntimeErrorLoom("Boolean 'or' requires boolean operands")
                if left_val:
                    return True
                right_val = self.eval(right_node)
                if not isinstance(right_val, bool):
                    raise RuntimeErrorLoom("Boolean 'or' requires boolean operands")
                return left_val or right_val
            L = self.eval(left_node)
            R = self.eval(right_node)
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
        if typ in ("Unary", "UnaryExpr"):
            op = node.get("op")
            operand = self.eval(node.get("expr") or node.get("value"))
            if op in ("-", "neg"):
                if not isinstance(operand, (int, float)):
                    raise RuntimeErrorLoom("Unary '-' requires number")
                return -operand
            if op == "+":
                if not isinstance(operand, (int, float)):
                    raise RuntimeErrorLoom("Unary '+' requires number")
                return +operand
            if op in ("not", "!"):
                return not bool(operand)
            raise RuntimeErrorLoom(f"Unsupported unary op: {op}")
        return node

class Interpreter:
    def __init__(
        self,
        *,
        enforce_capabilities: bool = False,
        fetcher=None,
        capabilities: Optional[Dict[str, Any]] = None,
        registry: Optional[Dict[str, Any]] = None,
    ):
        self._enforce_default = bool(enforce_capabilities)
        self._fetcher = fetcher or real_fetcher
        self._caps = capabilities or {}
        self._registry: Dict[str, Any] = dict(registry or {})
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

    def _resolve_call_inputs(self, raw_inputs: Dict[str, Any]) -> Dict[str, Any]:
        resolved: Dict[str, Any] = {}
        for key, expr in (raw_inputs or {}).items():
            resolved[key] = self.evaluator.eval(expr) if isinstance(expr, dict) else expr
        return resolved

    def _lookup_module(self, name: Optional[str]) -> Optional[Dict[str, Any]]:
        if not isinstance(name, str):
            return None
        if name in self._registry:
            return self._registry[name]
        try:
            slug = normalize_module_slug(name)
            for raw, module in self._registry.items():
                try:
                    if normalize_module_slug(raw) == slug:
                        return module
                except Exception:
                    continue
        except Exception:
            return None
        return None

    @staticmethod
    def _trace_expr_repr(expr: Any) -> Any:
        if isinstance(expr, dict) and expr.get("type") == "Boolean":
            return "true" if bool(expr.get("value")) else "false"
        return expr

    def _lineage_from_step(self, step: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(step, dict):
            return {}
        lineage = {
            "rawVerb": step.get("rawVerb"),
            "mappedVerb": step.get("mappedVerb"),
            "overlayDomain": step.get("overlayDomain"),
            "overlayVersion": step.get("overlayVersion"),
            "capabilityCheck": step.get("capabilityCheck"),
        }
        if lineage["rawVerb"] is None:
            lineage["rawVerb"] = step.get("verb")
        if lineage["mappedVerb"] is None:
            lineage["mappedVerb"] = step.get("verb")
        if lineage["capabilityCheck"] is None:
            lineage["capabilityCheck"] = "n/a"
        return lineage

    def _append_step(self, entry: Dict[str, Any], step_lineage: Optional[Dict[str, Any]] = None) -> None:
        step_lineage = step_lineage or {}
        lineage = {
            "rawVerb": step_lineage.get("rawVerb"),
            "mappedVerb": step_lineage.get("mappedVerb"),
            "overlayDomain": step_lineage.get("overlayDomain"),
            "overlayVersion": step_lineage.get("overlayVersion"),
            "capabilityCheck": step_lineage.get("capabilityCheck"),
        }
        if lineage["rawVerb"] is None:
            lineage["rawVerb"] = entry.get("verb")
        if lineage["mappedVerb"] is None:
            lineage["mappedVerb"] = entry.get("verb")
        if lineage["capabilityCheck"] is None:
            lineage["capabilityCheck"] = "n/a"
        for key, value in lineage.items():
            entry[key] = value
        self.receipt["steps"].append(entry)

    _brace_rx = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}")

    def _interpolate(self, s: str) -> str:
        def repl(m):
            name = m.group(1)
            val = self.env.get(name)
            return "" if val is None else str(val)
        return self._brace_rx.sub(repl, s)

    def _url_value(self, node_or_str: Any) -> str:
        if isinstance(node_or_str, dict):
            val = self.evaluator.eval(node_or_str)
            return "" if val is None else str(val)
        if isinstance(node_or_str, str):
            return self._interpolate(node_or_str)
        return ""

    # ---- capability helpers
    def _caps_root(self) -> Dict[str, Any]:
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
        netloc = urlparse(url).netloc.split("@")[-1]
        return netloc.split(":")[0].lower()

    # ---------- execution
    def exec_step(self, step: Dict[str, Any]) -> Tuple[Any, bool]:
        canon_verb, args, raw_verb = normalize_verb_and_args(step)
        lineage_info = self._lineage_from_step(step)

        if canon_verb == "Make":
            name = args.get("name")
            if not isinstance(name, str) or not name:
                raise RuntimeErrorLoom("Make: missing 'name'")
            val_node = self._get_expr(args, "expr", "value")
            value = self.evaluator.eval(val_node) if isinstance(val_node, dict) else val_node
            self.env[name] = value
            self._append_step({"event": "make", "name": name, "value": value, "verb": "Make"}, lineage_info)
            return None, False

        if canon_verb == "Show":
            expr = self._get_expr(args, "expr", "value", "text")
            value = self.evaluator.eval(expr) if isinstance(expr, dict) else expr
            self._append_step({"event": "show", "value": value, "verb": "Show"}, lineage_info)
            print(value)
            self.receipt.setdefault("logs", []).append(value)
            return None, False

        if canon_verb == "Return":
            expr = self._get_expr(args, "expr", "value")
            value = self.evaluator.eval(expr) if isinstance(expr, dict) else expr
            self._append_step({"event": "return", "value": value, "verb": "Return"}, lineage_info)
            return value, True

        if canon_verb == "Ask":
            prompt = (args.get("text") or "")
            store = args.get("store")
            default_raw = args.get("default", "")
            default_value = self.evaluator.eval(default_raw) if isinstance(default_raw, dict) else default_raw
            answer = None
            if isinstance(store, str) and store:
                if store in self.env and self.env[store] not in (None, ""):
                    answer = self.env[store]
                else:
                    answer = default_value
                    self.env[store] = answer
            self.receipt["ask"].append({"prompt": prompt, "store": store, "value": answer})
            return None, False

        if canon_verb == "Choose":
            branches: List[Dict[str, Any]] = list(args.get("branches") or [])
            for idx, br in enumerate(branches):
                if "when" in br:
                    cond_expr = br.get("when")
                    ok = self.evaluator.eval(cond_expr)
                    trace_expr = self._trace_expr_repr(cond_expr)
                    choose_entry = {
                        "event": "choose",
                        "predicateTrace": [{"expr": trace_expr, "value": bool(ok)}],
                        "verb": "Choose",
                        "rawVerb": None,
                        "selected": None,
                    }
                    if ok:
                        choose_entry["selected"] = {"branch": idx, "kind": "when"}
                        self._append_step(choose_entry, lineage_info)
                        res, did_return = self.exec_block({"steps": br.get("steps") or []})
                        if did_return:
                            return res, True
                        return res, False
                    else:
                        self._append_step(choose_entry, lineage_info)
                        continue
                elif br.get("otherwise"):
                    res, did_return = self.exec_block({"steps": br.get("steps") or []})
                    self._append_step({
                        "event": "choose",
                        "predicateTrace": [],
                        "selected": {"branch": idx, "kind": "otherwise"},
                        "verb": "Choose",
                    }, lineage_info)
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
                start_raw = rng.get("start", 0)
                end_raw = rng.get("end", 0)
                step_raw = rng.get("step", 1)
                inclusive = bool(rng.get("inclusive"))

                start_val = self.evaluator.eval(start_raw) if isinstance(start_raw, dict) else start_raw
                end_val = self.evaluator.eval(end_raw) if isinstance(end_raw, dict) else end_raw
                step_val = self.evaluator.eval(step_raw) if isinstance(step_raw, dict) else step_raw

                try:
                    start_int = int(start_val)
                    end_int = int(end_val)
                    step_int = int(step_val) if step_val not in (None, 0) else 1
                except Exception as exc:  # pragma: no cover - defensive
                    raise RuntimeErrorLoom("Repeat range bounds must be numeric") from exc
                if step_int == 0:
                    step_int = 1
                if inclusive:
                    end_int += 1 if step_int > 0 else -1
                it = range(start_int, end_int, step_int)
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
                    ns = {"atom": "http://www.w3.org/2005/Atom"}
                    root = xml_safe_fromstring(src_text)
                    node = root.find(".//atom:entry/atom:title", ns)
                    if node is None:
                        node = root.find(".//atom:title", ns)
                    if node is None:
                        node = root.find(".//title") or root.find("title")
                    if node is not None and node.text is not None:
                        title = node.text.strip()
                except Exception:
                    title = ""

                if isinstance(args.get("into"), str):
                    self.env[args["into"]] = title
                self._append_step({"event": "parse", "op": "xml.firstTitle", "verb": "Call"}, lineage_info)
                return None, False

            # Path A: module-to-module bookkeeping
            if "module" in args and "url" not in args and "http" not in args and "op" not in args:
                target_raw = args.get("module")
                self.receipt["callGraph"].append({"from": None, "to": target_raw})
                call_inputs = self._resolve_call_inputs(args.get("inputs") or {})
                callee = self._lookup_module(target_raw)
                if callee is not None:
                    nested = Interpreter(
                        enforce_capabilities=self._enforce_default,
                        fetcher=self._fetcher,
                        capabilities=self._caps,
                        registry=self._registry,
                    )
                    result_value = nested.run(copy.deepcopy(callee), inputs=call_inputs)
                    resolved_details: Dict[str, Any] = {}
                    for ask_entry in nested.receipt.get("ask", []):
                        store = ask_entry.get("store")
                        if not isinstance(store, str):
                            continue
                        value = ask_entry.get("value")
                        if store in call_inputs:
                            resolved_details[store] = {"value": call_inputs[store], "source": "caller", "meta": {}}
                        else:
                            source = "default" if value is not None else "missing"
                            resolved_details[store] = {"value": value, "source": source, "meta": {}}
                    for key, val in call_inputs.items():
                        resolved_details.setdefault(key, {"value": val, "source": "caller", "meta": {}})
                    call_entry = {
                        "event": "call",
                        "module": target_raw,
                        "inputs": call_inputs,
                        "inputsResolved": resolved_details,
                        "verb": "Call",
                    }
                    self._append_step(call_entry, lineage_info)
                    if isinstance(args.get("result"), str):
                        self.env[args["result"]] = result_value
                    return None, False
                call_entry = {
                    "event": "call",
                    "module": target_raw,
                    "inputs": call_inputs,
                    "inputsResolved": {
                        key: {"value": val, "source": "caller", "meta": {}}
                        for key, val in call_inputs.items()
                    },
                    "verb": "Call",
                }
                self._append_step(call_entry, lineage_info)
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
                        if domain not in set(self._allowed_domains()):
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

                # Choose fetcher: route fixture:// to fixture_fetcher always
                fetch_fn = fixture_fetcher if url.startswith("fixture://") else self._fetcher

                timeout = float(args.get("timeout") or DEFAULT_TIMEOUT)
                max_bytes = int(args.get("maxBytes") or DEFAULT_MAX_BYTES)
                result = fetch_fn(url, timeout=timeout, max_bytes=max_bytes)

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
                }, lineage_info)
                return None, False

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
        self._enforce_default = enforced

        self.env = dict(inputs or {})
        self.evaluator = Evaluator(self.env)
        self.receipt.update({"engine": "interpreter", "ask": [], "logs": [], "callGraph": [], "steps": []})
        res, did_return = self.exec_block({"steps": self._extract_flow(m)})
        self.receipt["env"] = dict(self.env)
        return res

# xml parse helper (safe-ish ET wrapper to normalize parser behavior)
def xml_safe_fromstring(text: str):
    try:
        return ET.fromstring(text or "")
    except Exception:
        return ET.fromstring("<root/>")


def _load_module_ast_from_file(path: str) -> Dict[str, Any]:
    text = Path(path).read_text(encoding="utf-8")
    return build_ast(parse(tokenize(text)))


def _prepare_overlay_runtime(
    overlay_names: Optional[List[str]],
    *,
    no_unknown_verbs: bool,
    enforce_capabilities: bool,
    granted_capabilities: Optional[List[str]] = None,
) -> Tuple[Dict[str, OverlayMapping], ExpandOptions]:
    names = list(overlay_names or [])
    overlays = load_overlays(names)
    opts = ExpandOptions(
        overlay_names=names,
        no_unknown_verbs=bool(no_unknown_verbs),
        enforce_capabilities=bool(enforce_capabilities),
        granted_capabilities=list(granted_capabilities or []),
    )
    return overlays, opts


def _attach_overlay_metadata(
    receipt: Dict[str, Any],
    overlay_names: List[str],
    warnings: Optional[List[str]] = None,
) -> None:
    loaded = ["core"] + [name for name in overlay_names if name and name != "core"]
    # Deduplicate while preserving order
    seen = set()
    ordered_loaded = []
    for name in loaded:
        if name in seen:
            continue
        seen.add(name)
        ordered_loaded.append(name)
    receipt["overlaysLoaded"] = ordered_loaded
    if warnings:
        logs = receipt.setdefault("logs", [])
        for warn in warnings:
            logs.append({"level": "warning", "event": "overlay", "message": warn})


def run_module_from_file(
    module_path: str,
    inputs: Optional[Dict[str, Any]] = None,
    *,
    overlay_names: Optional[List[str]] = None,
    no_unknown_verbs: bool = False,
    enforce_capabilities: bool = False,
    granted_capabilities: Optional[List[str]] = None,
) -> Tuple[Any, Dict[str, Any]]:
    module_ast = _load_module_ast_from_file(module_path)
    overlays, opts = _prepare_overlay_runtime(
        overlay_names,
        no_unknown_verbs=no_unknown_verbs,
        enforce_capabilities=enforce_capabilities,
        granted_capabilities=granted_capabilities,
    )
    expanded_module, overlay_warns = expand_module_ast(module_ast, overlays, opts)

    interpreter = Interpreter(enforce_capabilities=enforce_capabilities)
    result = interpreter.run(expanded_module, inputs=inputs)
    receipt = copy.deepcopy(interpreter.receipt)
    _attach_overlay_metadata(receipt, opts.overlay_names, overlay_warns)
    return result, receipt


def run_tests_from_file(
    module_path: str,
    *,
    overlay_names: Optional[List[str]] = None,
    no_unknown_verbs: bool = False,
    enforce_capabilities: bool = False,
    granted_capabilities: Optional[List[str]] = None,
) -> Tuple[int, int, List[Dict[str, Any]]]:
    module_ast = _load_module_ast_from_file(module_path)
    overlays, opts = _prepare_overlay_runtime(
        overlay_names,
        no_unknown_verbs=no_unknown_verbs,
        enforce_capabilities=enforce_capabilities,
        granted_capabilities=granted_capabilities,
    )
    expanded_module, overlay_warns = expand_module_ast(module_ast, overlays, opts)

    tests = list((expanded_module.get("tests") or []))
    results: List[Dict[str, Any]] = []
    passed = 0

    for idx, test_case in enumerate(tests, start=1):
        name = test_case.get("name") or f"test-{idx}"
        inputs = dict(test_case.get("inputs") or {})
        expected = test_case.get("expected", test_case.get("expect"))

        interpreter = Interpreter(enforce_capabilities=enforce_capabilities)
        result = interpreter.run(copy.deepcopy(expanded_module), inputs=inputs)
        receipt = copy.deepcopy(interpreter.receipt)
        warn_payload = overlay_warns if idx == 1 else []
        _attach_overlay_metadata(receipt, opts.overlay_names, warn_payload)

        ok = (result == expected)
        if ok:
            passed += 1

        results.append({
            "name": name,
            "inputs": inputs,
            "expected": expected,
            "actual": result,
            "pass": ok,
            "receipt": receipt,
        })

    return passed, len(tests), results
