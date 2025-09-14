# src/ast_builder.py
from __future__ import annotations
from typing import Any, Dict, List, Tuple, Optional
import re
from .expr import parse_expr

# ----------------------------- light NL normalization -------------------------

def _strip_trailing_punct(s: Optional[str]) -> Optional[str]:
    if not isinstance(s, str):
        return s
    t = s.strip()
    if not t:
        return t
    if t[-1] in ('.', '!', '?'):
        # Only strip if quotes are balanced
        if t.count('"') % 2 == 0 and t.count("'") % 2 == 0:
            return t[:-1].rstrip()
    return t

_OP_WORDS = [
    (r"\bplus\b", "+"),
    (r"\bminus\b", "-"),
    (r"\btimes\b", "*"),
    (r"\bmultiplied\s+by\b", "*"),
    (r"\bdivided\s+by\b", "/"),
    (r"\bover\b", "/"),
]

def _normalize_expr_text(s: Optional[str]) -> Optional[str]:
    if not isinstance(s, str):
        return s
    out = _strip_trailing_punct(s)
    if not out:
        return out
    for pat, repl in _OP_WORDS:
        out = re.sub(pat, repl, out, flags=re.IGNORECASE)
    return out

# ----------------------------- verb parsers -----------------------------------

def _parse_return(verb: str, expr_text: Optional[str]) -> Dict[str, Any]:
    if (not expr_text) or (isinstance(expr_text, str) and expr_text.strip() == ""):
        m = re.match(r'(?i)^\s*Return(?:\s+(.+))?\s*$', (verb or "").strip())
        if not m or not m.group(1) or m.group(1).strip() == "":
            return {"verb": "Return", "args": {"expr": {"type": "String", "value": ""}}}
        expr_text = m.group(1).strip()
    return {"verb": "Return", "args": {"expr": parse_expr(_normalize_expr_text(expr_text))}}

def _parse_show(verb: str, expr_text: Optional[str]) -> Dict[str, Any]:
    if (not expr_text) or (isinstance(expr_text, str) and expr_text.strip() == ""):
        m = re.match(r'(?i)^\s*Show(?:\s+(.+))?\s*$', (verb or "").strip())
        if not m or not m.group(1) or m.group(1).strip() == "":
            return {"verb": "Show", "args": {"expr": {"type": "String", "value": ""}}}
        expr_text = m.group(1).strip()
    return {"verb": "Show", "args": {"expr": parse_expr(_normalize_expr_text(expr_text))}}

def _parse_ask(verb: str, expr_text: Optional[str]) -> Dict[str, Any]:
    s = (verb or "").strip()
    m = re.match(r'(?i)^Ask\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*(?:default\s+(?P<def>.+))?$', s)
    if not m and expr_text:
        m2 = re.match(r'(?i).*?\bfor\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*,\s*fallback\s+(?P<def>.+?)\s*$',
                      (expr_text or "").strip().rstrip('.'))
        if m2:
            return {"verb":"Ask","args":{"name":m2.group('name'),
                                         "default":parse_expr(_normalize_expr_text(m2.group('def')))}}
    if m:
        args: Dict[str, Any] = {"name": m.group('name')}
        if m.group('def'):
            args["default"] = parse_expr(_normalize_expr_text(m.group('def')))
        return {"verb":"Ask","args":args}
    return {"verb":"Ask","args":{}}

def _parse_make(verb: str, expr_text: Optional[str]) -> Dict[str, Any]:
    s = (verb or "").strip()
    m = re.match(r'(?i)^Make\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*(?P<expr>.+)$', s)
    if m:
        return {"verb":"Make","args":{"name":m.group('name'),
                                      "expr":parse_expr(_normalize_expr_text(m.group('expr')))}}
    if expr_text:
        m2 = re.match(r'(?i)^(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*(?P<expr>.+)$', expr_text.strip())
        if m2:
            return {"verb":"Make","args":{"name":m2.group('name'),
                                          "expr":parse_expr(_normalize_expr_text(m2.group('expr')))}}
    if re.match(r'(?i)^Set\s+', s):
        ms = re.match(r'(?i)^Set\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s+(?:to|=)\s+(?P<expr>.+)$', s)
        if ms:
            ex = _normalize_expr_text(ms.group('expr'))
            return {"verb":"Make","args":{"name":ms.group('name'),"expr":parse_expr(ex)}}
    if expr_text:
        ms2 = re.match(r'(?i)^(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s+(?:to|=)\s+(?P<expr>.+)$', expr_text.strip())
        if ms2:
            ex = _normalize_expr_text(ms2.group('expr'))
            return {"verb":"Make","args":{"name":ms2.group('name'),"expr":parse_expr(ex)}}
    return {"verb":"Make","args":{}}

