from pathlib import Path
import json
import pytest
import jsonschema

# BOM-safe read (handles UTF-8 with BOM)
SCHEMA = json.loads(Path("Schemas/loom-module.schema.json").read_text(encoding="utf-8-sig"))

def validate_ast(ast):
    jsonschema.validate(instance=ast, schema=SCHEMA)

def _num(n): return {"type": "Number", "value": n}
def _id(name): return {"type": "Identifier", "name": name}
def _ret_num(n): return {"verb": "Return", "args": {"expr": _num(n)}}

def test_choose_valid_schema_roundtrip():
    ast = {
        "type": "Module",
        "name": "Dummy",
        "purpose": "demo",
        "inputs": [],
        "outputs": [],
        "flow": [
            {
                "verb": "Choose",
                "args": {
                    "branches": [
                        {"when": {"type": "Binary", "op": ">=", "left": _id("x"), "right": _num(10)}, "steps": [_ret_num(1)]},
                        {"otherwise": True, "steps": [_ret_num(0)]}
                    ]
                }
            }
        ],
        "tests": [],
        "version": "0.1",
        "astVersion": "2.1.0"
    }
    validate_ast(ast)  # should not raise

def test_choose_invalid_both_when_and_otherwise():
    bad = {
        "type": "Module",
        "name": "Dummy",
        "flow": [
            {"verb": "Choose", "args": {"branches": [
                {"when": _num(1), "otherwise": True, "steps": [_ret_num(1)]}
            ]}},
        ],
        "version": "0.1",
        "astVersion": "2.1.0"
    }
    with pytest.raises(jsonschema.ValidationError):
        validate_ast(bad)

def test_choose_invalid_empty_steps():
    bad = {
        "type": "Module",
        "name": "Dummy",
        "flow": [
            {"verb": "Choose", "args": {"branches": [
                {"when": _num(1), "steps": []}
            ]}},
        ],
        "version": "0.1",
        "astVersion": "2.1.0"
    }
    with pytest.raises(jsonschema.ValidationError):
        validate_ast(bad)
