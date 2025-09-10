# src/parser.py
# Parses tokenizer tokens into a pre-AST with sections and hierarchical Flow.
# Expects tokens shaped like:
# {"type": "SECTION"|"VALUE"|"IDENTIFIER"|"RESULTTYPE"|"VERB"|"EXPR"|"KEY", "value": str, "nesting": int}

# --- Phase 3 / Step 2: conditional grouping import (safe if unused) ----------
try:
    # package-relative (normal)
    from .tokenizer import detect_conditional_markers
except Exception:
    # script-relative (python src/parser.py)
    try:
        from tokenizer import detect_conditional_markers  # type: ignore
    except Exception:
        # last resort stub (keeps parser working if helper absent)
        def detect_conditional_markers(line: str):
            return {"is_conditional": False, "head": None, "has_then": False, "normalized": line or ""}

import re as _re

# trim trailing punctuation like ".", "!", ";"
_DEF_TRAIL_PUNCT = _re.compile(r"[.;!]+$")

# courtesy/polite prefixes we allow before heads (must match tokenizer's set)
_COURTESY_WORDS = r"(?:please|kindly|go ahead and|would you|could you)"

# --- Section normalization ----------------------------------------------------
_SECTION_KEYWORDS = ("Module", "Purpose", "Inputs", "Outputs", "Flow", "Tests", "Version")
_PREFIX_RE = _re.compile(r"^(?:[IVXLCDM]+\.|[A-Z]\.|[0-9]+\.)(?:\s+|$)", _re.IGNORECASE)

def _normalize_section(raw: str) -> tuple[str, str|None]:
    """
    Be robust to outlines like 'I. Module: Name', 'A. Purpose: ...', '1. Flow', etc.
    Returns (SectionName, inline_value_or_None)
    """
    s = (raw or "").strip()
    before, sep, after = s.partition(":")
    name_part = _PREFIX_RE.sub("", before.strip())  # drop 'I.' / 'A.' / '1.' prefixes
    # find the first known section keyword inside name_part
    found = None
    for key in _SECTION_KEYWORDS:
        if _re.search(rf"\b{key}\b", name_part, flags=_re.IGNORECASE):
            found = key
            break
    section = found or name_part.title()
    inline_val = after.strip() if sep else None
    return section, inline_val

# --- Conditional helpers ------------------------------------------------------
def _split_then(text: str) -> tuple[str, str]:
    """Return (cond, then_rest) split on the first 'then' (case-insensitive)."""
    if not isinstance(text, str):
        return "", ""
    s = _DEF_TRAIL_PUNCT.sub("", text).strip()
    m = _re.search(r"\bthen\b", s, flags=_re.IGNORECASE)
    if not m:
        return "", ""
    return s[:m.start()].strip(), s[m.end():].strip()

def _extract_when_expr(line: str) -> tuple[str|None, str|None, str|None]:
    """
    From a line like 'if n == 0 then return 1', returns ('if', 'n == 0', 'return 1').
    Returns (None, None, None) if not a recognizable conditional head.
    """
    info = detect_conditional_markers(line or "")
    if not info.get("is_conditional"):
        return None, None, None

    head = (info.get("head") or "").lower() if info.get("head") else None
    norm = info.get("normalized") or ""
    if head == "otherwise":
        # Standalone 'otherwise' is handled when we implement full chains (later step)
        return "otherwise", None, None

    # peel the leading courtesy + head word, capture the rest
    m = _re.match(
        rf"^\s*(?:{_COURTESY_WORDS}\s+)?(if|when|unless)\b(.*)$",
        norm,
        flags=_re.IGNORECASE,
    )
    if not m:
        return None, None, None

    rest = (m.group(2) or "").strip()
    cond, then_rest = _split_then(rest)
    if not cond:
        # not a proper head-with-then; we ignore in Step 2 (non-breaking)
        return None, None, None
    return head, cond.strip(), (then_rest or None)

# --- Phase 3: Multiline Choose absorption helpers ----------------------------

