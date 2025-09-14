# tests/test_normalization_hash.py
from __future__ import annotations
import hashlib
from src.outline_normalizer import normalize_loom_outline
from src.tokenizer import tokenize
from src.parser import parse
from src.ast_builder import build_ast

FACTORIAL_A = """\
I. Module: Factorial
D. Flow
  1. Make result = 1
  2. Repeat
      i in 1..n:
      Make result = result * i
  3. Return result
F. Version: 2.1
"""

FACTORIAL_B = """\
I. Module: Factorial
D. Flow
1.   Make   result = 1
2. Repeat i in 1..n:
    Make result = result * i
3. Return result
F. Version:   2.1
"""

def _hash_norm(s: str) -> str:
    norm = normalize_loom_outline(s)
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()

def _ast(s: str):
    # Build AST directly from raw text (no normalization) to assert parser resilience
    return build_ast(parse(tokenize(s)))

def test_normalization_hash_and_ast_match():
    # Hash equality under normalization
    hA = _hash_norm(FACTORIAL_A)
    hB = _hash_norm(FACTORIAL_B)
    assert hA == hB

    # AST equality (flows match even before normalization)
    aA = _ast(FACTORIAL_A)
    aB = _ast(FACTORIAL_B)
    assert aA.get("flow") == aB.get("flow")
