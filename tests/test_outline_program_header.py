# tests/test_outline_program_header.py
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from compile_outline_to_program import parse_outline_header

SAMPLE = """Agent Name: Loomweaver Mentor

Agent Purpose and Identity:
1. Teach others to write Loom modules.
2. Friendly but schema-obsessed.

I. Whatever Module
"""

def test_parse_outline_header_minimal_numbered():
    program = parse_outline_header(SAMPLE)
    assert program["type"] == "Program"
    assert program["name"] == "Loomweaver Mentor"
    assert program["purposeAndIdentity"] == [
        "Teach others to write Loom modules.",
        "Friendly but schema-obsessed."
    ]
    assert program["modules"] == []
    assert program["version"] == "1.0"
    assert program["astVersion"] == "2.1.0"
