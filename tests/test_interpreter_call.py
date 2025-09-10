# tests/test_interpreter_call.py
from src.parser import parse
from src.ast_builder import build_ast
from src.interpreter import Interpreter

def make_module(tokens):
    return build_ast(parse(tokens))

def test_call_executes_and_binds_result():
    # Callee returns "Hello " + Name
    callee_tokens = [
        {"type":"SECTION","value":"Module: Greeting","nesting":0},
        {"type":"SECTION","value":"Version: 2.1","nesting":0},
        {"type":"SECTION","value":"Purpose: demo","nesting":0},
        {"type":"SECTION","value":"Flow","nesting":0},
        {"type":"VERB","value":'Return "Hello " + Name',"nesting":1},
    ]
    callee = make_module(callee_tokens)

    parent_tokens = [
        {"type":"SECTION","value":"Module: Parent","nesting":0},
        {"type":"SECTION","value":"Version: 2.1","nesting":0},
        {"type":"SECTION","value":"Purpose: demo","nesting":0},
        {"type":"SECTION","value":"Flow","nesting":0},
        {"type":"VERB","value":'Call Greeting with Name = "World" save as Out',"nesting":1},
        {"type":"VERB","value":'Show Out',"nesting":1},
    ]
    parent = make_module(parent_tokens)

    interp = Interpreter(registry={"Greeting": callee})
    interp.run(parent)

    # Result shows up in logs and env via "save as Out"
    assert interp.receipt["logs"][-1] == "Hello World"
    # There should be a call event
    call_events = [s for s in interp.receipt["steps"] if s.get("event") == "call"]
    assert call_events and call_events[0]["module"] == "Greeting"
    assert call_events[0]["inputs"]["Name"] == "World"
