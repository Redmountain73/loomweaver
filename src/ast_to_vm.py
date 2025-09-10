# src/ast_to_vm.py
# ELI5: turn the little LEGO AST blocks (Make, Return, Choose) into the VM's opcodes.

from __future__ import annotations
from typing import Any, Dict, List, Tuple

Instruction = Tuple[str, Any]

# ---------- expressions ----------

def _emit_expr(node: Dict[str, Any]) -> List[Instruction]:
    """Compile an expression node to stack ops; result on top of the stack."""
    t = node.get("type")
    if t == "String":
        return [("PUSH_CONST", node.get("value", ""))]
    if t == "Number":
        return [("PUSH_CONST", node.get("value", 0))]
    if t == "Identifier":
        return [("LOAD", node.get("name", ""))]
    if t == "Unary":
        op = node.get("op")
        code = _emit_expr(node.get("expr") or {"type": "String", "value": ""})
        if op == "NOT":
            code.append(("NOT", None))
            return code
        # Unknown unary → just pass-through
        return code
    if t == "Binary":
        op = (node.get("op") or "").upper()
        left = _emit_expr(node.get("left") or {"type": "Number", "value": 0})
        right = _emit_expr(node.get("right") or {"type": "Number", "value": 0})
        code = left + right
        # Map to VM comparison ops
        if op == "==":
            code.append(("EQ", None))
        elif op == "!=":
            code.append(("NE", None))
        elif op == ">":
            code.append(("GT", None))
        elif op == ">=":
            code.append(("GE", None))
        elif op == "<":
            code.append(("LT", None))
        elif op == "<=":
            code.append(("LE", None))
        else:
            # Unknown binary op → fallback to equality on stringified pieces
            code.append(("EQ", None))
        return code

    # Fallback: push stringified node
    return [("PUSH_CONST", str(node))]

# ---------- statements ----------

def _emit_steps(steps: List[Dict[str, Any]], out: List[Instruction]) -> None:
    """Append compiled steps to 'out'."""
    i = 0
    while i < len(steps):
        st = steps[i]
        verb = (st.get("verb") or "").upper()

        if verb == "MAKE":
            var = st.get("args", {}).get("var", "")
            expr = st.get("args", {}).get("expr", {"type": "String", "value": ""})
            out += _emit_expr(expr)
            out.append(("STORE", var))
            i += 1
            continue

        if verb == "RETURN":
            expr = st.get("args", {}).get("expr", {"type": "String", "value": ""})
            out += _emit_expr(expr)
            out.append(("RET", None))
            i += 1
            continue

        if verb == "SHOW":
            text = st.get("args", {}).get("text", "")
            out.append(("PUSH_CONST", str(text)))
            out.append(("SHOW", None))
            i += 1
            continue

        if verb == "CHOOSE":
            # Structure:
            # {"verb":"Choose","args":{"branches":[ {"when": <expr>, "steps":[...]},
            #                                     {"otherwise":true, "steps":[...]}? ]}}
            branches = st.get("args", {}).get("branches", [])
            # Only support single when + optional otherwise for now
            when_branch = next((b for b in branches if "when" in b), None)
            otherwise_branch = next((b for b in branches if b.get("otherwise")), None)

            if when_branch is None:
                # Nothing to choose → no-op
                i += 1
                continue

            # 1) predicate
            out += _emit_expr(when_branch["when"])

            # 2) jump to else if predicate is False (we'll patch target after then-steps are emitted)
            jmp_index = len(out)
            out.append(("JMP_IF_FALSE", -1))  # placeholder

            # 3) then steps
            _emit_steps(when_branch.get("steps", []), out)

            # 4) patch jump to point to start of else (or to fallthrough if no else)
            else_target = len(out)
            out[jmp_index] = ("JMP_IF_FALSE", else_target)

            # 5) else steps (if present)
            if otherwise_branch:
                _emit_steps(otherwise_branch.get("steps", []), out)

            i += 1
            continue

        # Unknown verb → record it so authors can see it
        out.append(("PUSH_CONST", f"[uncompiled verb: {verb}]"))
        out.append(("SHOW", None))
        i += 1

def compile_module_to_code(module_ast: Dict[str, Any]) -> List[Instruction]:
    """
    Input: one module AST dict with "flow": [Steps...]
    Output: VM instruction list (List[Tuple[op, arg]])
    """
    out: List[Instruction] = []
    _emit_steps(module_ast.get("flow", []), out)
    return out
