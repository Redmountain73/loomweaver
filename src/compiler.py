# src/compiler.py
from __future__ import annotations
from typing import Any, Dict, List, Tuple, Optional
from .tokenizer import tokenize
from .parser import parse
from .ast_builder import build_ast
from .vm import VM

Instr = Tuple[str, Any]
class CompileError(Exception): ...

def _expr_to_text(node: Any) -> str:
    if isinstance(node, dict):
        t = node.get("type")
        if t == "Boolean":
            return "true" if bool(node.get("value")) else "false"
        if t == "Number":
            return str(node.get("value"))
        if t == "String":
            v = node.get("value")
            return repr(v) if v is not None else '""'
        if t == "Identifier":
            return str(node.get("name") or "")
        return t or ""
    if isinstance(node, bool): return "true" if node else "false"
    if isinstance(node, (int, float)): return str(node)
    if isinstance(node, str): return repr(node)
    return ""

def compile_expr(node: Any, code: List[Instr]) -> None:
    if node is None:
        code.append(("PUSH_CONST", None)); return
    if isinstance(node, (int, float, bool, str)):
        code.append(("PUSH_CONST", node)); return
    if not isinstance(node, dict):
        code.append(("PUSH_CONST", node)); return

    t = node.get("type")
    if t in ("Number", "String", "Boolean"):
        code.append(("PUSH_CONST", node.get("value"))); return
    if t == "Identifier":
        code.append(("LOAD", node.get("name"))); return
    if t == "Unary":
        op = node.get("op")
        compile_expr(node.get("expr"), code)
        if op == "-": code.append(("NEG", None)); return
        if op == "+": return
        if op == "not": code.append(("NOT", None)); return
        raise CompileError(f"unknown unary op: {op}")
    if t == "Binary":
        op = node.get("op")
        compile_expr(node.get("left"), code)
        compile_expr(node.get("right"), code)
        if op == "+": code.append(("ADD", None)); return
        if op == "-": code.append(("SUB", None)); return
        if op == "*": code.append(("MUL", None)); return
        if op == "/": code.append(("DIV", None)); return
        if op == "==": code.append(("EQ", None)); return
        if op == "!=": code.append(("NE", None)); return
        if op == "<": code.append(("LT", None)); return
        if op == "<=": code.append(("LE", None)); return
        if op == ">": code.append(("GT", None)); return
        if op == ">=": code.append(("GE", None)); return
        raise CompileError(f"unknown binary op: {op}")
    if t == "Range":
        compile_expr(node.get("start"), code)
        compile_expr(node.get("end"), code)
        code.append(("BUILD_RANGE", bool(node.get("inclusive", True))))  # DEFAULT INCLUSIVE
        return
    raise CompileError(f"unknown expression type: {t}")

