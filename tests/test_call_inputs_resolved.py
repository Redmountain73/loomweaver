from src.parser import parse
from src.ast_builder import build_ast
from src.interpreter import Interpreter

def make(tokens):
    return build_ast(parse(tokens))

def _lower_keys(d):
    return { (k.lower() if isinstance(k, str) else k): v for k, v in (d or {}).items() }

def test_call_inputs_resolved_uses_default_when_caller_omits():
    # Callee asks for 'name' with a default
    callee = make([
        {"type":"SECTION","value":"Module: Greeter","nesting":0},
        {"type":"SECTION","value":"Version: 2.1","nesting":0},
        {"type":"SECTION","value":"Purpose: demo","nesting":0},
        {"type":"SECTION","value":"Flow","nesting":0},
        {"type":"VERB","value":'Ask name default "World"', "nesting":1},
        {"type":"VERB","value":'Return "Hi " + name', "nesting":1},
    ])

    # Parent calls without inputs; callee default should hydrate it.
    parent = make([
        {"type":"SECTION","value":"Module: Parent","nesting":0},
        {"type":"SECTION","value":"Version: 2.1","nesting":0},
        {"type":"SECTION","value":"Purpose: demo","nesting":0},
        {"type":"SECTION","value":"Flow","nesting":0},
        {"type":"VERB","value":'Call Greeter save as Out', "nesting":1},
        {"type":"VERB","value":'Return Out', "nesting":1},
    ])

    interp = Interpreter(registry={"Greeter": callee})
    result = interp.run(parent)

    # Find the call event
    call_events = [s for s in interp.receipt["steps"] if s.get("event") == "call"]
    assert len(call_events) == 1
    call = call_events[0]

    # Result correctness
    assert result == "Hi World"

    # Provenance: input 'name' came from default (case-insensitive check)
    resolved = _lower_keys(call.get("inputsResolved", {}))
    assert "name" in resolved
    assert resolved["name"]["source"] == "default"
    assert resolved["name"]["value"] == "World"
