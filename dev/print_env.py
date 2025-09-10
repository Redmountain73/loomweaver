# dev/print_env.py
# Prints current folder, sys.path, and whether 'src' is importable.

import os, sys, importlib.util, pathlib

root = pathlib.Path(__file__).resolve().parent.parent  # project root (folder that contains src and dev)
print("cwd (os.getcwd):", os.getcwd())
print("script root:", root)
print("exists src?:", (root / "src").is_dir())
print("exists dev?:", (root / "dev").is_dir())
print("src/__init__.py exists?:", (root / "src" / "__init__.py").is_file())

# Ensure project root is on sys.path (so 'import src' can work)
if str(root) not in sys.path:
    sys.path.insert(0, str(root))
print("\nFIRST 5 sys.path entries:")
for p in sys.path[:5]:
    print("  -", p)

# Can Python find 'src' as a package?
spec = importlib.util.find_spec("src")
print("\nfind_spec('src'):", spec.origin if spec else spec)

# Try importing src.parser and src.ast_builder and print their file paths.
def try_import(name):
    try:
        mod = __import__(name, fromlist=["*"])
        print(f"Imported {name} from:", getattr(mod, "__file__", "<no file>"))
    except Exception as e:
        print(f"FAILED to import {name}: {e.__class__.__name__}: {e}")

try_import("src")
try_import("src.parser")
try_import("src.ast_builder")
