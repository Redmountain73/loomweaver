# src/tokenizer.py
# Tokenizes Loom outline into flat tokens with nesting.
# Tokens:
#   {"type": "SECTION"|"VALUE"|"IDENTIFIER"|"RESULTTYPE"|"VERB"|"EXPR"|"KEY",
#    "value": str, "nesting": int}

from __future__ import annotations
import re
from typing import List, Dict, Tuple, Optional

# ------------------------------ Config ---------------------------------------

SECTION_NAMES = {"module", "purpose", "inputs", "outputs", "flow", "tests", "version"}

# Known Flow verbs (lowercase). NL layer in ast_builder will add more semantics.
KNOWN_VERBS = {
    # core
    "make", "set", "assign", "remember", "forget",
    "return", "show", "print", "emit", "check", "assert", "ensure", "require",
    "repeat", "try", "choose",
    # ask family
    "ask", "prompt", "get", "collect", "request",
    # "for each" handled specially
}

# Courtesy prefixes that shouldn’t block verb detection
COURTESY_RE = re.compile(r'^(?:\s*(?:please|kindly|go ahead and)\s+)+', re.IGNORECASE)

# ------------------------------ Patterns -------------------------------------

# Example: "I. Module: Greeting"  or  "D. Flow"
HEADER_RE = re.compile(
    r'^\s*([A-Za-z0-9IVXLCDM]+)\.\s*([A-Za-z ]+?)(?::\s*(.*))?\s*$'
)

# Generic bullet item:
#    "  1. something"
#    "A. Inputs"
#    "   i. return message."
BULLET_RE = re.compile(
    r'^(?P<indent>\s*)(?P<tag>(?:\d+|[A-Za-z]|[ivxlcdmIVXLCDM]+))\.\s*(?P<rest>.*)$'
)

# Inputs/Outputs: "name: Type"
IO_RE = re.compile(
    r'^\s*(?P<name>[A-Za-z_][A-Za-z0-9_\-]*)\s*:\s*(?P<typ>[A-Za-z/ ]+)\s*$'
)

# Tests: "key: value"   (supports bullet or non-bullet lines)
TEST_KV_RE = re.compile(
    r'^\s*(?P<key>input|expectedOutput)\s*:\s*(?P<val>.*)\s*$',
    re.IGNORECASE
)

# A top-level bullet’s rest might itself be a section header: "Inputs", "Flow", etc.
INLINE_SECTION_RE = re.compile(
    r'^(?P<sec>[A-Za-z ]+?)(?::\s*(?P<val>.*))?$'
)

# --------------------------- Helpers & emitters -------------------------------