# Only for trimming a trailing colon on headers like "when x:" / "else if y:"
_COLON_TRAIL = _re.compile(r"\s*:\s*$")

def _match_branch_header(line: str):
    """
    Recognize multiline branch headers (case-insensitive):

      when <expr>[:]
      if <expr>[:]
      else if <expr>[:] | otherwise if <expr>[:] | elif <expr>[:]
      otherwise[:] | else[:]
      unless <expr>[:]

    Returns:
      ("when", "<expr>") | ("unless", "<expr>") | ("otherwise", None) | (None, None)
    """
    if not isinstance(line, str) or not line.strip():
        return None, None
    s = _COLON_TRAIL.sub("", line.strip())

    # otherwise / else (no expression)
    if _re.match(r"^(?:otherwise|else)\s*$", s, flags=_re.IGNORECASE):
        return "otherwise", None

    # else-if family
    m = _re.match(r"^(?:else\s+if|otherwise\s+if|elif)\s+(?P<cond>.+)$", s, flags=_re.IGNORECASE)
    if m:
        return "when", (m.group("cond") or "").strip()

    # when / if
    m = _re.match(r"^(?:when|if)\s+(?P<cond>.+)$", s, flags=_re.IGNORECASE)
    if m:
        return "when", (m.group("cond") or "").strip()

    # unless
    m = _re.match(r"^(?:unless)\s+(?P<cond>.+)$", s, flags=_re.IGNORECASE)
    if m:
        return "unless", (m.group("cond") or "").strip()

    return None, None


def _absorb_multiline_choose(choose_node: dict) -> dict:
    """
    For a block 'Choose' node, absorb branch headers and their indented bodies into:
      choose_node['branches'] = [ {head, when, body:{steps:[...]}} ... ]
      choose_node['otherwise'] = {'steps':[...]}  # optional
    and clear choose_node['body']['steps'] to avoid double-processing.
    """
    if not isinstance(choose_node, dict):
        return choose_node
    if (choose_node.get("verb") or "").lower() != "choose":
        return choose_node
    if not choose_node.get("is_block"):
        return choose_node

    base_level = int(choose_node.get("level", 0))
    body = choose_node.get("body") or {}
    steps = list(body.get("steps") or [])
    if not steps:
        return choose_node

    branches = []
    otherwise = None
    i, n = 0, len(steps)

    while i < n:
        s = steps[i]
        if not isinstance(s, dict):
            i += 1
            continue

        lvl = int(s.get("level", 0))
        # Only consider headers exactly one indent deeper than Choose
        if lvl != base_level + 1:
            i += 1
            continue

        kind, cond = _match_branch_header(s.get("verb"))
        if kind is None:
            i += 1
            continue

        # Collect branch body: all following steps with deeper indentation
        j = i + 1
        body_steps = []
        while j < n:
            sj = steps[j]
            if not isinstance(sj, dict):
                break
            lj = int(sj.get("level", 0))
            if lj <= lvl:
                break
            body_steps.append(sj)
            j += 1

        if kind == "otherwise":
            otherwise = {"steps": body_steps}
        else:
            branches.append({
                "head": kind,               # 'when' | 'unless'
                "when": (cond or ""),       # string; builder will parse to Expr
                "body": {"steps": body_steps},
            })
        i = j

    if branches or otherwise is not None:
        out = {**choose_node}
        out["branches"] = branches
        if otherwise is not None:
            out["otherwise"] = otherwise
        # clear raw body steps so we don't execute duplicated children
        out["body"] = {"steps": []}
        return out

    return choose_node
# --- end multiline Choose helpers --------------------------------------------

# --- Phase 3: Multiline Choose absorption helpers ----------------------------

import re as _re  # parser already uses regex; local alias is fine

# Trim optional trailing ":" on headers like "when x:".
_COLON_TRAIL = _re.compile(r"\s*:\s*$")

