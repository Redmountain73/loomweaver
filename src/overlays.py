#!/usr/bin/env python3
"""
SPEC-003 Overlay loader + expander.

- Loads compile-time overlay packs (JSON) from agents/loomweaver/overlays.
- Always loads `verbs.core.json`.
- Optionally loads packs listed in `overlay_names` (e.g., ["research"]).
- Expands author verbs into canonical IR verbs before execution.
- Records receipt lineage for each expansion step.

This module is intentionally independent of the existing runtime so we can
iterate without breaking SPEC-002. Later we can hook this into the compiler.
"""

from __future__ import annotations
import copy
import json
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

OVERLAY_DIR = os.path.join("agents", "loomweaver", "overlays")

# Canonical IR verbs we allow to be produced by overlays
CANONICAL_VERBS = {"Make", "Show", "Return", "Ask", "Choose", "Repeat", "Call"}

# ----------------------------
# Errors
# ----------------------------

class OverlayError(Exception):
    pass

class UnknownVerbError(OverlayError):
    def __init__(self, verb: str):
        super().__init__(f"Unknown verb (no overlay mapping): {verb}")
        self.verb = verb

class CapabilityError(OverlayError):
    def __init__(self, verb: str, missing: List[str]):
        super().__init__(f"Capabilities required by '{verb}' not granted: {', '.join(missing)}")
        self.verb = verb
        self.missing = missing

# ----------------------------
# Data classes
# ----------------------------

@dataclass
class OverlayMapping:
    overlay: str
    version: str
    verb: str               # raw author verb, e.g., "Summarize"
    mappedVerb: Any         # str or list[str]
    mapping: Dict[str, Any] # full mapping object from JSON
    capabilities: List[str] = field(default_factory=list)

@dataclass
class ReceiptLineage:
    rawVerb: str
    mappedVerb: Any                       # str or list[str] or None
    overlayDomain: Optional[str] = None
    overlayVersion: Optional[str] = None
    capabilityCheck: str = "n/a"          # "pass" | "warn" | "fail" | "n/a"
    notes: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rawVerb": self.rawVerb,
            "mappedVerb": self.mappedVerb,
            "overlayDomain": self.overlayDomain,
            "overlayVersion": self.overlayVersion,
            "capabilityCheck": self.capabilityCheck,
            "notes": self.notes,
        }

@dataclass
class ExpandOptions:
    overlay_names: List[str] = field(default_factory=list)  # e.g., ["research"]
    no_unknown_verbs: bool = False
    enforce_capabilities: bool = False
    granted_capabilities: List[str] = field(default_factory=list)  # e.g., ["network:fetch"]

# ----------------------------
# Loader
# ----------------------------