def _level_from_indent(indent: str) -> int:
    """Convert leading whitespace to nesting level (2 spaces ~= 1 level, tabs=4 spaces)."""
    if not indent:
        return 0
    width = indent.replace("\t", "    ")
    # accept 2..4 per level, but use //2 to be tolerant
    return max(0, len(width) // 2)

def _emit(tokens: List[Dict], t: str, v: str, lvl: int):
    tokens.append({"type": t, "value": v, "nesting": lvl})

def _detect_flow_verb(text: str) -> Tuple[Optional[str], Optional[str]]:
    """
    If text starts with a known verb (after removing courtesy), return (verb, remainder).
    Special-case 'for each ...' as 'repeat'.
    Otherwise return (None, None) and let NL layer handle as EXPR.
    """
    s = COURTESY_RE.sub("", text).strip()
    if not s:
        return None, None

    # Special multi-word "for each"
    m = re.match(r'^(for\s+each)\b(.*)$', s, flags=re.IGNORECASE)
    if m:
        return "repeat", (m.group(2) or "").strip()

    # Single word head
    m = re.match(r'^([A-Za-z]+)\b(.*)$', s)
    if not m:
        return None, None
    head = m.group(1).lower()
    rest = (m.group(2) or "").strip()
    if head in KNOWN_VERBS:
        return head, rest
    return None, None

def _emit_section(tokens: List[Dict], name: str, inline_val: str | None):
    sec_title = name.title()
    _emit(tokens, "SECTION", sec_title, 0)
    if inline_val and inline_val.strip():
        _emit(tokens, "VALUE", inline_val.strip(), 0)

# ------------------------------ Main tokenizer -------------------------------

# ------------------------------ Main tokenizer -------------------------------

def tokenize(text: str) -> List[Dict]:
    tokens: List[Dict] = []
    current_section: Optional[str] = None  # Title-cased, e.g., "Flow"

    lines = text.splitlines()

    for raw in lines:
        # 1) Outline headers like "I. Module: Greeting" or "D. Flow"
        h = HEADER_RE.match(raw)
        if h:
            sec = (h.group(2) or "").strip()
            if sec.lower() in SECTION_NAMES:
                current_section = sec.title()
                _emit_section(tokens, current_section, (h.group(3) or ""))
                continue  # handled as a section line

        # 2) Bullets: items within sections or section bullets like "B. Inputs"
        b = BULLET_RE.match(raw)
        if b:
            indent = b.group("indent") or ""
            rest = (b.group("rest") or "")
            lvl = _level_from_indent(indent)

            # Top-level bullet might itself be a section switch, e.g., "B. Inputs"
            if lvl == 0:
                ms = INLINE_SECTION_RE.match(rest)
                if ms:
                    sec = (ms.group("sec") or "").strip()
                    val = (ms.group("val") or "").strip()
                    if sec.lower() in SECTION_NAMES:
                        current_section = sec.title()
                        _emit_section(tokens, current_section, val)
                        continue  # section handled; next line

            # If not a section header, tokenize based on current_section
            if current_section is None:
                # Bullets before any known section → ignore
                continue

            if current_section in ("Inputs", "Outputs"):
                m = IO_RE.match(rest)
                if m:
                    _emit(tokens, "IDENTIFIER", m.group("name").strip(), lvl)
                    _emit(tokens, "RESULTTYPE", m.group("typ").strip().title(), lvl)
                # ignore non-matching in IO
                continue

            if current_section == "Tests":
                m = TEST_KV_RE.match((rest or "").strip())
                if m:
                    _emit(tokens, "KEY", m.group("key").strip(), lvl)
                    _emit(tokens, "VALUE", m.group("val").strip(), lvl)
                # ignore non-matching in Tests
                continue

            if current_section == "Flow":
                s = (rest or "").strip()
                verb, remainder = _detect_flow_verb(s)
                if verb:
                    _emit(tokens, "VERB", verb.title(), lvl)
                    _emit(tokens, "EXPR", remainder or "", lvl)
                else:
                    # Pass whole line to NL layer as EXPR so ast_builder can interpret
                    _emit(tokens, "EXPR", s, lvl)
                continue

            # Other sections with bullets → treat as VALUE
            _emit(tokens, "VALUE", (rest or "").strip(), lvl)
            continue

        # 3) Non-bullet lines inside sections
        if current_section in ("Module", "Purpose", "Version"):
            s = raw.strip()
            if s:
                _emit(tokens, "VALUE", s, 0)
            continue

        if current_section == "Tests":
            s = raw.strip()
            if s:
                m = TEST_KV_RE.match(s)
                if m:
                    _emit(tokens, "KEY", m.group("key").strip(), 0)
                    _emit(tokens, "VALUE", m.group("val").strip(), 0)
            continue

        if current_section == "Flow":
            s = raw.strip()
            if s:
                verb, remainder = _detect_flow_verb(s)
                if verb:
                    _emit(tokens, "VERB", verb.title(), 0)
                    _emit(tokens, "EXPR", remainder or "", 0)
                else:
                    _emit(tokens, "EXPR", s, 0)
            continue

        # Lines outside any section are ignored

    return tokens

# --- Conditional detectors for Phase 3 (Step 1) ------------------------------
# Non-breaking helpers: parser will call these in Phase 3 / Step 2.
# They DO NOT change tokenization behavior today.

# Courtesy/polite prefixes (kept permissive; parser still has final authority)
_COND_COURTESY = r"(?:please|kindly|go ahead and|would you|could you)\s+"

# Heads: if/when/unless ... then ...
_COND_IF_HEAD = re.compile(
    rf"^\s*(?:{_COND_COURTESY})?\s*(if|when|unless)\b",
    re.IGNORECASE,
)
_COND_THEN = re.compile(r"\bthen\b", re.IGNORECASE)

# Else / otherwise variants (including chained else-if)
_COND_ELSE_HEAD = re.compile(
    r"^\s*(?:else\s+if|otherwise\s+if|otherwise|else)\b",
    re.IGNORECASE,
)

_TRAIL_PUNCT = re.compile(r"[.;!]+$")


def detect_conditional_markers(line: str) -> dict:
    """
    Lightweight NL scan for conditional scaffolding.

    Returns:
      {
        'is_conditional': bool,            # any of if/when/unless/else/otherwise heads
        'head': 'if'|'when'|'unless'|'otherwise'|None,
        'has_then': bool,                  # true if a 'then' delimiter appears
        'normalized': str                  # punctuation-trimmed text (no mutation of caller state)
      }
    """
    if not isinstance(line, str):
        return {"is_conditional": False, "head": None, "has_then": False, "normalized": ""}

    text = _TRAIL_PUNCT.sub("", line.strip())
    head = None

    m_if = _COND_IF_HEAD.match(text)
    if m_if:
        head = m_if.group(1).lower()
    elif _COND_ELSE_HEAD.match(text):
        head = "otherwise"

    return {
        "is_conditional": head is not None,
        "head": head,
        "has_then": bool(_COND_THEN.search(text)),
        "normalized": text,
    }

# (Optional) If your tokenizer builds per-line flow records like
# {'kind': 'FlowLine', 'text': 'if n == 0 then return 1'},
# you MAY enrich them with: rec['cond'] = detect_conditional_markers(rec['text'])
# but DO NOT change current outputs yet. Parser will call the helper directly.
