# tests/conftest.py
# Ensure the project root (the folder that contains 'src' and 'tests') is on sys.path
# so that `from src...` imports work during pytest collection and execution.
# Also alias `src.tokenizer` as a top-level module named "tokenizer" so tests that do
# `from tokenizer import tokenize` work in all environments.

import sys
import pathlib
import types

ROOT = pathlib.Path(__file__).resolve().parents[1]  # …/Loom vs code files
ROOT_STR = str(ROOT)

if ROOT_STR not in sys.path:
    sys.path.insert(0, ROOT_STR)

# Sanity check: make sure 'src' is importable and looks like a package
try:
    import src  # noqa: F401
except Exception as e:
    has_pkg = (ROOT / "src" / "__init__.py").is_file()
    raise RuntimeError(
        f"Failed to import 'src' from {ROOT_STR}. "
        f"src/__init__.py exists: {has_pkg}"
    ) from e

# ---- Alias src.tokenizer -> tokenizer (for tests that import `tokenizer`) ----
try:
    from src import tokenizer as _tok_mod
    _tok_err = None
except Exception as _e:  # pragma: no cover
    _tok_mod = None
    _tok_err = _e

if "tokenizer" not in sys.modules:
    shim = types.ModuleType("tokenizer")
    if _tok_mod is not None:
        # Re-export the real tokenize
        shim.tokenize = _tok_mod.tokenize  # type: ignore[attr-defined]
    else:
        # If import failed, expose a stub that raises the original error when used
        def tokenize(*_args, **_kwargs):
            raise _tok_err  # type: ignore[misc]
        shim.tokenize = tokenize  # type: ignore[assignment]
    sys.modules["tokenizer"] = shim
