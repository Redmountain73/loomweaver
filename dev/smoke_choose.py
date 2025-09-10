# dev/smoke_choose.py
# Self-contained smoke test: adds project ROOT to sys.path, then imports src.*

import os, sys, json

# Compute project ROOT = folder that contains 'src' and 'dev'
HERE = os.path.abspath(os.path.dirname(__file__))          # ...\Loom vs code files\dev
ROOT = os.path.abspath(os.path.join(HERE, os.pardir))      # ...\Loom vs code files
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# Safety checks
assert os.path.isdir(os.path.join(ROOT, "src")), "missing src/"
assert os.path.isfile(os.path.join(ROOT, "src", "__init__.py")), "missing src/__init__.py"

from src.parser import parse
from src.ast_builder import build_ast

# Provide required sections:
# - Module: <name>
# - Version: MAJOR.MINOR (e.g., 2.1)  ← schema enforces ^\d+\.\d+$
# - Purpose: <short string>            ← schema requires string
# - Flow: (then the steps)
tokens = [
    {"type": "SECTION", "value": "Module: SmokeChoose",           "nesting": 0},
    {"type": "SECTION", "value": "Version: 2.1",                  "nesting": 0},
    {"type": "SECTION", "value": "Purpose: parser smoke for Choose","nesting": 0},
    {"type": "SECTION", "value": "Flow",                          "nesting": 0},

    # Multiline Choose: levels 1/2/3 (header/labels/bodies)
    {"type": "VERB", "value": "Choose",               "nesting": 1},
    {"type": "VERB", "value": "when score >= 90:",    "nesting": 2},
    {"type": "VERB", "value": 'Show "A"',             "nesting": 3},
    {"type": "VERB", "value": "else if score >= 80:", "nesting": 2},
    {"type": "VERB", "value": 'Show "B"',             "nesting": 3},
    {"type": "VERB", "value": "otherwise:",           "nesting": 2},
    {"type": "VERB", "value": 'Show "F"',             "nesting": 3},
]

tree = parse(tokens)
module = build_ast(tree)

# Print the Choose step to verify branches
print(json.dumps(module["flow"][0], indent=2))