def _match_branch_header(line: str):
    """
    Recognize multiline branch headers (case-insensitive):

      when <expr>[:]
      if <expr>[:]
      else if <expr>[:] | otherwise if <expr>[:] | elif <expr>[:]
      otherwise[:] | else[:]
      unless <expr>[:]

    Returns:
      ("when", "<expr>") | ("unless", "<expr>") | ("otherwise", None) | (None, None)
    """
    if not isinstance(line, str) or not line.strip():
        return None, None
    s = _COLON_TRAIL.sub("", line.strip())

    # otherwise / else (no expression)
    if _re.match(r"^(?:otherwise|else)\s*$", s, flags=_re.IGNORECASE):
        return "otherwise", None

    # else-if family
    m = _re.match(r"^(?:else\s+if|otherwise\s+if|elif)\s+(?P<cond>.+)$", s, flags=_re.IGNORECASE)
    if m:
        return "when", (m.group("cond") or "").strip()

    # when / if
    m = _re.match(r"^(?:when|if)\s+(?P<cond>.+)$", s, flags=_re.IGNORECASE)
    if m:
        return "when", (m.group("cond") or "").strip()

    # unless
    m = _re.match(r"^(?:unless)\s+(?P<cond>.+)$", s, flags=_re.IGNORECASE)
    if m:
        return "unless", (m.group("cond") or "").strip()

    return None, None


def _absorb_multiline_choose(choose_node: dict) -> dict:
    """
    For a block 'Choose' node, absorb branch headers and their indented bodies into:
      choose_node['branches'] = [ {head, when, body:{steps:[...]}} ... ]
      choose_node['otherwise'] = {'steps':[...]}  # optional
    and clear choose_node['body']['steps'] to avoid double-processing.
    """
    if not isinstance(choose_node, dict):
        return choose_node
    if (choose_node.get("verb") or "").lower() != "choose":
        return choose_node
    if not choose_node.get("is_block"):
        return choose_node

    base_level = int(choose_node.get("level", 0))
    body = choose_node.get("body") or {}
    steps = list(body.get("steps") or [])
    if not steps:
        return choose_node

    branches = []
    otherwise = None
    i, n = 0, len(steps)

    while i < n:
        s = steps[i]
        if not isinstance(s, dict):
            i += 1
            continue

        lvl = int(s.get("level", 0))
        # Only consider headers exactly one indent deeper than Choose
        if lvl != base_level + 1:
            i += 1
            continue

        kind, cond = _match_branch_header(s.get("verb"))
        if kind is None:
            i += 1
            continue

        # Collect branch body: all following steps with deeper indentation
        j = i + 1
        body_steps = []
        while j < n:
            sj = steps[j]
            if not isinstance(sj, dict):
                break
            lj = int(sj.get("level", 0))
            if lj <= lvl:
                break
            body_steps.append(sj)
            j += 1

        if kind == "otherwise":
            otherwise = {"steps": body_steps}
        else:
            branches.append({
                "head": kind,               # 'when' | 'unless'
                "when": (cond or ""),       # string; builder will parse to Expr
                "body": {"steps": body_steps},
            })
        i = j

    if branches or otherwise is not None:
        out = {**choose_node}
        out["branches"] = branches
        if otherwise is not None:
            out["otherwise"] = otherwise
        # clear raw body steps so we don't execute duplicated children
        out["body"] = {"steps": []}
        return out

    return choose_node
# --- end multiline Choose helpers --------------------------------------------


def _make_inline_step(text: str, level: int) -> dict:
    """Create a parser-level step from an inline 'then' action (keeps NL for builder)."""
    return {
        "verb": (text or "").strip(),  # AST builder will interpret NL here
        "expr": "",
        "level": level,
        "is_block": False,
    }