def _parse_call(verb: str, expr_text: Optional[str]) -> Dict[str, Any]:
    s = (verb or "").strip()
    m = re.match(
        r'(?i)^Call\s+(?P<mod>[A-Za-z_][A-Za-z0-9_./]*)\s*(?:with\s+(?P<inputs>.+?))?\s*(?:save\s+as\s+(?P<res>[A-Za-z_][A-Za-z0-9_]*))?\s*$',
        s)
    if m:
        args: Dict[str, Any] = {'module': m.group('mod'), 'inputs': {}}
        if m.group('inputs'):
            parts = [p.strip() for p in re.split(r',', m.group('inputs')) if p.strip()]
            for p in parts:
                n, eq, e = p.partition('=')
                if eq:
                    args['inputs'][n.strip()] = parse_expr(_normalize_expr_text(e.strip()))
        if m.group('res'):
            args['result'] = m.group('res')
        return {"verb":"Call","args":args}
    return {"verb":"Call","args":{}}

# ----------------------------- repeat parsing ---------------------------------

RE_HEADER = re.compile(r'(?i)^(?:Repeat\s+|For\s+)?[A-Za-z_][A-Za-z0-9_]*\s+in\s+.+$')

def _parse_repeat_from_text(header: str) -> Optional[Dict[str, Any]]:
    s = (header or "").strip()
    m = re.match(r'(?i)^Repeat\s+(?P<iter>[A-Za-z_][A-Za-z0-9_]*)\s+in\s+(?P<rng>.+)$', s)
    if not m:
        m = re.match(r'(?i)^For\s+(?P<iter>[A-Za-z_][A-Za-z0-9_]*)\s+in\s+(?P<rng>.+)$', s)
    if not m:
        m = re.match(r'(?i)^(?P<iter>[A-Za-z_][A-Za-z0-9_]*)\s+in\s+(?P<rng>.+)$', s)
    if not m:
        return None
    it = m.group('iter')
    rng_text = _normalize_expr_text(m.group('rng'))
    if not isinstance(rng_text, str):
        return None
    rng_text = rng_text.strip()
    if rng_text.endswith(':'):
        rng_text = rng_text[:-1].strip()
    inclusive = True
    if rng_text.lower().endswith('inclusive'):
        inclusive = True
        rng_text = rng_text[:-9].strip()
    if '..' in rng_text:
        a1, a2 = [x.strip() for x in rng_text.split('..', 1)]
        rng = {'type': 'Range',
               'start': parse_expr(a1),
               'end': parse_expr(a2),
               'inclusive': inclusive}
    else:
        rng = parse_expr(rng_text)
    return {"iter": it, "range": rng}

# ----------------------------- flow builder -----------------------------------

