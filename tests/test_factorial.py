from pathlib import Path
from src.interpreter import run_tests_from_file, run_module_from_file

def test_factorial_passes_embedded_test():
    mod = Path("Modules") / "factorial.loom"
    passed, total, results = run_tests_from_file(str(mod))
    assert passed == total == 1, f"results={results}"

def test_factorial_direct_run():
    mod = Path("Modules") / "factorial.loom"
    result, _ = run_module_from_file(str(mod), inputs={"n": 6})
    assert result == 720
