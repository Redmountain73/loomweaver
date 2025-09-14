# src/nl_comparatives.py
# ELI5: turn phrases like "score is at least 90" into ("score", ">=", 90)

from __future__ import annotations
import re
from typing import Optional, Tuple, Union

Value = Union[int, float, str]
Comparative = Tuple[str, str, Value]  # (left, op, right)

_ID = r"[A-Za-z_][A-Za-z0-9_\.]*"         # identifiers (allow dotted: a.b.c)
_NUM = r"(?:\d+(?:\.\d+)?)"               # 123 or 123.45
_STR = r"(?:'[^']*'|\"[^\"]*\")"          # 'foo' or "foo"
_VAL = rf"(?:{_NUM}|{_STR}|{_ID})"        # number | string | identifier

def _coerce(val: str) -> Value:
    val = val.strip()
    if re.fullmatch(_NUM, val):
        return int(val) if "." not in val else float(val)
    if (val.startswith("'") and val.endswith("'")) or (val.startswith('"') and val.endswith('"')):
        return val[1:-1]
    return val  # identifier string

def _clean_tail(text: str) -> str:
    s = text.strip()
    # Remove optional courtesy phrase (please/thanks/thank you) possibly preceded by comma/semicolon and followed by punctuation
    s = re.sub(r"\s*[,;:]?\s*(?:please|thanks|thank you)\s*[\.!\?,;:]*\s*$", "", s, flags=re.IGNORECASE)
    # Then remove any leftover trailing punctuation
    s = re.sub(r"\s*[\.!\?,;:]+\s*$", "", s)
    return s

_PATTERNS = [
    # >=
    (re.compile(rf"^({_ID})\s+(?:is\s+|are\s+)?(?:at\s+least|no\s+less\s+than)\s+({_VAL})$", re.IGNORECASE), ">="),
    # <=
    (re.compile(rf"^({_ID})\s+(?:is\s+|are\s+)?(?:at\s+most|no\s+more\s+than)\s+({_VAL})$", re.IGNORECASE), "<="),
    # >
    (re.compile(rf"^({_ID})\s+(?:is\s+|are\s+)?(?:greater\s+than|more\s+than)\s+({_VAL})$", re.IGNORECASE), ">"),
    # <
    (re.compile(rf"^({_ID})\s+(?:is\s+|are\s+)?(?:less\s+than|fewer\s+than)\s+({_VAL})$", re.IGNORECASE), "<"),
    # !=
    (re.compile(rf"^({_ID})\s+(?:is\s+|are\s+)?(?:not\s+equal\s+to|is\s+not|are\s+not)\s+({_VAL})$", re.IGNORECASE), "!="),
    # == (explicit equals/equal to)
    (re.compile(rf"^({_ID})\s+(?:is\s+|are\s+)?(?:equals?|equal\s+to)\s+({_VAL})$", re.IGNORECASE), "=="),
    # == (simple copula: "x is 5", "status is 'ok'")
    (re.compile(rf"^({_ID})\s+(?:is|are)\s+({_VAL})$", re.IGNORECASE), "=="),
    # Symbolic operators (spaces optional)
    (re.compile(rf"^({_ID})\s*>=\s*({_VAL})$", re.IGNORECASE), ">="),
    (re.compile(rf"^({_ID})\s*<=\s*({_VAL})$", re.IGNORECASE), "<="),
    (re.compile(rf"^({_ID})\s*>\s*({_VAL})$", re.IGNORECASE), ">"),
    (re.compile(rf"^({_ID})\s*<\s*({_VAL})$", re.IGNORECASE), "<"),
    (re.compile(rf"^({_ID})\s*==\s*({_VAL})$", re.IGNORECASE), "=="),
    (re.compile(rf"^({_ID})\s*!=\s*({_VAL})$", re.IGNORECASE), "!="),
]

def parse_comparative(text: str) -> Optional[Comparative]:
    """
    Returns (left, op, right) or None if not a comparative we know.
    Accepts trailing punctuation/courtesy words. Ignores leading 'when/if/unless'.
    """
    if not text:
        return None
    s = text.strip()

    # strip leading heads like "when", "if", "unless"
    s = re.sub(r"^(?:when|if|unless)\s+", "", s, flags=re.IGNORECASE)

    # drop a trailing ':' and courtesy words/punct
    s = s[:-1] if s.endswith(":") else s
    s = _clean_tail(s)

    for pat, op in _PATTERNS:
        m = pat.match(s)
        if m:
            left = m.group(1)
            right_raw = m.group(2)
            right = _coerce(right_raw)
            return (left, op, right)
    return None
