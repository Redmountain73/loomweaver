# src/names.py
# Normalization helpers for module and capability identifiers.
from __future__ import annotations
import re

# Lowercase, spaces -> hyphens, preserve underscores, strip other punctuation.
# Ensure leading char is [a-z_] and max length 128.
_SLUG_ALLOWED = re.compile(r'[^a-z0-9_-]+')
_LEADING_OK = re.compile(r'^[a-z_]')
_WS = re.compile(r'\s+')

def normalize_module_slug(name: str | None) -> str:
    if not isinstance(name, str):
        return "_"
    s = name.strip().lower()
    s = _WS.sub("-", s)
    s = _SLUG_ALLOWED.sub("", s)
    if not s:
        s = "_"
    if not _LEADING_OK.match(s):
        s = "_" + s
    if len(s) > 128:
        s = s[:128]
    return s

def cap_match(rule_val: str, actual_norm: str) -> bool:
    """Match capability 'from'/'to' where '*' is wildcard, else compare normalized."""
    if rule_val == "*":
        return True
    return normalize_module_slug(rule_val) == actual_norm

def check_capability(capabilities: dict | None, from_name: str, to_name: str, action: str = "Call") -> dict:
    """
    Evaluate capability for an action. Returns a dict suitable for receipts:
    {
      'action': 'Call', 'from': <norm>, 'to': <norm>,
      'allowed': True/False, 'matchedRule': {...} or None, 'mode': 'warn'|'enforce'|'none',
      'raw': {'from': <raw>, 'to': <raw>}
    }
    """
    from_norm = normalize_module_slug(from_name or "")
    to_norm = normalize_module_slug(to_name or "")
    result = {
        "action": action,
        "from": from_norm,
        "to": to_norm,
        "allowed": True,
        "matchedRule": None,
        "raw": {"from": from_name, "to": to_name},
    }
    if not capabilities or not isinstance(capabilities, dict):
        result["mode"] = "none"
        return result
    rules = capabilities.get("rules") or []
    for r in rules:
        try:
            rv_from = r.get("from", "*")
            rv_to = r.get("to", "*")
            allow = r.get("allow") or []
            if cap_match(rv_from, from_norm) and cap_match(rv_to, to_norm) and action in allow:
                result["matchedRule"] = {"from": rv_from, "to": rv_to, "allow": list(allow)}
                result["allowed"] = True
                result["mode"] = "policy"
                return result
        except Exception:
            # Ignore malformed rule and continue
            continue
    result["allowed"] = False
    result["mode"] = "policy"
    return result