def _group_conditionals_in_steps(steps: list[dict]) -> list[dict]:
    """
    Non-breaking transformation:
      - Detects inline conditionals like: 'if X then <inline action>'
      - Chains same-level 'else if Y then <action>' and 'otherwise <action>'
      - Emits a parser-level Choose node:

        {
          'verb': 'Choose',
          'branches': [
            {'head':'if'|'when'|'unless', 'when':'X', 'body':{'steps':[ ... ]}},
            {'head':'when', 'when':'Y', 'body':{'steps':[ ... ]}}
          ],
          'otherwise': {'steps':[ ... ]},   # optional
          'is_block': True
        }

    Only triggers when 'then' bodies are inline. Multiline branch bodies are deferred.
    Existing steps without conditionals are returned unchanged.
    """
    out: list[dict] = []
    i = 0
    n = len(steps or [])

    while i < n:
        s = steps[i]

        # Recurse into real block children first (Repeat/Try/Choose etc.)
        if isinstance(s, dict) and s.get("is_block") and isinstance(s.get("body"), dict):
            s = {**s}
            s_body = s.get("body") or {}
            s_body_steps = s_body.get("steps") or []
            s_body["steps"] = _group_conditionals_in_steps(s_body_steps)
            s["body"] = s_body

        # Absorb multiline Choose branches (Phase 3)
        if (s.get("verb") or "").lower() == "choose":
            s = _absorb_multiline_choose(s)


        line = s.get("verb") if isinstance(s, dict) else None
        if isinstance(line, str):
            head, cond, then_rest = _extract_when_expr(line)
            if head in ("if", "when", "unless") and cond:
                base_level = int(s.get("level", 0))
                branch_steps = []
                if then_rest:
                    branch_steps.append(_make_inline_step(then_rest, base_level + 1))

                choose_node = {
                    "verb": "Choose",
                    "branches": [
                        {
                            "head": head,          # 'if' | 'when' | 'unless' (builder uses 'unless' for sugar)
                            "when": cond,
                            "body": {"steps": branch_steps},
                        }
                    ],
                    "level": base_level,
                    "is_block": True,
                    "body": {"steps": []},      # kept for consistency with other block nodes
                }

                # --- Absorb same-level 'else if' and 'otherwise' (inline) -----------------------
                j = i + 1
                while j < n:
                    sj = steps[j]
                    if not isinstance(sj, dict):
                        break
                    if int(sj.get("level", -1)) != base_level:
                        break

                    line_j = sj.get("verb")
                    if not isinstance(line_j, str):
                        break

                    # Try generic extractor first
                    h2, cond2, then2 = _extract_when_expr(line_j)

                    # If extractor says 'otherwise', see if it's actually "else if ..." / "otherwise if ..."
                    if h2 == "otherwise" and (cond2 is None):
                        txt = _DEF_TRAIL_PUNCT.sub("", (line_j or "").strip())
                        m_elseif = _re.match(
                            r"^\s*(?:else\s+if|otherwise\s+if)\s+(?P<cond>.+?)(?:\s+then\s+(?P<body>.+))?\s*$",
                            txt, flags=_re.IGNORECASE,
                        )
                        if m_elseif:
                            h2 = "when"  # treat chained else-if as another conditional branch
                            cond2 = (m_elseif.group("cond") or "").strip()
                            then2 = (m_elseif.group("body") or "").strip() or None

                    # Chain another conditional branch
                    if h2 in ("if", "when", "unless") and cond2:
                        branch2_steps = []
                        if then2:
                            branch2_steps.append(_make_inline_step(then2, base_level + 1))
                        choose_node["branches"].append({
                            "head": h2,
                            "when": cond2,
                            "body": {"steps": branch2_steps},
                        })
                        j += 1
                        continue

                    # Otherwise branch (inline)
                    if h2 == "otherwise":
                        other_steps = []
                        # For 'otherwise <inline action>' we treat the remainder as the action
                        rest = _DEF_TRAIL_PUNCT.sub("", (line_j or "").strip())
                        # capture optional inline action after the head
                        m_other = _re.match(r"^\s*(?:otherwise|else)\b(?:\s+(?P<body>.+))?\s*$", rest, flags=_re.IGNORECASE)
                        if m_other and m_other.group("body"):
                            other_steps.append(_make_inline_step(m_other.group("body"), base_level + 1))
                        choose_node["otherwise"] = {"steps": other_steps}
                        j += 1
                        # nothing should follow an 'otherwise' in the same chain
                        break

                    # Not part of this chain → stop absorbing
                    break

                out.append(choose_node)
                i = j
                continue

            # Standalone 'otherwise' without a preceding inline-if is ignored at this step
            # (will be handled when multiline branches are introduced)
            if head == "otherwise":
                pass

        out.append(s)
        i += 1

    return out

