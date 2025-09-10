# src/outline_normalizer.py
# Deterministic outline normalizer for Loom.
# - Canonicalizes section lines (collapse spaces, normalize 'Key: Value')
# - Canonicalizes Flow block:
#     * bullets -> "  N. <Verb ...>" with Title-Case verbs (Repeat, Choose, Make, Return)
#     * headers -> "    <lowercased header ending with ':'>"
#     * bodies  -> "      <collapsed>"
# - Splits inline "Repeat i in ..." or "i in ..." under bullet into header form.

from __future__ import annotations
import re
from typing import List

# Section headers and bullets
RE_SECTION      = re.compile(r'^\s*([A-Z])\.\s*(.+?)\s*$')
RE_FLOW         = re.compile(r'^\s*[A-Z]\.\s*Flow\s*$', re.IGNORECASE)
RE_FLOW_BULLET  = re.compile(r'^\s*(\d+)\.\s*(.+?)\s*$')

# Clause/header recognizers (no bullet)
RE_CHOOSE       = re.compile(r'^\s*choose\s*$', re.IGNORECASE)
RE_WHEN         = re.compile(r'^\s*when\s+.+:\s*$', re.IGNORECASE)
RE_ELSEIF       = re.compile(r'^\s*else\s+if\s+.+:\s*$', re.IGNORECASE)
RE_OTHERWISE    = re.compile(r'^\s*otherwise\s*:\s*$', re.IGNORECASE)
RE_REPEAT_HDR   = re.compile(r'^\s*repeat\b.+:\s*$', re.IGNORECASE)
RE_RANGE_HDR    = re.compile(r'^\s*[A-Za-z_][A-Za-z0-9_]*\s+in\s+.+:\s*$', re.IGNORECASE)

# Indents
TOP   = "  "      # 2 spaces
HDR   = "    "    # 4 spaces
BODY  = "      "  # 6 spaces

KNOWN_VERBS = {"repeat": "Repeat", "choose": "Choose", "make": "Make", "return": "Return"}

def _strip(s: str) -> str:
    return (s or "").rstrip()

def _collapse_spaces(s: str) -> str:
    return re.sub(r'[ \t]+', ' ', (s or "").strip())

def _canon_section(line: str) -> str:
    m = RE_SECTION.match(line or "")
    if not m:
        return _strip(line)
    letter, rest = m.group(1), m.group(2)
    rest_c = _collapse_spaces(rest)
    if ':' in rest_c:
        k, v = rest_c.split(':', 1)
        return f"{letter}. {k.strip()}: {v.strip()}"
    return f"{letter}. {rest_c}"

def _canon_bullet_text(rest: str) -> str:
    """Title-case known verbs; collapse spaces elsewhere."""
    rest_c = _collapse_spaces(rest)
    if not rest_c:
        return rest_c
    parts = rest_c.split(' ', 1)
    head = parts[0]
    tail = parts[1] if len(parts) > 1 else ""
    hv = KNOWN_VERBS.get(head.lower())
    if hv:
        return f"{hv}{(' ' + tail) if tail else ''}"
    return rest_c

def _canon_header_line(raw: str) -> str:
    """Normalize a header (strip leading/trailing, collapse inner, lowercase)."""
    return _collapse_spaces(raw).lower()

def normalize_loom_outline(text: str) -> str:
    lines = (text or "").splitlines()
    out: List[str] = []

    in_flow = False
    in_choose = False
    in_repeat = False
    awaiting_body = False  # true right after a header

    for raw in lines:
        line = raw.rstrip()

        # Flow section start
        if RE_FLOW.match(line):
            out.append("D. Flow")
            in_flow = True
            in_choose = False
            in_repeat = False
            awaiting_body = False
            continue

        # Any new section (other than Flow) terminates Flow formatting
        if in_flow and RE_SECTION.match(line) and not RE_FLOW.match(line):
            out.append(_canon_section(line))
            in_flow = False
            in_choose = False
            in_repeat = False
            awaiting_body = False
            continue

        if not in_flow:
            # Outside Flow: canonicalize sections; otherwise trim
            if RE_SECTION.match(line):
                out.append(_canon_section(line))
            else:
                out.append(_strip(line))
            continue

        # Inside Flow: bullets first
        mb = RE_FLOW_BULLET.match(line)
        if mb:
            n, rest_raw = mb.group(1), mb.group(2)
            rest_c = _collapse_spaces(rest_raw)
            low = rest_c.lower()

            # Inline 'Repeat ...:' -> split
            if low.startswith("repeat ") and low.endswith(":"):
                # 'Repeat <header>:'
                first = rest_c.split(' ', 1)[0]  # 'Repeat'
                header = rest_c[len(first):].strip()  # '<header>:'
                out.append(f"{TOP}{n}. Repeat")
                out.append(f"{HDR}{_canon_header_line(header)}")
                in_repeat = True
                in_choose = False
                awaiting_body = True
                continue

            # Inline '<iter> in ...:' -> implied 'Repeat' bullet
            if RE_RANGE_HDR.match(rest_c):
                out.append(f"{TOP}{n}. Repeat")
                out.append(f"{HDR}{_canon_header_line(rest_c)}")
                in_repeat = True
                in_choose = False
                awaiting_body = True
                continue

            # Plain bullets: normalize verb casing and collapse spaces
            canon = _canon_bullet_text(rest_c)
            out.append(f"{TOP}{n}. {canon}")
            in_choose = False
            in_repeat = False
            awaiting_body = False
            continue

        # Clause/header lines under a bullet (strip leading spaces!)
        if RE_CHOOSE.match(line):
            out.append(f"{HDR}Choose")
            in_choose = True
            in_repeat = False
            awaiting_body = False
            continue

        if RE_WHEN.match(line) or RE_ELSEIF.match(line) or RE_OTHERWISE.match(line):
            out.append(f"{HDR}{_canon_header_line(line)}")
            in_choose = True
            in_repeat = False
            awaiting_body = True
            continue

        if RE_REPEAT_HDR.match(line) or RE_RANGE_HDR.match(line):
            out.append(f"{HDR}{_canon_header_line(line)}")
            in_repeat = True
            in_choose = False
            awaiting_body = True
            continue

        # Non-empty lines → body (after a header) or fallback as a TOP-indented plain line
        stripped = _strip(line)
        if stripped != "":
            if in_choose or in_repeat or awaiting_body:
                out.append(f"{BODY}{_collapse_spaces(stripped)}")
            else:
                # A stray line inside Flow → normalize as TOP-indented
                out.append(f"{TOP}{_collapse_spaces(stripped)}")
            continue

        # Blank inside Flow → keep a canonical blank
        out.append("")

    # Trim trailing empty lines
    while out and out[-1] == "":
        out.pop()

    return "\n".join(out) + ("\n" if out else "")
