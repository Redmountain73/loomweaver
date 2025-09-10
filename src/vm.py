# src/vm.py
from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple
from zfc import zfc_run

Instruction = Tuple[str, Any]

class VMError(Exception): ...
class TypeErrorLoom(VMError): ...
class RuntimeErrorLoom(VMError): ...

class VM:
    def __init__(self, module_name: str = "<anonymous>"):
        self.stack: List[Any] = []
        self.env: Dict[str, Any] = {}
        self.ip: int = 0
        self.code: List[Instruction] = []
        self.logs: List[Any] = []
        self.ask_events: List[Dict[str, Any]] = []
        self.iter_states: Dict[str, Dict[str, Any]] = {}
        self.module_name: str = module_name
        self.receipt: Dict[str, Any] = {
            "engine": "vm",
            "logs": [],
            "steps": [],
            "callGraph": [],
            "ask": [],
            "env": {}
        }
        self._choose_stack: List[Dict[str, Any]] = []

    # --- Helpers ------------------------------------------------------------
    def _pop(self) -> Any:
        if not self.stack:
            raise RuntimeErrorLoom("stack underflow")
        return self.stack.pop()

    def _peek(self) -> Any:
        if not self.stack:
            raise RuntimeErrorLoom("stack underflow")
        return self.stack[-1]

    # --- Execution ----------------------------------------------------------
    def run(self, code: List[Instruction], inputs: Optional[Dict[str, Any]] = None,
            module_name: Optional[str] = None) -> Any:
        self.code = code
        self.env = dict(inputs or {})
        self.stack = []
        self.logs = []
        self.ask_events = []
        self.iter_states = {}
        self._choose_stack = []
        self.ip = 0
        self.module_name = module_name or "<anonymous>"
        self.receipt = {"engine": "vm", "logs": [], "steps": [], "callGraph": [], "ask": [], "env": {}}
        ret: Any = None

        while self.ip < len(self.code):
            op, arg = self.code[self.ip]
            self.ip += 1

            # Stack & env
            if op == "PUSH_CONST":
                self.stack.append(arg); continue
            if op == "LOAD":
                self.stack.append(self.env.get(arg)); continue
            if op == "STORE":
                val = self._pop()
                self.env[arg] = val
                continue

            # Show
            if op == "SHOW":
                self.logs.append(str(self._pop()))
                continue

            # Ask (with default)
            if op in ("ASK", "ASK_DEFAULT"):
                name, default = arg
                if name not in self.env:
                    self.env[name] = default
                self.ask_events.append({"name": name})
                continue

            # Arithmetic
            if op in ("ADD","SUB","MUL","DIV"):
                b = self._pop(); a = self._pop()
                if op == "ADD": self.stack.append(a + b); continue
                if op == "SUB": self.stack.append(a - b); continue
                if op == "MUL": self.stack.append(a * b); continue
                if op == "DIV": self.stack.append(a / b); continue
            if op == "NEG":
                v = self._pop()
                if not isinstance(v, (int, float)):
                    raise TypeErrorLoom("unary - requires number")
                self.stack.append(-v); continue

            # Comparison
            if op in ("EQ","NE","LT","LE","GT","GE"):
                b = self._pop(); a = self._pop()
                if op == "EQ": self.stack.append(a == b); continue
                if op == "NE": self.stack.append(a != b); continue
                if op == "LT": self.stack.append(a < b); continue
                if op == "LE": self.stack.append(a <= b); continue
                if op == "GT": self.stack.append(a > b); continue
                if op == "GE": self.stack.append(a >= b); continue

            # Boolean
            if op == "NOT":
                v = self._pop()
                if not isinstance(v, bool):
                    raise TypeErrorLoom("not requires boolean")
                self.stack.append(not v); continue
            if op in ("AND","OR"):
                b = self._pop(); a = self._pop()
                if not isinstance(a, bool) or not isinstance(b, bool):
                    raise TypeErrorLoom(f"{op.lower()} requires booleans")
                self.stack.append(a and b if op == "AND" else a or b); continue

            # Return (support both mnemonics)
            if op in ("RET", "RETURN"):
                ret = self._pop()
                break

            # Choose receipts
            if op == "CHOOSE_TRACE":
                val = self._pop()
                self.receipt["steps"].append({"event": "choose",
                                              "predicateTrace": [{"expr": arg, "value": bool(val)}],
                                              "selected": None})
                continue
            if op == "CHOOSE_SELECT":
                if self.receipt["steps"] and self.receipt["steps"][-1].get("event") == "choose":
                    self.receipt["steps"][-1]["selected"] = {"branch": int(arg), "kind": "when"}
                continue
            if op == "CHOOSE_OTHERWISE":
                self.receipt["steps"].append({"event": "choose",
                                              "predicateTrace": [],
                                              "selected": {"branch": int(arg), "kind": "otherwise"}})
                continue

            # Repeat lowering
            if op == "BUILD_RANGE":
                inclusive = bool(arg)
                end_v = self._pop()
                start_v = self._pop()
                try:
                    s = int(start_v); e = int(end_v)
                except Exception as e:
                    raise RuntimeErrorLoom(f"Range endpoints must be integers: {e}")
                if s <= e:
                    stop = e + (1 if inclusive else 0)
                    self.stack.append(list(range(s, stop, 1)))
                else:
                    stop = e - (1 if inclusive else 0)
                    self.stack.append(list(range(s, stop, -1)))
                continue

            if op == "ITER_PUSH":
                it_name = str(arg)
                iterable = self._pop()
                if not isinstance(iterable, list):
                    raise RuntimeErrorLoom("Repeat requires a list iterable")
                self.iter_states[it_name] = {"iterable": iterable, "index": 0}
                continue

            if op == "ITER_NEXT":
                it_name = str(arg)
                st = self.iter_states.get(it_name) or {"iterable": [], "index": 0}
                idx = st["index"]; iterb = st["iterable"]
                if idx < len(iterb):
                    self.stack.append(iterb[idx])
                    st["index"] = idx + 1
                    self.iter_states[it_name] = st
                    self.stack.append(True)
                else:
                    self.stack.append(False)
                continue

            if op == "JMP_IF_FALSE":
                target = int(arg)
                v = self._pop()
                if not bool(v):
                    self.ip = target
                continue

            if op == "JMP":
                self.ip = int(arg)
                continue

            # Call (now wrapped in Zero-Failure Contract)
            if op == "CALL":
                callee_name = str(arg.get("module"))
                inputs = arg.get("inputs") or {}
                child_code = arg.get("code") or []
                child_mod_name = arg.get("moduleName") or callee_name or "<anonymous>"
                at_step = int(arg.get("atStep") or 0)

                child = VM()

                def _invoke():
                    return child.run(child_code, inputs=inputs, module_name=child_mod_name)

                env_call = zfc_run(
                    _invoke,
                    default=None,
                    cb_key=f"module:{callee_name}",
                    cache_key=f"module:{callee_name}",
                )

                # Record the attempted call in callGraph regardless of success
                self.receipt["callGraph"].append({
                    "from": self.module_name,
                    "to": callee_name,
                    "atStep": at_step
                })

                # Record a step with the envelope for observability
                self.receipt["steps"].append({
                    "verb": "Call",
                    "module": callee_name,
                    "moduleName": child_mod_name,
                    "inputs": inputs,
                    "atStep": at_step,
                    "envelope": env_call.to_receipt()
                })

                # On success, merge child artifacts (logs/asks)
                if not env_call.degraded:
                    self.logs.extend(child.logs)
                    self.ask_events.extend(child.ask_events)

                # Push the (possibly synthetic) value so the flow always progresses
                self.stack.append(env_call.value)
                continue

            raise RuntimeErrorLoom(f"Unknown opcode: {op}")

        self.receipt["logs"] = [str(x) for x in self.logs]
        self.receipt["ask"] = self.ask_events
        self.receipt["env"] = dict(self.env)
        return ret