BLOCK_VERBS = {"repeat", "try", "choose"}

# --- Normalize clause & body nesting for Choose/Repeat (indent-agnostic) ----
def _normalize_clause_nesting(tokens: list[dict]) -> list[dict]:
    """
    Parser-side pre-pass (indentation-agnostic):
    - Inside D. Flow, after a 'Choose' line, promote clause headers
      'when …:' / 'else if …:' / 'otherwise:'  to type='VERB' at (choose_level + 1),
      and lift their bodies to (choose_level + 2).
    - Inside 'Repeat …:', FUSE the header to a single VERB:
         VERB 'Repeat' + EXPR 'for i in 1..3:'  →  VERB 'Repeat for i in 1..3:'
      and lift body lines to (repeat_level + 1).
    This uses outline numbers/letters for structure; whitespace is ignored.
    """
    import re as _re

    def is_clause_header(s: str) -> bool:
        s = (s or "").strip().lower()
        return bool(
            _re.match(r"^when\s+.+:\s*$", s)
            or _re.match(r"^else\s+if\s+.+:\s*$", s)
            or _re.match(r"^otherwise:\s*$", s)
        )

    def is_repeat_for(s: str) -> bool:
        return bool(_re.match(r"^\s*for\s+.+:\s*$", (s or "")))

    FLOW = False
    choose_level: int | None = None
    repeat_level: int | None = None
    expect_repeat_for: bool = False  # fuse flag (seen VERB 'Repeat', waiting EXPR 'for …:')

    out: list[dict] = []
    prev: dict | None = None

    body_verbs = {"show", "make", "ask", "return", "check", "remember", "forget", "call", "try", "choose", "repeat"}

    for tok in tokens:
        t = dict(tok)  # shallow copy
        ttype = t.get("type")
        val = (t.get("value") or "")
        low = val.strip().lower()
        nesting = int(t.get("nesting", 0))

        # Track sections
        if ttype == "SECTION":
            FLOW = (val.strip().lower() == "flow")
            choose_level = None
            repeat_level = None
            expect_repeat_for = False
            out.append(t); prev = t
            continue

        if not FLOW:
            out.append(t); prev = t
            continue

        # Detect Choose/Repeat start
        if ttype == "VERB" and low == "choose":
            choose_level = nesting
            repeat_level = None
            expect_repeat_for = False
            out.append(t); prev = t
            continue

        if ttype == "VERB" and low == "repeat":
            repeat_level = nesting
            choose_level = None
            expect_repeat_for = True  # next EXPR 'for …:' should fuse into this VERB
            out.append(t); prev = t
            continue

        # Fuse 'Repeat' + 'for …:' into a single VERB
        if expect_repeat_for and ttype == "EXPR" and is_repeat_for(val):
            # modify the previously appended VERB 'Repeat'
            if out and out[-1].get("type") == "VERB" and out[-1].get("value", "").strip().lower() == "repeat":
                out[-1]["value"] = f"Repeat {val.strip()}"  # e.g., 'Repeat for i in 1..3:'
                # Ensure header nesting stays at repeat_level
                out[-1]["nesting"] = repeat_level
            expect_repeat_for = False
            prev = out[-1]
            # DO NOT append this EXPR token (it's been fused)
            continue
        else:
            # If any other token arrives, stop expecting 'for …:'
            expect_repeat_for = False

        # Within Choose: promote clause headers and lift bodies
        if choose_level is not None:
            # Close Choose if a peer/top verb starts
            if ttype == "VERB" and low in {"choose", "repeat", "try"} and nesting <= choose_level:
                choose_level = None
                # fall through to default
            elif ttype in {"VERB", "EXPR"} and is_clause_header(val):
                t["type"] = "VERB"
                t["value"] = low  # normalized lowercase header
                t["nesting"] = max(nesting, choose_level + 1)
                out.append(t); prev = t
                continue
            elif ttype == "VERB" and (low in body_verbs):
                if nesting < choose_level + 2:
                    t["nesting"] = choose_level + 2
                out.append(t); prev = t
                continue
            elif ttype == "EXPR" and prev and prev.get("type") == "VERB" and (prev.get("value", "").strip().lower() in body_verbs):
                if nesting < choose_level + 2:
                    t["nesting"] = choose_level + 2
                out.append(t); prev = t
                continue

        # Within Repeat: lift body lines
        if repeat_level is not None:
            # Close Repeat if a peer/top verb starts
            if ttype == "VERB" and low in {"choose", "repeat", "try"} and nesting <= repeat_level:
                repeat_level = None
                # fall through
            else:
                if ttype == "VERB":
                    if nesting < repeat_level + 1:
                        t["nesting"] = repeat_level + 1
                elif ttype == "EXPR" and prev and prev.get("type") == "VERB":
                    if nesting < repeat_level + 1:
                        t["nesting"] = repeat_level + 1
                out.append(t); prev = t
                continue

        # Default
        out.append(t); prev = t

    return out

