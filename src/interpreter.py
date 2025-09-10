# src/interpreter.py
from __future__ import annotations
from typing import Any, Dict, List, Tuple, Optional
from pathlib import Path
from .ast_builder import build_ast
from .tokenizer import tokenize
from .parser import parse
from .names import normalize_module_slug, check_capability

class RuntimeErrorLoom(Exception): pass

# ------------------------- expression evaluator -------------------------

class Evaluator:
    def __init__(self, env: Dict[str, Any]):
        self.env = env

    def eval(self, node: Optional[Dict[str, Any]]) -> Any:
        if node is None: return None
        t = node.get("type")
        if t in ("Number", "String", "Boolean"):
            return node.get("value")
        if t == "Identifier":
            name = node.get("name")
            if name in self.env:
                return self.env[name]
            raise RuntimeErrorLoom(f"Undefined identifier: {name}")
        if t == "Unary":
            op = node.get("op")
            v = self.eval(node.get("expr"))
            if op == "-": return -v
            if op == "+": return +v
            if op == "not": return not bool(v)
            raise RuntimeErrorLoom(f"unknown unary op: {op}")
        if t == "Binary":
            op = node.get("op")
            if op == "and":
                l = self.eval(node.get("left"))
                if not isinstance(l, bool):
                    raise RuntimeErrorLoom("and expects booleans")
                if not l: return False
                r = self.eval(node.get("right"))
                if not isinstance(r, bool):
                    raise RuntimeErrorLoom("and expects booleans")
                return l and r
            if op == "or":
                l = self.eval(node.get("left"))
                if not isinstance(l, bool):
                    raise RuntimeErrorLoom("or expects booleans")
                if l: return True
                r = self.eval(node.get("right"))
                if not isinstance(r, bool):
                    raise RuntimeErrorLoom("or expects booleans")
                return l or r

            l = self.eval(node.get("left")); r = self.eval(node.get("right"))
            if op == "+": return l + r
            if op == "-": return l - r
            if op == "*": return l * r
            if op == "/": return l / r
            if op == "==": return l == r
            if op == "!=": return l != r
            if op == "<": return l < r
            if op == "<=": return l <= r
            if op == ">": return l > r
            if op == ">=": return l >= r
            raise RuntimeErrorLoom(f"unknown binary op: {op}")
        if t == "Range":
            start = int(self.eval(node.get("start")))
            end = int(self.eval(node.get("end")))
            inclusive = bool(node.get("inclusive"))
            if inclusive:
                return list(range(start, end + 1))
            return list(range(start, end))
        if t == "Call":
            # Expressions don't support function calls yet
            return f"[expr-call:{node}]"
        # Fallback
        return str(node)

# --------------------------- interpreter core ----------------------------