def compile_flow(steps: List[Dict[str, Any]], code: List[Instr]) -> None:
    for st in steps or []:
        verb = st.get("verb")
        args = st.get("args", {}) or {}

        if verb == "Make":
            name = args.get("name") or args.get("var") or args.get("identifier")
            if not name: raise CompileError("Make requires a name")
            expr = args.get("expr") or args.get("value") or args.get("to")
            compile_expr(expr, code)
            code.append(("STORE", name))
            continue

        if verb == "Show":
            expr = args.get("expr") or args.get("text") or args.get("value")
            compile_expr(expr, code)
            code.append(("SHOW", None))
            continue

        if verb == "Ask":
            name = args.get("name")
            default_expr = args.get("default")
            dv = None
            if isinstance(default_expr, dict) and default_expr.get("type") in ("Number", "String", "Boolean"):
                dv = default_expr.get("value")
            code.append(("ASK_DEFAULT", (name, dv)))
            continue

        if verb == "Return":
            expr = args.get("expr") or args.get("value")
            compile_expr(expr, code)
            code.append(("RETURN", None))
            return

        if verb == "Check":
            continue  # no-op in VM pilot

        if verb == "Choose":
            branches = args.get("branches", []) or []
            end_jumps: List[int] = []
            false_patch: Optional[int] = None
            br_idx = 0
            for br in branches:
                if br.get("otherwise"):
                    if false_patch is not None:
                        code[false_patch] = ("JMP_IF_FALSE", len(code)); false_patch = None
                    body = br.get("steps") or br.get("block") or br.get("body") or []
                    if isinstance(body, dict): body = body.get("steps") or []
                    for b in body: compile_flow([b], code)
                    code.append(("CHOOSE_OTHERWISE", br_idx))
                    end_jumps.append(len(code)); code.append(("JMP", None))
                    br_idx += 1
                    break
                else:
                    when_expr = br.get("when")
                    compile_expr(when_expr, code)
                    code.append(("CHOOSE_TRACE", _expr_to_text(when_expr)))
                    fp = len(code); code.append(("JMP_IF_FALSE", None))
                    body = br.get("steps") or br.get("block") or br.get("body") or []
                    if isinstance(body, dict): body = body.get("steps") or []
                    for b in body: compile_flow([b], code)
                    code.append(("CHOOSE_SELECT", br_idx))
                    end_jumps.append(len(code)); code.append(("JMP", None))
                    if false_patch is not None:
                        code[false_patch] = ("JMP_IF_FALSE", len(code))
                    false_patch = fp
                    br_idx += 1
            if false_patch is not None:
                code[false_patch] = ("JMP_IF_FALSE", len(code))
            end_target = len(code)
            for idx in end_jumps: code[idx] = ("JMP", end_target)
            continue

        if verb == "Repeat":
            iterator_node = args.get("iterator")
            iter_name = None
            if isinstance(iterator_node, dict) and "name" in iterator_node:
                iter_name = iterator_node["name"]
            elif isinstance(iterator_node, str):
                iter_name = iterator_node
            iter_name = iter_name or args.get("iter")

            iterable_expr = args.get("iterable")
            if iterable_expr is None and "range" in args:
                iterable_expr = args.get("range")
            if not iter_name or iterable_expr is None:
                raise CompileError("Repeat requires iterator name and iterable expression")

            if isinstance(iterable_expr, dict) and iterable_expr.get("type") == "Range":
                compile_expr(iterable_expr.get("start"), code)
                compile_expr(iterable_expr.get("end"), code)
                code.append(("BUILD_RANGE", bool(iterable_expr.get("inclusive", True))))  # DEFAULT INCLUSIVE
            else:
                compile_expr(iterable_expr, code)

            it_state = f"it_{iter_name}"
            code.append(("ITER_PUSH", it_state))
            loop_start = len(code)
            code.append(("ITER_NEXT", it_state))
            jmp_end_idx = len(code); code.append(("JMP_IF_FALSE", None))
            code.append(("STORE", iter_name))

            body_steps = st.get("steps")
            if not isinstance(body_steps, list):
                blk = st.get("block") or st.get("body")
                if isinstance(blk, list): body_steps = blk
                elif isinstance(blk, dict): body_steps = blk.get("steps") or []
                else: body_steps = []
            compile_flow(body_steps, code)

            code.append(("JMP", loop_start))
            end_target = len(code)
            code[jmp_end_idx] = ("JMP_IF_FALSE", end_target)
            continue

        raise CompileError(f"verb not supported by VM pilot: {verb}")

def compile_loom_text_to_bytecode(text: str) -> Tuple[List[Instr], str]:
    tokens = tokenize(text)
    tree = parse(tokens)
    module = build_ast(tree)
    steps = module.get("flow") or []
    code: List[Instr] = []
    compile_flow(steps, code)
    return code, (module.get("name") or "<anonymous>")

def run_loom_text_with_vm(text: str, inputs: Optional[Dict[str, Any]] = None) -> Tuple[Any, Dict[str, Any]]:
    code, name = compile_loom_text_to_bytecode(text)
    vm = VM(module_name=name)
    result = vm.run(code, inputs or {})
    return result, vm.receipt
