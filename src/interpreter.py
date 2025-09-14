"""Loom Interpreter aligned with SPEC-001, extended for SPEC-002 fetch.

- Verb synonyms supported (Make, Show, Return, Ask, Choose, Repeat, Call).
- Make accepts LHS: name/target/var/id/key/binding/lhs; RHS: expr/value/to/rhs/with/is/equals.
- Choose supports branches with {"when": <expr>} and {"otherwise": true}.
- Evaluator supports: Identifier, String, Number, Bool, Binary/BinaryExpr.
- Receipt shape (unchanged for SPEC-001 goldens): ask, callGraph, engine, env, logs, steps.
- SPEC-002: Call can fetch a URL when args has {"url": "..."} with limits and optional sinks:
    into, intoBytes, intoStatus, intoType. Network calls are blocked when enforcement is enabled.
"""

from typing import Any, Dict, List, Optional, Tuple
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
                    args["name"] = args.pop(k); break
        if "expr" not in args:
            for k in ("value", "to", "rhs", "with", "is", "equals"):
                if k in args:
                    args["expr"] = args.pop(k); break

    elif canon == "Show":
        if "expr" not in args:
            if "text" in args: args["expr"] = args.get("text")
            elif "value" in args: args["expr"] = args.get("value")

    elif canon == "Ask":
        if "text" not in args and "prompt" in args:
            args["text"] = args.get("prompt")
        if "store" not in args:
            for k in ("name", "var", "target", "lhs", "key"):
                if k in args:
                    args["store"] = args.pop(k); break

    elif canon == "Repeat":
        if "iterator" not in args:
            if "var" in args: args["iterator"] = args.pop("var")
            elif "it" in args: args["iterator"] = args.pop("it")
        if "iterable" not in args and "in" in args:
            args["iterable"] = args.pop("in")
        if "block" not in args and "steps" not in args and "body" in args:
            args["block"] = {"steps": args.pop("body")}
        if "block" not in args and isinstance(args.get("steps"), list):
            args["block"] = {"steps": args.pop("steps")}

    elif canon == "Call":
        # Accept {"module":"..."}, {"target":"..."} or a direct URL via {"url":"..."} / {"http":"..."}
        if "module" not in args and "target" in args:
            args["module"] = args.pop("target")

    return canon, args, raw or None

class Evaluator:
    """Tiny expression evaluator for Loom-ish AST nodes."""
    def __init__(self, env: Dict[str, Any]): self.env = env
    def eval(self, node: Any) -> Any:
        if node is None: return None
        if not isinstance(node, dict): return node
        typ = node.get("type")
        if typ == "Identifier": return self.env.get(node.get("name"))
        if typ == "String":     return node.get("value", "")
        if typ == "Number":     return node.get("value", 0)
        if typ == "Bool":       return bool(node.get("value"))
        if typ in ("Binary", "BinaryExpr"):
            op = node.get("op")
            L = self.eval(node.get("left")); R = self.eval(node.get("right"))
            if op == "+": return L + R
            if op == "-": return L - R
            if op == "*": return L * R
            if op == "/": return L / R
            if op in ("==","equals"): return L == R
            if op in ("!=","notEquals"): return L != R
            if op in ("<","lt"): return L < R
            if op in ("<=","lte"): return L <= R
            if op in (">","gt"): return L > R
            if op in (">=","gte"): return L >= R
            raise RuntimeErrorLoom(f"Unsupported binary op: {op}")
        return node

class Interpreter:
    def __init__(self, *, enforce_capabilities: bool = False, fetcher=None):
        self._enforce_default = bool(enforce_capabilities)
        self._fetcher = fetcher or real_fetcher
        self.env: Dict[str, Any] = {}
        self.receipt: Dict[str, Any] = {
            "ask": [],
            "callGraph": [],
            "engine": "interpreter",
            "env": {},
            "logs": [],
            "steps": [],
        }

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
            store  = args.get("store")
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
            # Path A: module-to-module (existing behavior, record only)
            if "module" in args and "url" not in args and "http" not in args:
                target_raw = args.get("module")
                target_norm = normalize_module_slug(target_raw or "")
                self.receipt["callGraph"].append({"from": None, "to": target_raw})
                return None, False

            # Path B: SPEC-002 URL fetch
            url = args.get("url") or args.get("http")
            if url:
                if self._enforce_default:
                    # Capabilities enforced: block network usage
                    self.receipt["logs"].append({"level": "error", "event": "capability", "cap": "network:fetch", "action": "blocked"})
                    raise RuntimeErrorLoom("network fetch disallowed under capability enforcement")
                timeout = float(args.get("timeout") or DEFAULT_TIMEOUT)
                max_bytes = int(args.get("maxBytes") or DEFAULT_MAX_BYTES)
                result = self._fetcher(url, timeout=timeout, max_bytes=max_bytes)
                # optional sinks
                if isinstance(args.get("into"), str):
                    text = result["body"].decode("utf-8", errors="replace")
                    self.env[args["into"]] = text
                if isinstance(args.get("intoBytes"), str):
                    self.env[args["intoBytes"]] = int(len(result["body"]))
                if isinstance(args.get("intoStatus"), str):
                    self.env[args["intoStatus"]] = int(result.get("status", 0))
                if isinstance(args.get("intoType"), str):
                    self.env[args["intoType"]] = result.get("content_type", "")
                # record minimal step
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
    ) -> Any:
        m = self._unwrap_module(module)
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
