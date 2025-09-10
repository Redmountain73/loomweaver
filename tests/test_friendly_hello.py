from pathlib import Path
from src.interpreter import run_tests_from_file

def test_friendly_hello_nl():
    mod = Path("Modules") / "friendly_hello.loom"
    p, t, _ = run_tests_from_file(str(mod))
    assert p == t == 2