class Interpreter:
    def __init__(self, registry: Optional[Dict[str, Dict[str, Any]]] = None,
                 capabilities: Optional[Dict[str, Any]] = None,
                 enforce_capabilities: bool = False):
        self.env: Dict[str, Any] = {}
        self.evaluator = Evaluator(self.env)
        self.registry = registry or {}
        self.capabilities = capabilities
        self.enforce_capabilities = bool(enforce_capabilities)
        self.receipt: Dict[str, Any] = {
            "engine": "interpreter",
            "logs": [],
            "ask": [],
            "callGraph": [],
            "steps": [],
            "env": {},
        }
        self._call_stack: List[str] = []

    @staticmethod
    def _get_expr(args: Dict[str, Any], *keys: str) -> Optional[Dict[str, Any]]:
        for k in keys:
            v = args.get(k)
            if v is not None: return v
        return None

    def _extract_flow(self, module: Dict[str, Any]) -> List[Dict[str, Any]]:
        return module.get("flow") or module.get("steps") or module.get("block", {}).get("steps") or []

    def exec_step(self, step: Dict[str, Any], step_index: int = 0) -> Tuple[Any, bool]:
        verb = step.get("verb")
        args = step.get("args", {}) or {}

        if verb == "Show":
            expr = self._get_expr(args, "expr", "text", "value")
            val = self.evaluator.eval(expr) if isinstance(expr, dict) else (expr if expr is not None else "")
            self.receipt["logs"].append(str(val))
            print(val)
            return None, False

        if verb == "Return":
            expr = self._get_expr(args, "expr", "value")
            val = self.evaluator.eval(expr) if isinstance(expr, dict) else expr
            return val, True

        if verb == "Ask":
            name = args.get("name")
            default_expr = args.get("default")
            if name not in self.env:
                self.env[name] = self.evaluator.eval(default_expr) if default_expr is not None else None
            self.receipt["ask"].append({"verb": "Ask", "name": name, "default": default_expr})
            return None, False

        if verb == "Choose":
            branches = args.get("branches") or []
            for idx, br in enumerate(branches):
                pred = br.get("when")
                if pred is not None:
                    val = bool(self.evaluator.eval(pred))
                    self.receipt["steps"].append({
                        "event": "choose",
                        "predicateTrace": [{"expr": pred, "value": val}],
                        "selected": {"branch": idx, "kind": "when"} if val else None,
                    })
                    if val:
                        body = br.get("steps") or br.get("block") or br.get("body") or []
                        if isinstance(body, dict):
                            body = body.get("steps") or []
                        for st in body:
                            res, returned = self.exec_step(st)
                            if returned:
                                return res, True
                        return None, False
                else:
                    body = br.get("steps") or br.get("block") or br.get("body") or []
                    if isinstance(body, dict):
                        body = body.get("steps") or []
                    for st in body:
                        res, returned = self.exec_step(st)
                        if returned:
                            self.receipt["steps"].append({
                                "event": "choose",
                                "predicateTrace": [],
                                "selected": {"branch": idx, "kind": "otherwise"},
                            })
                            return res, True
                    self.receipt["steps"].append({
                        "event": "choose",
                        "predicateTrace": [],
                        "selected": {"branch": idx, "kind": "otherwise"},
                    })
                    return None, False
            return None, False

        if verb == "Repeat":
            iterator = args.get("iterator")
            it_name = None
            if isinstance(iterator, dict) and "name" in iterator:
                it_name = iterator["name"]
            elif isinstance(iterator, str):
                it_name = iterator
            if not it_name:
                it_name = args.get("iter")

            iterable_expr = args.get("iterable")
            if iterable_expr is None:
                iterable_expr = args.get("range")
            if iterable_expr is None or not it_name:
                raise RuntimeErrorLoom("Malformed Repeat: missing iterator/iterable")

            if isinstance(iterable_expr, dict) and iterable_expr.get("type") == "Range":
                start = int(self.evaluator.eval(iterable_expr.get("start")))
                end = int(self.evaluator.eval(iterable_expr.get("end")))
                inclusive = bool(iterable_expr.get("inclusive"))
                values = list(range(start, end + 1 if inclusive else end))
            else:
                values = list(self.evaluator.eval(iterable_expr))

            blk = args.get("block") or args.get("steps") or args.get("body")
            if isinstance(blk, list):
                body_steps = blk
            elif isinstance(blk, dict):
                body_steps = blk.get("steps") or []
            else:
                body_steps = []

            for v in values:
                self.env[it_name] = v
                for st in body_steps:
                    res, returned = self.exec_step(st)
                    if returned:
                        return res, True
            return None, False

        if verb == "Call":
            raw_mod_name = args.get("module")
            inputs_obj = args.get("inputs") or {}
            child_inputs: Dict[str, Any] = {}
            for k, ex in inputs_obj.items():
                child_inputs[k] = self.evaluator.eval(ex)

            # Resolve callee from registry or Modules/<name>.loom
            callee = None
            if raw_mod_name in self.registry:
                callee = self.registry[raw_mod_name]
            else:
                # Try normalized key
                norm_key = normalize_module_slug(raw_mod_name or "")
                if norm_key in self.registry:
                    callee = self.registry[norm_key]
            if callee is None:
                mod_file = Path("Modules") / f"{raw_mod_name}.loom"
                if not mod_file.exists():
                    raise RuntimeErrorLoom(f"Call: cannot resolve module {raw_mod_name}")
                text = mod_file.read_text(encoding="utf-8")
                callee = build_ast(parse(tokenize(text)))

            # Prepare child interpreter (share registry/policy)
            child = Interpreter(registry=self.registry, capabilities=self.capabilities, enforce_capabilities=self.enforce_capabilities)
            # Carry env defaults (Ask fallbacks etc.)
            child.env.update(dict(self.env))
            # Bind explicit inputs
            child.env.update(child_inputs)

            # Execute child
            self._call_stack.append(callee.get("name") or raw_mod_name or "<anonymous>")
            try:
                child_result = child.exec_block({"steps": callee.get("flow") or []})
            finally:
                self._call_stack.pop()

            # Compute inputsResolved against child's view
            inputsResolved: Dict[str, Any] = {}
            asked = [a.get("name") for a in child.receipt.get("ask", []) if isinstance(a, dict)]
            for key in set(asked) | set(child_inputs.keys()):
                if key in child_inputs:
                    inputsResolved[key] = {"source": "explicit", "value": child_inputs[key]}
                else:
                    inputsResolved[key] = {"source": "default", "value": child.env.get(key)}

            # Capability check (warn-only by default)
            caller_raw = self._call_stack[-1] if self._call_stack else "<anonymous>"
            cap = check_capability(self.capabilities, caller_raw, raw_mod_name or "", action="Call")
            violation = (cap.get("mode") != "none" and not cap.get("allowed"))
            cap_record = dict(cap)
            cap_record["mode"] = ("enforce" if self.enforce_capabilities else "warn") if cap.get("mode") != "none" else "none"

            # Record step
            self.receipt["steps"].append({
                "event": "call",
                "module": raw_mod_name,
                "moduleNorm": normalize_module_slug(raw_mod_name or ""),
                "inputs": dict(child_inputs),
                "inputsResolved": inputsResolved,
                "capabilityCheck": cap_record,
            })

            # Record callGraph (keep raw for parity; add normalized alongside)
            self.receipt["callGraph"].append({
                "from": caller_raw,
                "to": raw_mod_name,
                "fromNorm": normalize_module_slug(caller_raw or ""),
                "toNorm": normalize_module_slug(raw_mod_name or ""),
                "atStep": step_index
            })

            # Enforce if configured
            if violation and self.enforce_capabilities:
                raise RuntimeErrorLoom(f"Capability denied: Call from '{caller_raw}' to '{raw_mod_name}'")

            save_as = args.get("result") or args.get("saveAs") or args.get("save") or args.get("as")
            if save_as:
                self.env[save_as] = child_result

            return None, False

        raise RuntimeErrorLoom(f"Unknown verb: {verb}")

    def exec_block(self, block: Dict[str, Any]) -> Any:
        result = None
        for idx, step in enumerate(block.get("steps", [])):
            res, returned = self.exec_step(step, step_index=idx)
            if returned:
                result = res
                break
        return result

    def run(self, module: Dict[str, Any], inputs: Optional[Dict[str, Any]] = None) -> Any:
        if inputs:
            self.env.update(inputs)
        name = module.get("name") or module.get("module", {}).get("name") or "<anonymous>"
        self._call_stack.append(name)
        try:
            flow = self._extract_flow(module)
            result = self.exec_block({"steps": flow})
            return result
        finally:
            self._call_stack.pop()
            self.receipt["env"] = dict(self.env)

