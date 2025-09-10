# tests/test_schema_call.py
import json
from pathlib import Path
import jsonschema
import pytest

SCHEMA_PATH = Path(__file__).resolve().parents[1] / "Schemas" / "loom-module.schema.json"
SCHEMA = json.loads(Path(SCHEMA_PATH).read_text(encoding="utf-8"))

def validate(obj):
    jsonschema.validate(instance=obj, schema=SCHEMA)

def base_module(flow):
    return {
        "type": "Module",
        "name": "SchemaCall",
        "purpose": "schema test",
        "version": "2.1",
        "astVersion": "2.1.0",
        "flow": flow,
        "inputs": [],
        "outputs": [],
        "tests": []
    }

def test_call_valid_minimal():
    mod = base_module([
        {"verb": "Call", "args": {"module": "Greeting", "inputs": {}}}
    ])
    validate(mod)  # should NOT raise

def test_call_requires_module_and_inputs():
    mod_missing_module = base_module([
        {"verb": "Call", "args": {"inputs": {}}}
    ])
    with pytest.raises(jsonschema.ValidationError):
        validate(mod_missing_module)

    mod_missing_inputs = base_module([
        {"verb": "Call", "args": {"module": "Greeting"}}
    ])
    with pytest.raises(jsonschema.ValidationError):
        validate(mod_missing_inputs)

def test_call_args_shapes():
    # inputs must be an object
    mod_inputs_array = base_module([
        {"verb": "Call", "args": {"module": "Greeting", "inputs": []}}
    ])
    with pytest.raises(jsonschema.ValidationError):
        validate(mod_inputs_array)

    # result (if present) must be string
    mod_result_not_string = base_module([
        {"verb": "Call", "args": {"module": "Greeting", "inputs": {}, "result": 123}}
    ])
    with pytest.raises(jsonschema.ValidationError):
        validate(mod_result_not_string)

def test_call_no_extra_args_allowed():
    mod_extra = base_module([
        {"verb": "Call", "args": {"module": "Greeting", "inputs": {}, "foo": 1}}
    ])
    with pytest.raises(jsonschema.ValidationError):
        validate(mod_extra)
