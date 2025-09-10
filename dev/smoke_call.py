# dev/smoke_call.py
# Proves Phase 4 Call: parent Calls Greeting with Name="World" and captures result

import os, sys, json
HERE = os.path.abspath(os.path.dirname(__file__))
ROOT = os.path.abspath(os.path.join(HERE, os.pardir))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src.parser import parse
from src.ast_builder import build_ast
from src.interpreter import Interpreter

# --- Callee module: Greeting ---
callee_tokens = [
    {"type": "SECTION", "value": "Module: Greeting", "nesting": 0},
    {"type": "SECTION", "value": "Version: 2.1",     "nesting": 0},
    {"type": "SECTION", "value": "Purpose: demo",    "nesting": 0},
    {"type": "SECTION", "value": "Flow",             "nesting": 0},
    # Return "Hello " + Name
    {"type": "VERB", "value": 'Return "Hello " + Name', "nesting": 1},
]
callee_ast = build_ast(parse(callee_tokens))

# --- Parent module that Calls Greeting ---
parent_tokens = [
    {"type": "SECTION", "value": "Module: Parent", "nesting": 0},
    {"type": "SECTION", "value": "Version: 2.1",   "nesting": 0},
    {"type": "SECTION", "value": "Purpose: demo",  "nesting": 0},
    {"type": "SECTION", "value": "Flow",           "nesting": 0},

    # Option A: Call with save as
    {"type": "VERB", "value": 'Call Greeting with Name = "World" save as Out', "nesting": 1},
    {"type": "VERB", "value": 'Show Out', "nesting": 1},

    # Option B (also supported): Make Out = Call Greeting with Name = "World"
    # {"type": "VERB", "value": 'Make Out = Call Greeting with Name = "World"', "nesting": 1},
    # {"type": "VERB", "value": 'Show Out', "nesting": 1},
]
parent_ast = build_ast(parse(parent_tokens))

# We register the callee under its Module name so the interpreter can resolve it.
registry = {"Greeting": callee_ast}

interp = Interpreter(registry=registry)
interp.run(parent_ast)

print("Logs:", interp.receipt["logs"])
print("Steps:", json.dumps(interp.receipt["steps"], indent=2))