def _load_overlay_file(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def _resolve_overlay_path(name: str) -> str:
    # name "core" -> verbs.core.json; name "research" -> verbs.research.json
    return os.path.join(OVERLAY_DIR, f"verbs.{name}.json")

def load_overlays(overlay_names: List[str]) -> Dict[str, OverlayMapping]:
    """
    Load core + any requested overlays. Last-loaded wins for conflicts (warn here if desired).
    Returns a mapping: rawVerb -> OverlayMapping
    """
    merged: Dict[str, OverlayMapping] = {}

    def _merge_pack(pack: Dict[str, Any]):
        overlay = str(pack.get("overlay"))
        version = str(pack.get("version"))
        verbs = pack.get("verbs", {})
        for raw, body in verbs.items():
            mverb = body.get("mappedVerb")
            capabilities = list(body.get("capabilities", []))
            # Normalize: mappedVerb can be str or list[str]
            if isinstance(mverb, list):
                norm = list(mverb)
            else:
                norm = str(mverb) if mverb is not None else None
            merged[raw] = OverlayMapping(
                overlay=overlay,
                version=version,
                verb=raw,
                mappedVerb=norm,
                mapping=body,
                capabilities=capabilities
            )

    # Always core first
    core_path = _resolve_overlay_path("core")
    if not os.path.isfile(core_path):
        raise OverlayError(f"Missing required core overlay: {core_path}")
    _merge_pack(_load_overlay_file(core_path))

    # Then optional packs, last one wins
    for name in overlay_names:
        path = _resolve_overlay_path(name)
        if not os.path.isfile(path):
            raise OverlayError(f"Requested overlay '{name}' not found at {path}")
        _merge_pack(_load_overlay_file(path))

    return merged

# ----------------------------
# Expansion
# ----------------------------

def _capability_delta(required: List[str], granted: List[str]) -> List[str]:
    required_set = set(required or [])
    granted_set = set(granted or [])
    return sorted(list(required_set - granted_set))


def _annotate_step(step: Dict[str, Any], lineage: ReceiptLineage) -> Dict[str, Any]:
    """Return a deep-copied step annotated with lineage metadata."""
    annotated = copy.deepcopy(step)
    lineage_dict = lineage.to_dict()
    # Remove helper notes unless explicitly needed downstream (kept for debugging).
    lineage_payload = {k: v for k, v in lineage_dict.items() if k != "notes"}
    # Ensure args dict exists for interpreter normalization downstream.
    args = dict(annotated.get("args") or {})
    annotated["args"] = args
    annotated.update(lineage_payload)
    return annotated

def expand_steps(
    steps: List[Dict[str, Any]],
    overlays: Dict[str, OverlayMapping],
    opts: ExpandOptions
) -> Tuple[List[Dict[str, Any]], List[ReceiptLineage], List[str]]:
    """
    Expand a list of author steps (AST-ish) to canonical steps.
    Each input step: {"verb": "Summarize", "args": {...}}
    Returns (canonical_steps, receipt_lineage, warnings)
    """
    canonical: List[Dict[str, Any]] = []
    lineage: List[ReceiptLineage] = []
    warns: List[str] = []

    for step in steps:
        raw = step.get("verb")
        args = step.get("args", {}) or {}

        mapping = overlays.get(raw)
        if not mapping:
            if raw in CANONICAL_VERBS:
                canon_step = copy.deepcopy(step)
                canon_step["verb"] = raw
                canon_step["args"] = dict(args)
                lineage_entry = ReceiptLineage(
                    rawVerb=raw,
                    mappedVerb=raw,
                    overlayDomain=None,
                    overlayVersion=None,
                    capabilityCheck="n/a",
                    notes="canonical-pass-through"
                )
                canonical.append(_annotate_step(canon_step, lineage_entry))
                lineage.append(lineage_entry)
                continue

            msg = f"Unknown verb: {raw}"
            if opts.no_unknown_verbs:
                raise UnknownVerbError(raw)
            warns.append(msg)
            lineage_entry = ReceiptLineage(
                rawVerb=raw,
                mappedVerb=None,
                capabilityCheck="n/a",
                notes="No overlay mapping; left as-is."
            )
            canonical.append(_annotate_step(step, lineage_entry))
            lineage.append(lineage_entry)
            continue

        # Capability check
        missing = _capability_delta(mapping.capabilities, opts.granted_capabilities)
        cap_status = "pass"
        if mapping.capabilities and missing:
            cap_status = "fail" if opts.enforce_capabilities else "warn"
            if opts.enforce_capabilities:
                # fail fast
                raise CapabilityError(raw, missing)
            warns.append(f"Verb '{raw}' requires capabilities: {', '.join(mapping.capabilities)} "
                         f"(missing: {', '.join(missing)})")

        # Expand
        annotated_steps: List[Dict[str, Any]] = []

        if isinstance(mapping.mappedVerb, list):
            # pipelined multi-verb mapping
            pipeline = mapping.mapping.get("pipeline", [])
            # Fallback: generate simple steps from mappedVerb list if no pipeline provided
            if not pipeline:
                for mv in mapping.mappedVerb:
                    if mv not in CANONICAL_VERBS:
                        raise OverlayError(f"Overlay mapped to non-canonical verb: {mv}")
                    annotated_steps.append({"verb": mv, "args": dict(args)})
            else:
                for stage in pipeline:
                    # stage like { "Make": {"op": "format.compose"} }
                    if not isinstance(stage, dict) or len(stage) != 1:
                        raise OverlayError(f"Invalid pipeline stage in overlay for {raw}: {stage}")
                    mv, margs = next(iter(stage.items()))
                    if mv not in CANONICAL_VERBS:
                        raise OverlayError(f"Overlay mapped to non-canonical verb: {mv}")
                    stage_args = dict(margs or {})
                    # Merge incoming args (author args win)
                    merged_args = {**stage_args, **args}
                    annotated_steps.append({"verb": mv, "args": merged_args})
        else:
            mv = mapping.mappedVerb
            if mv not in CANONICAL_VERBS:
                raise OverlayError(f"Overlay mapped to non-canonical verb: {mv}")
            # copy mapping defaults
            defaults = {k: v for k, v in mapping.mapping.items()
                        if k not in ("mappedVerb", "notes", "pipeline", "capabilities")}
            merged_args = {**defaults, **args}
            annotated_steps.append({"verb": mv, "args": merged_args})

        lineage_entry = ReceiptLineage(
            rawVerb=raw,
            mappedVerb=mapping.mappedVerb,
            overlayDomain=mapping.overlay,
            overlayVersion=mapping.version,
            capabilityCheck=cap_status
        )
        lineage.append(lineage_entry)
        for st in annotated_steps:
            canonical.append(_annotate_step(st, lineage_entry))

    return canonical, lineage, warns


def expand_module_ast(
    module: Dict[str, Any],
    overlays: Dict[str, OverlayMapping],
    opts: ExpandOptions
) -> Tuple[Dict[str, Any], List[str]]:
    """Expand an author module dict into canonical verbs recursively."""

    warnings: List[str] = []

    def _expand_steps(step_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        canon, _lineage, warns = expand_steps(step_list, overlays, opts)
        warnings.extend(warns)
        return [_expand_nested(step) for step in canon]

    def _expand_nested(step: Dict[str, Any]) -> Dict[str, Any]:
        step = copy.deepcopy(step)
        args = step.get("args") or {}
        verb = step.get("verb")

        if verb == "Choose":
            branches = args.get("branches")
            if isinstance(branches, list):
                new_branches = []
                for branch in branches:
                    branch_copy = copy.deepcopy(branch)
                    branch_steps = branch_copy.get("steps") or []
                    branch_copy["steps"] = _expand_steps(branch_steps)
                    new_branches.append(branch_copy)
                args["branches"] = new_branches

        if verb == "Repeat":
            block = args.get("block")
            if block is None and isinstance(step.get("block"), dict):
                block = step.get("block")
            if block is None and isinstance(step.get("block"), list):
                block = {"steps": step.get("block")}
            if isinstance(block, dict):
                block_copy = copy.deepcopy(block)
                block_copy["steps"] = _expand_steps(block_copy.get("steps") or [])
                args["block"] = block_copy
            elif isinstance(block, list):
                args["block"] = {"steps": _expand_steps(block)}
            step.pop("block", None)

        # Generic nested steps handler if a verb embeds sub-steps directly in args
        if isinstance(args.get("steps"), list):
            args["steps"] = _expand_steps(args.get("steps") or [])

        step["args"] = args
        return step

    def _apply(node: Dict[str, Any]) -> Dict[str, Any]:
        node_copy = copy.deepcopy(node)
        if isinstance(node_copy.get("flow"), list):
            node_copy["flow"] = _expand_steps(node_copy.get("flow") or [])
        if isinstance(node_copy.get("steps"), list) and "flow" not in node_copy:
            node_copy["steps"] = _expand_steps(node_copy.get("steps") or [])
        return node_copy

    if module is None:
        return module, warnings

    if isinstance(module.get("module"), dict):
        expanded_inner = _apply(module.get("module"))
        outer = copy.deepcopy(module)
        outer["module"] = expanded_inner
        return outer, warnings

    return _apply(module), warnings


def expand_modules_doc(
    doc: Dict[str, Any],
    overlays: Dict[str, OverlayMapping],
    opts: ExpandOptions
) -> Tuple[Dict[str, Any], List[str]]:
    """Expand every module inside a modules document."""

    warnings: List[str] = []
    out = copy.deepcopy(doc)
    modules = out.get("modules")
    if isinstance(modules, list):
        expanded_modules = []
        for module in modules:
            expanded, warns = expand_module_ast(module, overlays, opts)
            warnings.extend(warns)
            expanded_modules.append(expanded)
        out["modules"] = expanded_modules
    return out, warnings

# ----------------------------
# Helper op: xml.firstTitle (for fixture-backed test)
# ----------------------------

def xml_first_title(atom_xml_path: str) -> Optional[str]:
    """
    Minimal helper to support the Summarize→Call(op=xml.firstTitle) test.
    Reads an Atom XML file and returns the first <entry><title> text.
    """
    import xml.etree.ElementTree as ET
    if not os.path.isfile(atom_xml_path):
        raise FileNotFoundError(atom_xml_path)
    ns = {"a": "http://www.w3.org/2005/Atom"}
    tree = ET.parse(atom_xml_path)
    root = tree.getroot()
    first_title = root.find("./a:entry/a:title", ns)
    return first_title.text if first_title is not None else None