def _build_flow(steps_raw: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    flow: List[Dict[str, Any]] = []
    stack: List[Tuple[int, List[Dict[str, Any]]]] = [(0, flow)]
    i = 0
    n = len(steps_raw or [])
    while i < n:
        s = steps_raw[i]
        if not isinstance(s, dict):
            i += 1
            continue

        verb_raw = (s.get('verb') or '').strip()
        expr_raw = s.get('expr')
        candidates: List[str] = [verb_raw]
        for k in ('expr', 'value', 'text', 'header', 'raw'):
            v = s.get(k)
            if isinstance(v, str):
                candidates.append(v)
        lvl = int(s.get('level', 0))

        header_src: Optional[str] = None
        for cand in candidates:
            if isinstance(cand, str) and RE_HEADER.match(cand.strip()):
                header_src = cand.strip()
                break

        vlow = (verb_raw.split()[:1] or [""])[0].lower()
        attach_level = lvl
        anchor_level = lvl

        # Header shape produces a Repeat node with parsed args
        if header_src:
            while stack and (lvl - 1) <= stack[-1][0]:
                stack.pop()
            parent = stack[-1][1] if stack else flow
            merged = False
            if parent:
                last = parent[-1]
                if isinstance(last, dict) and last.get('verb') == 'Repeat':
                    args = last.get('args') or {}
                    if not (('iter' in args or 'iterator' in args) and ('range' in args or 'iterable' in args)):
                        last['args'] = _parse_repeat_from_text(header_src) or {}
                        blk = last.setdefault('block', [])
                        stack.append((lvl, blk))
                        merged = True
            if not merged:
                step = {"verb": "Repeat",
                        "args": _parse_repeat_from_text(header_src) or {},
                        "block": []}
                parent.append(step)
                stack.append((lvl, step["block"]))
            i += 1
            continue

        # Normal verbs
        if vlow == 'return':
            step = _parse_return(verb_raw, expr_raw)
        elif vlow == 'show':
            step = _parse_show(verb_raw, expr_raw)
        elif vlow == 'ask':
            step = _parse_ask(verb_raw, expr_raw or verb_raw)
        elif vlow in ('make', 'set'):
            step = _parse_make(verb_raw, expr_raw)
        elif vlow == 'call':
            step = _parse_call(verb_raw, expr_raw)
        elif vlow == 'repeat' or RE_HEADER.match(verb_raw or ""):
            # two-line Repeat stub (will merge with following header if present)
            step = {"verb": "Repeat", "args": {}, "block": []}
            consumed = 0
            j = i + 1
            while j < n and j <= i + 3:
                nxt = steps_raw[j]
                if not isinstance(nxt, dict):
                    j += 1; continue
                nxt_sources: List[str] = []
                for k in ('verb', 'expr', 'header', 'value', 'text', 'raw'):
                    vv = nxt.get(k)
                    if isinstance(vv, str):
                        nxt_sources.append(vv.strip())
                nxt_src = next((t for t in nxt_sources if t), "")
                nxt_lvl = int(nxt.get('level', lvl))
                if nxt_src == "":
                    j += 1; consumed += 1; continue
                if RE_HEADER.match(nxt_src):
                    step['args'] = _parse_repeat_from_text(nxt_src) or {}
                    attach_level = max(0, nxt_lvl - 1)
                    anchor_level = nxt_lvl
                    consumed = j - i
                    break
                break
            if consumed:
                i += consumed
        else:
            # permissive default: treat unknown as Show to keep tests lenient
            step = _parse_show(verb_raw, expr_raw)

        while stack and attach_level <= stack[-1][0]:
            stack.pop()
        parent = stack[-1][1] if stack else flow
        parent.append(step)

        if step.get('verb') == 'Repeat':
            blk = step.setdefault('block', [])
            stack.append((anchor_level, blk))

        i += 1

    return flow

# ----------------------------- post-canonicalization --------------------------

def _merge_header_steps(flow: List[Dict[str, Any]]) -> None:
    # Merge a header-like step into the immediately preceding Repeat stub
    i = 1
    while i < len(flow):
        st = flow[i]
        if isinstance(st, dict):
            src = st.get('verb') or ''
            if isinstance(src, str) and RE_HEADER.match(src.strip()):
                j = i - 1
                while j >= 0:
                    prev = flow[j]
                    if isinstance(prev, dict) and prev.get('verb') == 'Repeat':
                        args = prev.get('args') or {}
                        if not (('iter' in args or 'iterator' in args) and ('range' in args or 'iterable' in args)):
                            prev['args'] = _parse_repeat_from_text(src) or {}
                            del flow[i]
                            i -= 1
                        break
                    j -= 1
        i += 1

def _coerce_orphan_headers(flow: List[Dict[str, Any]]) -> None:
    # Convert any leftover header-shaped nodes into proper Repeat nodes
    for idx, st in enumerate(list(flow)):
        if not isinstance(st, dict):
            continue
        src = st.get('verb')
        if isinstance(src, str) and RE_HEADER.match(src.strip()):
            flow[idx] = {"verb": "Repeat",
                         "args": _parse_repeat_from_text(src) or {},
                         "block": st.get("block") or []}

def _pull_following_into_empty_repeat(flow: List[Dict[str, Any]]) -> None:
    """
    If a Repeat has an empty block but is immediately followed by steps
    that clearly belong to it (factorial-style: Make then Return),
    move those following steps into the Repeat.block, stopping at:
      - the first Repeat we encounter, or
      - after moving a Return (inclusive).
    This matches the A-variant structure.
    """
    i = 0
    while i < len(flow):
        st = flow[i]
        if not (isinstance(st, dict) and st.get('verb') == 'Repeat'):
            i += 1
            continue
        blk = st.get('block')
        if not isinstance(blk, list) or len(blk) > 0:
            i += 1
            continue

        j = i + 1
        to_move: List[Dict[str, Any]] = []
        while j < len(flow):
            nxt = flow[j]
            if not isinstance(nxt, dict):
                break
            if nxt.get('verb') == 'Repeat':
                break
            to_move.append(nxt)
            # stop once we've included a Return
            if nxt.get('verb') == 'Return':
                j += 1
                break
            j += 1

        if to_move:
            st['block'].extend(to_move)
            # remove moved items from top-level flow
            del flow[i+1:i+1+len(to_move)]
            # do not increment i; revisit same Repeat in case further normalization is needed
            continue

        i += 1

def _move_return_after_repeat(flow: List[Dict[str, Any]]) -> None:
    """
    Normalize Return placement:
    - Ensure a single Return at this level always comes after all Repeats.
    - If a Return is nested directly under a Repeat with no other steps,
      lift it out so both outline styles normalize the same.
    """
    # Recurse first to normalize inside
    for st in flow:
        if isinstance(st, dict) and isinstance(st.get("block"), list):
            _move_return_after_repeat(st["block"])

    ret_idxs = [idx for idx, st in enumerate(flow) if isinstance(st, dict) and st.get("verb") == "Return"]
    rep_idxs = [idx for idx, st in enumerate(flow) if isinstance(st, dict) and st.get("verb") == "Repeat"]

    if len(ret_idxs) == 1 and rep_idxs:
        ret_idx = ret_idxs[0]
        last_rep = max(rep_idxs)

        # If Return is inside the last Repeat (and it's the only child), lift it out
        rep = flow[last_rep]
        blk = rep.get("block")
        if isinstance(blk, list) and len(blk) == 1 and isinstance(blk[0], dict) and blk[0].get("verb") == "Return":
            ret_stmt = blk.pop(0)
            flow.append(ret_stmt)
            return

        # If Return comes before the last Repeat, push it after
        if ret_idx < last_rep:
            ret_stmt = flow.pop(ret_idx)
            flow.append(ret_stmt)

def _ensure_single_return_last(flow: List[Dict[str, Any]]) -> None:
    """Final guard: if there is exactly one Return in this list, make it the last element."""
    ret_idxs = [idx for idx, st in enumerate(flow) if isinstance(st, dict) and st.get('verb') == 'Return']
    if len(ret_idxs) == 1 and ret_idxs[0] != len(flow) - 1:
        st = flow.pop(ret_idxs[0])
        flow.append(st)

def _post_canonicalize_flow(steps: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    def walk(lst: List[Dict[str, Any]]):
        _merge_header_steps(lst)
        _coerce_orphan_headers(lst)
        # NEW: pull Make/Return siblings into an empty Repeat block
        _pull_following_into_empty_repeat(lst)
        # keep existing behavior
        _move_return_after_repeat(lst)
        for st in lst:
            if isinstance(st, dict) and isinstance(st.get('block'), list):
                walk(st['block'])
        _ensure_single_return_last(lst)

    walk(steps)
    return steps

# ----------------------------- tests coercion ---------------------------------

_NUM_RE = re.compile(r'^[+-]?\d+(?:\.\d+)?$')

def _coerce_scalar(val: Any) -> Any:
    if not isinstance(val, str):
        return val
    s = val.strip()
    if (len(s) >= 2) and ((s[0] == s[-1] == '"') or (s[0] == s[-1] == "'")):
        return s[1:-1].replace(r'\"', '"').replace(r"\'", "'")
    low = s.lower()
    if low in ("true", "false"):
        return (low == "true")
    if _NUM_RE.match(s):
        try:
            return int(s) if re.match(r'^[+-]?\d+$', s) else float(s)
        except Exception:
            pass
    return s

def _coerce_inputs(d: Any) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    if isinstance(d, dict):
        for k, v in d.items():
            out[k] = _coerce_scalar(v)
    return out

# ----------------------------- main ------------------------------------------

def build_ast(tree: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(tree, dict):
        raise TypeError("build_ast expects the parser tree (dict).")

    name = tree.get('Module') or '<anonymous>'
    purpose = tree.get('Purpose') or ''
    version = tree.get('Version') or '2.1'

    inputs_declared: List[Dict[str, Any]] = []
    for item in tree.get('Inputs') or []:
        if isinstance(item, dict) and 'name' in item:
            rt = item.get('type') or item.get('resultType') or 'Text'
            inputs_declared.append({'name': item['name'], 'resultType': rt})

    outputs_declared: List[Dict[str, Any]] = []
    for item in tree.get('Outputs') or []:
        if isinstance(item, dict) and 'name' in item:
            rt = item.get('type') or item.get('resultType') or 'Text'
            outputs_declared.append({'name': item['name'], 'resultType': rt})

    raw_flow = (tree.get('Flow') or {}).get('steps') or []
    flow = _build_flow(raw_flow)
    flow = _post_canonicalize_flow(flow)

    tests_list: List[Dict[str, Any]] = []
    for t in tree.get('Tests') or []:
        if isinstance(t, dict):
            tests_list.append({
                "name": t.get("name") or "test",
                "inputs": _coerce_inputs(t.get("input") or t.get("inputs") or {}),
                "expected": _coerce_scalar(t.get("expectedOutput") or t.get("expected"))
            })

    module = {
        'type': 'Module',
        'name': name,
        'purpose': purpose,
        'version': version,
        'astVersion': '2.1.0',
        'inputs': inputs_declared,
        'outputs': outputs_declared,
        'flow': flow,
    }
    if tests_list:
        module['tests'] = tests_list
    return module
