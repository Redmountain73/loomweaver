# tests/test_vm_neg.py
from textwrap import dedent
import pytest

from src.compiler import run_loom_text_with_vm
from src.vm import TypeErrorLoom

def _mod_neg_ok() -> str:
    return dedent("""\
    I. Module: NegOnNumber
    B. Inputs
    C. Outputs
    D. Flow
       1. Make x = 7
       2. Return -x
    F. Version: 2.1
    """)

def _mod_neg_bad() -> str:
    return dedent("""\
    I. Module: NegOnString
    B. Inputs
    C. Outputs
    D. Flow
       1. Make s = "hi"
       2. Return -s
    F. Version: 2.1
    """)

def test_neg_on_number_returns_negated_value():
    text = _mod_neg_ok()
    result, receipt = run_loom_text_with_vm(text)
    # Accept either int or float, depending on numeric normalization
    assert result == -7 or result == -7.0
    assert receipt.get("engine") == "vm"

def test_neg_on_non_number_raises_typeerrorloom():
    text = _mod_neg_bad()
    with pytest.raises(TypeErrorLoom) as ex:
        run_loom_text_with_vm(text)
    # Keep this loose to avoid coupling to exact message text
    assert "requires number" in str(ex.value).lower()
