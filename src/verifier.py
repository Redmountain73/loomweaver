# src/verifier.py
# Loom-native static verifier (schema-free).
# Goals:
# - Catch obvious type/flow issues early, with Loom-fluent messages.
# - Never block authoring on ambiguous cases: unknowns become warnings, not errors.

from __future__ import annotations
from typing import Any, Dict, List, Tuple, Optional

# We only import RuntimeErrorLoom for raising combined failures when requested.
try:
    from .interpreter import RuntimeErrorLoom  # type: ignore
except Exception:
    class RuntimeErrorLoom(RuntimeError):  # fallback when running standalone
        pass


def _expr_type(e: Dict[str, Any]) -> str:
    """Very lightweight type inference: Boolean | Number | Text | Range | Unknown."""
    if not isinstance(e, dict):
        return "Unknown"
    t = e.get("type")
    if t in ("Boolean",):
        return "Boolean"
    if t in ("Number",):
        return "Number"
    if t in ("String",):
        return "Text"
    if t in ("Range",):
        return "Range"
    if t in ("Identifier",):
        return "Unknown"
    if t == "Unary":
        op = e.get("op")
        inner = _expr_type(e.get("expr"))
        if op == "not":
            return "Boolean"
        if op in ("+","-"):
            return "Number" if inner == "Number" else "Unknown"
        return "Unknown"
    if t == "Binary":
        op = e.get("op")
        if op in ("and","or"):
            return "Boolean"
        if op in ("<", "<=", ">", ">=", "==", "!="):
            return "Boolean"
        if op == "+":
            lt = _expr_type(e.get("left"))
            rt = _expr_type(e.get("right"))
            if "Text" in (lt, rt):
                return "Text"
            if lt == "Number" and rt == "Number":
                return "Number"
            return "Unknown"
        if op in ("-","*","/","%"):
            lt = _expr_type(e.get("left"))
            rt = _expr_type(e.get("right"))
            if lt == "Number" and rt == "Number":
                return "Number"
            return "Unknown"
        return "Unknown"
    return "Unknown"


def _collect_identifiers(e: Any, out: Optional[List[str]] = None) -> List[str]:
    if out is None:
        out = []
    if isinstance(e, dict):
        if e.get("type") == "Identifier":
            name = e.get("name")
            if isinstance(name, str):
                out.append(name)
        else:
            for k, v in e.items():
                _collect_identifiers(v, out)
    elif isinstance(e, list):
        for v in e:
            _collect_identifiers(v, out)
    return out


def _fmt_expr(e: Dict[str, Any]) -> str:
    """Tiny pretty-printer for error messages."""
    t = e.get("type")
    if t == "Identifier":
        return e.get("name", "<id>")
    if t in ("Number","String","Boolean"):
        return repr(e.get("value"))
    if t == "Unary":
        return f"({e.get('op')} {_fmt_expr(e.get('expr', {}))})"
    if t == "Binary":
        return f"({_fmt_expr(e.get('left', {}))} {e.get('op')} {_fmt_expr(e.get('right', {}))})"
    if t == "Range":
        inc = " .. " if e.get("inclusive") else " ..< "
        return f"[{_fmt_expr(e.get('start', {}))}{inc}{_fmt_expr(e.get('end', {}))}]"
    return str(e)


def verify_module(module: Dict[str, Any]) -> Dict[str, List[str]]:
    """
    Returns {'errors': [...], 'warnings': [...]} without raising.
    Rules:
      - Choose.when must be boolean (error if statically Number/Text/Range, warn if Unknown)
      - Repeat iterable Range should have numeric endpoints when literals (error otherwise)
      - 'and'/'or' operands should be booleans (warn if Unknown)
      - Basic flow name tracking: warn if Identifier may be undefined
    """
    errs: List[str] = []
    warns: List[str] = []

    declared: set[str] = set()

    def note_declare(name: Optional[str]):
        if isinstance(name, str) and name:
            declared.add(name)

    def walk_steps(steps: List[Dict[str, Any]]):
        for i, st in enumerate(steps or []):
            verb = (st.get("verb") or "")
            args = st.get("args") or {}
            where = f"step {i+1} ({verb})"

            if verb == "Ask":
                note_declare(args.get("name"))

            elif verb == "Make":
                note_declare(args.get("name"))
                e = args.get("expr")
                for ident in _collect_identifiers(e):
                    if ident not in declared:
                        warns.append(f"{where}: identifier '{ident}' may be undefined")

            elif verb == "Return":
                e = args.get("expr")
                # Boolean op checks
                def check_boolean_ops(n: Any):
                    if not isinstance(n, dict):
                        return
                    if n.get("type") == "Binary" and n.get("op") in ("and","or"):
                        lt = _expr_type(n.get("left", {}))
                        rt = _expr_type(n.get("right", {}))
                        if lt not in ("Boolean","Unknown"):
                            warns.append(f"{where}: 'and/or' expects booleans (left is {lt})")
                        if rt not in ("Boolean","Unknown"):
                            warns.append(f"{where}: 'and/or' expects booleans (right is {rt})")
                    for v in n.values():
                        if isinstance(v, (dict, list)):
                            check_boolean_ops(v)
                check_boolean_ops(e)
                for ident in _collect_identifiers(e):
                    if ident not in declared:
                        warns.append(f"{where}: identifier '{ident}' may be undefined")

            elif verb == "Repeat":
                it = args.get("iterable")
                if isinstance(it, dict) and it.get("type") == "Range":
                    s = it.get("start", {})
                    e = it.get("end", {})
                    stype = _expr_type(s)
                    etype = _expr_type(e)
                    if stype in ("Text","Range") or etype in ("Text","Range"):
                        errs.append(f"{where}: Repeat range endpoints must be numeric (got {stype}, {etype})")
                # iterator variable
                itvar = args.get("iterator", {})
                if isinstance(itvar, dict) and itvar.get("type") == "Identifier":
                    note_declare(itvar.get("name"))
                # Nested
                for child in st.get("steps") or []:
                    pass
                walk_steps(st.get("steps") or [])

            elif verb == "Choose":
                branches = (args.get("branches") or []) if isinstance(args, dict) else []
                has_otherwise = False
                for b_idx, br in enumerate(branches):
                    if br.get("otherwise"):
                        has_otherwise = True
                        walk_steps(br.get("steps") or [])
                        continue
                    cond = br.get("when")
                    ctype = _expr_type(cond)
                    if ctype in ("Number","Text","Range"):
                        errs.append(f"{where}: 'when' must be boolean (got {ctype}) — expr={_fmt_expr(cond)}")
                    elif ctype == "Unknown":
                        warns.append(f"{where}: 'when' should be boolean (static type unknown) — expr={_fmt_expr(cond)}")
                    walk_steps(br.get("steps") or [])

            elif verb == "Call":
                res_name = args.get("result")
                if isinstance(res_name, str) and res_name:
                    note_declare(res_name)
                ins = args.get("inputs") or {}
                for k, v in ins.items():
                    if isinstance(v, dict):
                        for ident in _collect_identifiers(v):
                            if ident not in declared:
                                warns.append(f"{where}: call input '{k}' references '{ident}' which may be undefined")

            else:
                for ident in _collect_identifiers(args):
                    if ident not in declared:
                        warns.append(f"{where}: identifier '{ident}' may be undefined")

    walk_steps(module.get("flow", []))

    return {"errors": errs, "warnings": warns}


def verify_or_raise(module: Dict[str, Any]) -> None:
    res = verify_module(module)
    if res["errors"]:
        raise RuntimeErrorLoom("Static verification failed:\n- " + "\n- ".join(res["errors"]))
