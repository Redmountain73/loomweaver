from pathlib import Path
from src.interpreter import run_tests_from_file

def test_greeting_passes():
    mod = Path("Modules") / "greeting.loom"
    passed, total, results = run_tests_from_file(str(mod))
    assert passed == total == 1, f"results={results}"
