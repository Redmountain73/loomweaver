# dev/smoke_choose_receipt.py
# Runs a Choose with Score=87 and prints the interpreter receipt.

import os, sys, json

# Make the project root importable so 'src.*' works
HERE = os.path.abspath(os.path.dirname(__file__))          # ...\dev
ROOT = os.path.abspath(os.path.join(HERE, os.pardir))      # ...\project root
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src.parser import parse
from src.ast_builder import build_ast
from src.interpreter import Interpreter

# Required sections (Module / Version / Purpose / Flow)
tokens = [
    {"type": "SECTION", "value": "Module: SmokeChooseReceipt", "nesting": 0},
    {"type": "SECTION", "value": "Version: 2.1",              "nesting": 0},
    {"type": "SECTION", "value": "Purpose: receipts demo",    "nesting": 0},
    {"type": "SECTION", "value": "Flow",                      "nesting": 0},

    {"type": "VERB", "value": "Make Score = 87",              "nesting": 1},

    {"type": "VERB", "value": "Choose",                       "nesting": 1},
    {"type": "VERB", "value": "when Score >= 90:",            "nesting": 2},
    {"type": "VERB", "value": 'Show "A"',                     "nesting": 3},
    {"type": "VERB", "value": "else if Score >= 80:",         "nesting": 2},
    {"type": "VERB", "value": 'Show "B"',                     "nesting": 3},
    {"type": "VERB", "value": "otherwise:",                   "nesting": 2},
    {"type": "VERB", "value": 'Show "F"',                     "nesting": 3},
]

ast = build_ast(parse(tokens))
interp = Interpreter()
interp.run(ast)

print(json.dumps(interp.receipt, indent=2))
