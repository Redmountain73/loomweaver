# dev/smoke_boolean.py
# Verifies not/and/or precedence + short-circuit through the interpreter.

import os, sys, json
HERE = os.path.abspath(os.path.dirname(__file__))
ROOT = os.path.abspath(os.path.join(HERE, os.pardir))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src.parser import parse
from src.ast_builder import build_ast
from src.interpreter import Interpreter

tokens = [
    {"type": "SECTION", "value": "Module: SmokeBoolean", "nesting": 0},
    {"type": "SECTION", "value": "Version: 2.1",         "nesting": 0},
    {"type": "SECTION", "value": "Purpose: boolean ops", "nesting": 0},
    {"type": "SECTION", "value": "Flow",                 "nesting": 0},

    {"type": "VERB", "value": "Make Adult = true",       "nesting": 1},
    {"type": "VERB", "value": "Make HasId = false",      "nesting": 1},
    {"type": "VERB", "value": "Make Expired = false",    "nesting": 1},

    {"type": "VERB", "value": "Choose",                                 "nesting": 1},
    {"type": "VERB", "value": "when Adult and (HasId or not Expired):", "nesting": 2},
    {"type": "VERB", "value": 'Show "eligible"',                        "nesting": 3},
    {"type": "VERB", "value": "otherwise:",                             "nesting": 2},
    {"type": "VERB", "value": 'Show "ineligible"',                      "nesting": 3},
]

ast = build_ast(parse(tokens))
interp = Interpreter()
interp.run(ast)

print("logs:", interp.receipt["logs"])
print("choose:", [s for s in interp.receipt["steps"] if s.get("event") == "choose"][0])
