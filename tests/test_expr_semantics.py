from src.tokenizer import tokenize
from src.parser import parse
from src.ast_builder import build_ast
from src.interpreter import Interpreter, RuntimeErrorLoom
import pytest

def _build_mod(expr: str):
    # Outline style so the builder sets name/purpose/version correctly.
    text = f"""I. Module: ExprProbe
A. Purpose: test
D. Flow
   1. Return {expr}
F. Version: 2.1
"""
    return build_ast(parse(tokenize(text)))

def run_expr(expr: str):
    mod = _build_mod(expr)
    return Interpreter().run(mod)

def test_arithmetic_tighter_than_comparisons():
    # 1 + 2*3 = 7; 7 > 6 => True
    assert run_expr("1 + 2 * 3 > 6") is True

def test_comparisons_tighter_than_boolean():
    assert run_expr("1 < 2 and 3 < 4") is True
    assert run_expr("1 < 2 or 3 < 4") is True
    assert run_expr("not (2 == 2) or true") is True  # requires parens

def test_boolean_precedence_not_and_or():
    assert run_expr("not false or false") is True      # (not false) or false
    assert run_expr("not (false or false)") is True    # explicit parens
    assert run_expr("true and not false") is True

def test_short_circuit_and_skips_right():
    # Right would divide by zero if evaluated; short-circuit must skip it.
    assert run_expr("false and (1 / 0 == 1)") is False

def test_truthiness_is_boolean_only_and_or_left():
    # Non-boolean in boolean ops should raise
    with pytest.raises(RuntimeErrorLoom):
        run_expr("1 and true")
    with pytest.raises(RuntimeErrorLoom):
        run_expr("false or 1")