def _load_or_build_module(path: str) -> Dict[str, Any]:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    return build_ast(parse(tokenize(text)))

def run_module_from_file(path: str, inputs: Optional[Dict[str, Any]] = None) -> Tuple[Any, Dict[str, Any]]:
    module = _load_or_build_module(path)
    interp = Interpreter()
    result = interp.run(module, inputs=inputs or {})
    return result, interp.receipt

def run_tests_from_file(path: str) -> Tuple[int, int, List[Any]]:
    module = _load_or_build_module(path)
    tests = module.get("tests") or []
    passed, results = 0, []
    from .expr import parse_expr
    def coerce_scalar(v: Any) -> Any:
        if isinstance(v, (int, float, bool)): return v
        if isinstance(v, str):
            s = v.strip().rstrip(".")
            try:
                node = parse_expr(s)
                return Evaluator({}).eval(node)
            except Exception:
                if s.startswith('"') and s.endswith('"'):
                    return s[1:-1]
                return s
        return v
    def coerce_inputs(d: Dict[str, Any]) -> Dict[str, Any]:
        return {k: coerce_scalar(v) for k, v in (d or {}).items()}
    for t in tests:
        name = t.get("name") or "test"
        expected = coerce_scalar(t.get("expected"))
        inputs = coerce_inputs(t.get("inputs") or t.get("input") or {})
        actual = Interpreter().run(module, inputs=inputs)
        ok = (actual == expected)
        if ok: passed += 1
        results.append((name, ok, actual, expected))
    return passed, len(tests), results
