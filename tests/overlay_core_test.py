import os
import json
import pytest

from src.overlays import (
    load_overlays, expand_steps, ExpandOptions,
    xml_first_title, UnknownVerbError, CapabilityError
)

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
WITH_SPACES_ROOT = os.path.basename(REPO_ROOT)  # just to remind us paths may have spaces

AGENTS_DIR = os.path.join(REPO_ROOT, "agents", "loomweaver")
OVERLAYS_DIR = os.path.join(AGENTS_DIR, "overlays")
FIXTURE_XML = os.path.join(REPO_ROOT, "fixtures", "arxiv.atom.xml")

def test_setup_files_exist():
    assert os.path.isfile(os.path.join(OVERLAYS_DIR, "verbs.core.json"))
    assert os.path.isfile(os.path.join(OVERLAYS_DIR, "verbs.research.json"))
    assert os.path.isfile(FIXTURE_XML)

def test_query_maps_to_call_core_only():
    overlays = load_overlays([])
    steps = [{"verb": "Query", "args": {"resource": "foo"}}]
    canon, receipts, warns = expand_steps(steps, overlays, ExpandOptions())
    assert len(canon) == 1
    assert canon[0]["verb"] == "Call"
    assert canon[0]["args"]["resource"] == "foo"
    assert len(receipts) == 1
    r = receipts[0]
    assert r.rawVerb == "Query"
    assert r.overlayDomain == "core"
    assert r.overlayVersion == "0.1.0"
    assert r.capabilityCheck in ("n/a", "pass", "warn")

def test_summarize_maps_to_call_xml_first_title_fixture_backed():
    overlays = load_overlays([])
    steps = [{"verb": "Summarize", "args": {"path": FIXTURE_XML}}]
    canon, receipts, warns = expand_steps(steps, overlays, ExpandOptions())
    assert len(canon) == 1
    assert canon[0]["verb"] == "Call"
    # expansion should carry op=xml.firstTitle
    assert canon[0]["args"].get("op") == "xml.firstTitle"
    # prove the op is meaningful using the fixture
    title = xml_first_title(FIXTURE_XML)
    assert isinstance(title, str) and len(title) > 0
    assert "Quantum Kittens" in title

def test_report_maps_to_make_show_pipeline():
    overlays = load_overlays([])
    steps = [{"verb": "Report", "args": {"text": "hi"}}]
    canon, receipts, warns = expand_steps(steps, overlays, ExpandOptions())
    # Expect a two-step pipeline: Make(...), Show(stdout)
    assert [s["verb"] for s in canon] == ["Make", "Show"]
    assert canon[0]["args"].get("op") == "format.compose"
    assert canon[1]["args"].get("sink") == "stdout"
    assert receipts[0].mappedVerb == ["Make", "Show"]

def test_unknown_verb_warns_by_default_passes_through():
    overlays = load_overlays([])
    steps = [{"verb": "Teleport", "args": {"to": "Orion"}}]
    canon, receipts, warns = expand_steps(steps, overlays, ExpandOptions())
    # Pass-through since we didn't set no_unknown_verbs
    assert canon[0]["verb"] == "Teleport"
    assert any("Unknown verb" in w for w in warns)
    assert receipts[0].mappedVerb is None

def test_unknown_verb_errors_when_flag_set():
    overlays = load_overlays([])
    steps = [{"verb": "Teleport", "args": {"to": "Orion"}}]
    with pytest.raises(UnknownVerbError):
        expand_steps(steps, overlays, ExpandOptions(no_unknown_verbs=True))

def test_capabilities_warning_by_default_and_error_with_flag():
    # research overlay declares capabilities for "Research"
    overlays = load_overlays(["research"])
    steps = [{"verb": "Research", "args": {"query": "cats"}}]

    # Default: warn (not enforcing); should not raise
    canon, receipts, warns = expand_steps(steps, overlays, ExpandOptions())
    assert len(warns) >= 1
    assert any("requires capabilities" in w for w in warns)
    assert receipts[0].capabilityCheck in ("warn", "fail")  # warn expected

    # Enforced capabilities with none granted -> error
    with pytest.raises(CapabilityError):
        expand_steps(steps, overlays, ExpandOptions(enforce_capabilities=True))

    # Enforced but granted -> OK
    canon2, receipts2, warns2 = expand_steps(
        steps, overlays,
        ExpandOptions(enforce_capabilities=True, granted_capabilities=["network:fetch"])
    )
    assert len(canon2) == 1
    assert receipts2[0].capabilityCheck == "pass"