def parse(tokens):
    tree = {
        "Module": None,
        "Purpose": None,
        "Inputs": [],
        "Outputs": [],
        "Flow": {"steps": []},
        "Tests": [],
        "Version": None,
    }

    current_section = None

    # Flow hierarchy via block stack keyed by `nesting`
    root_block = {"steps": [], "level": 0}
    stack = [root_block]

    # Tests accumulation
    current_test = None

    def add_step(step, level):
        # Pop until parent level < level — NEVER pop the root (level==0)
        while len(stack) > 1 and stack[-1]["level"] >= level:
            stack.pop()
        parent = stack[-1]
        parent["steps"].append(step)
        if step.get("is_block"):
            step.setdefault("body", {"steps": []})
            stack.append({"steps": step["body"]["steps"], "level": level})

    # Normalize clause headers/bodies BEFORE computing n (length can change)
    tokens = _normalize_clause_nesting(tokens)

    i = 0
    n = len(tokens)

    while i < n:
        tok = tokens[i]
        ttype = tok["type"]
        val = tok.get("value", "")
        level = tok.get("nesting", 0)

        # --- Sections --------------------------------------------------------
        # If pre-pass fused a Repeat header like "Repeat for i in 1..3:",
        # split it back to VERB "Repeat" + EXPR "for i in 1..3:" so schema stays valid.
        if ttype == "VERB":
            low_val = val.strip().lower()
            if low_val.startswith("repeat "):
                after = val.strip()[len("repeat "):]  # keep original casing for EXPR
                if after.lower().startswith("for "):
                    # mutate current token to plain 'Repeat'
                    tokens[i] = dict(tok)
                    tokens[i]["type"] = "VERB"
                    tokens[i]["value"] = "Repeat"
                    tokens[i]["nesting"] = level
                    # insert EXPR token right after with same nesting
                    tokens.insert(i + 1, {"type": "EXPR", "value": after, "nesting": level})
                    n = len(tokens)  # list length changed
                    # refresh locals for continued parsing
                    tok = tokens[i]
                    ttype = "VERB"
                    val = "Repeat"

        if ttype == "SECTION":
            section, inline_val = _normalize_section(val)

            current_section = section

            if current_section == "Flow":
                root_block = {"steps": [], "level": 0}
                stack = [root_block]
                tree["Flow"] = {"steps": root_block["steps"]}

            elif current_section == "Tests":
                tree["Tests"] = []

            elif current_section == "Module" and inline_val:
                tree["Module"] = inline_val

            elif current_section == "Purpose" and inline_val:
                tree["Purpose"] = inline_val

            elif current_section == "Version" and inline_val:
                tree["Version"] = inline_val

            i += 1
            continue

        # Simple sections: Module / Purpose / Version (line following a section)
        if current_section == "Module" and ttype in {"VALUE", "IDENTIFIER"}:
            tree["Module"] = val.strip()
            i += 1
            continue

        if current_section == "Purpose" and ttype in {"VALUE", "IDENTIFIER"}:
            tree["Purpose"] = val.strip()
            i += 1
            continue

        if current_section == "Version" and ttype in {"VALUE", "IDENTIFIER"}:
            tree["Version"] = val.strip()
            i += 1
            continue

        # Inputs/Outputs: IDENTIFIER + RESULTTYPE (next token)
        if current_section == "Inputs" and ttype == "IDENTIFIER":
            name = val.strip()
            if i + 1 < n and tokens[i + 1]["type"] == "RESULTTYPE":
                typ = tokens[i + 1]["value"].strip().title()
                tree["Inputs"].append({"name": name, "type": typ})
                i += 2
                continue

        if current_section == "Outputs" and ttype == "IDENTIFIER":
            name = val.strip()
            if i + 1 < n and tokens[i + 1]["type"] == "RESULTTYPE":
                typ = tokens[i + 1]["value"].strip().title()
                tree["Outputs"].append({"name": name, "type": typ})
                i += 2
                continue

        # --- Flow steps ------------------------------------------------------
        if current_section == "Flow" and ttype == "VERB":
            verb = val.strip().lower()
            expr = None
            if i + 1 < n and tokens[i + 1]["type"] == "EXPR" and tokens[i + 1]["nesting"] == level:
                expr = tokens[i + 1]["value"].strip()
                i += 1  # consume EXPR

            step = {"verb": verb.title(), "expr": expr, "level": level}
            if verb == "repeat" and expr:
                # e.g., "i in 1..n"
                step["repeatSpec"] = expr
                step["is_block"] = True
                step["body"] = {"steps": []}
            elif verb in {"try", "choose"}:
                step["is_block"] = True
                step["body"] = {"steps": []}
            else:
                step["is_block"] = False

            add_step(step, level)
            i += 1
            continue

        # Flow fallback: conversational lines tokenized as EXPR / VALUE / IDENTIFIER
        if current_section == "Flow" and ttype in {"EXPR", "VALUE", "IDENTIFIER"}:
            line = (val or "").strip()
            step = {
                "verb": line,   # NL layer in ast_builder will interpret this full sentence
                "expr": "",
                "level": level,
                "is_block": False,
            }
            add_step(step, level)
            i += 1
            continue

        # --- Tests section ---------------------------------------------------
        if current_section == "Tests" and ttype == "KEY":
            key = val.strip().lower()
            if key == "input":
                # if a previous test exists and already has expectedOutput, push it
                if current_test and ("expectedOutput" in current_test):
                    tree["Tests"].append(current_test)
                    current_test = None
                if not current_test:
                    current_test = {"input": {}, "expectedOutput": None}

            if i + 1 < n and tokens[i + 1]["type"] == "VALUE":
                raw = tokens[i + 1]["value"].strip()
                if key == "input":
                    # parse "a=1, b=2" into dict; accept "{}" for empty
                    s = raw.strip()
                    if s != "{}":
                        for pair in [p.strip() for p in s.split(",") if p.strip()]:
                            if "=" in pair:
                                k, v = pair.split("=", 1)
                                current_test["input"][k.strip()] = v.strip()
                elif key == "expectedoutput":
                    if not current_test:
                        current_test = {"input": {}, "expectedOutput": None}
                    current_test["expectedOutput"] = raw
                i += 2
                continue
            else:
                i += 1
                continue

        # Some tokenizers may emit a bare VALUE for expectedOutput
        if current_section == "Tests" and ttype == "VALUE" and current_test and current_test.get("expectedOutput") is None:
            current_test["expectedOutput"] = val.strip()
            i += 1
            continue

        # Ignore anything else
        i += 1

    # Close last open test
    if current_test:
        tree["Tests"].append(current_test)

    # Phase 3 / Step 2/5: group inline-if chains into parser-level Choose nodes (safe if none present)
    flow = tree.get("Flow")
    if isinstance(flow, dict):
        flow_steps = flow.get("steps") or []
        flow["steps"] = _group_conditionals_in_steps(flow_steps)

    return tree
