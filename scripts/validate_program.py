# scripts/validate_program.py 
# Validate Program + Modules (+ optional Capabilities) using LOCAL, REF-FREE schemas.
# - Normalizes outline shorthands.
# - Embeds module schema into program schema (no network).
# - Warns on name normalization & collisions.
# - Exit policy:
#     default: exit 0 unless schema/logic errors
#     --strict: same as default (errors -> nonzero)
#     --warnings-as-errors: warnings ALSO cause nonzero
from __future__ import annotations
import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List

# Make repo root importable; import from src as a package
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.names import normalize_module_slug  # noqa: E402
from src.overlays import load_overlays, ExpandOptions, expand_modules_doc  # noqa: E402

try:
    import jsonschema
    from jsonschema import Draft202012Validator
except Exception:
    jsonschema = None
    Draft202012Validator = None

SCHEMAS = ROOT / "Schemas"


SUCCESS_CRITERIA_PROP = {"type": "array", "items": {"type": "string"}, "default": []}
EXAMPLES_PROP = {
    "type": "array",
    "items": {"type": "object", "properties": {"description": {"type": "string"}}, "additionalProperties": True},
    "default": []
}

def load_json(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))

def _scrub_ids(schema: dict) -> dict:
    def walk(node):
        if isinstance(node, dict):
            node = dict(node)
            node.pop("$id", None)
            for k, v in list(node.items()):
                node[k] = walk(v)
            return node
        if isinstance(node, list):
            return [walk(v) for v in node]
        return node
    return walk(schema)

def _rewrite_internal_refs_to_embedded(schema: dict) -> dict:
    # In the MODULE schema: '#/...' -> '#/$defs/Module/...'
    def walk(node):
        if isinstance(node, dict):
            out = {}
            for k, v in node.items():
                if k == "$ref" and isinstance(v, str) and v.startswith("#/"):
                    out[k] = v.replace("#/", "#/$defs/Module/")
                else:
                    out[k] = walk(v)
            return out
        if isinstance(node, list):
            return [walk(v) for v in node]
        return node
    return walk(schema)

def _rewrite_prog_external_refs(schema: dict) -> dict:
    # In the PROGRAM schema: any ref to 'loom-module.schema.json[#fragment]' -> '#/$defs/Module[/fragment]'
    def rewrite_ref(ref: str) -> str:
        if "loom-module.schema.json" not in ref:
            return ref
        frag = ""
        if "#" in ref:
            _, frag = ref.split("#", 1)
            frag = "/" + frag.lstrip("/") if frag else ""
        return "#/$defs/Module" + frag
    def walk(node):
        if isinstance(node, dict):
            out = {}
            for k, v in node.items():
                if k == "$ref" and isinstance(v, str):
                    out[k] = rewrite_ref(v)
                else:
                    out[k] = walk(v)
            return out
        if isinstance(node, list):
            return [walk(v) for v in node]
        return node
    return walk(schema)

def load_module_schema_with_overlay() -> dict:
    mod = load_json(SCHEMAS / "loom-module.schema.json")
    props = mod.setdefault("properties", {})
    props.setdefault("successCriteria", SUCCESS_CRITERIA_PROP)
    props.setdefault("examples", EXAMPLES_PROP)
    # Temporarily allow spaces in authoring names
    name_prop = props.get("name")
    if isinstance(name_prop, dict):
        pat = name_prop.get("pattern")
        if isinstance(pat, str):
            name_prop["pattern"] = (
                pat.replace("[A-Za-z0-9_\\-]{0,127}", "[A-Za-z0-9_\\- ]{0,127}")
                   .replace("[A-Za-z0-9_\\\\-]{0,127}", "[A-Za-z0-9_\\\\- ]{0,127}")
            )
    mod = _scrub_ids(mod)
    mod = _rewrite_internal_refs_to_embedded(mod)
    return mod

_SHORT = re.compile(r'^\s*([A-Za-z_][A-Za-z0-9_]*)\s*\(([^)]+)\)\s*$')
def _canonicalize_io_shorthand(seq: list) -> list:
    out = []
    for item in seq or []:
        if isinstance(item, str):
            m = _SHORT.match(item)
            if m: out.append({"name": m.group(1), "resultType": m.group(2)})
            else: out.append({"name": item})
        elif isinstance(item, dict):
            out.append(item)
    return out

def _normalize_module_obj(m: dict) -> dict:
    m = dict(m or {})
    if isinstance(m.get("inputs"), list):
        m["inputs"] = _canonicalize_io_shorthand(m["inputs"])
    if isinstance(m.get("outputs"), list):
        m["outputs"] = _canonicalize_io_shorthand(m["outputs"])
    if isinstance(m.get("examples"), list):
        m["examples"] = [{"description": e} if isinstance(e, str) else e for e in m["examples"]]
    return m

def _normalize_combined_instance(combined: dict) -> dict:
    combined = dict(combined or {})
    combined["modules"] = [ _normalize_module_obj(m) for m in (combined.get("modules") or []) ]
    return combined

def main(argv: List[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--program", required=True, help="Program JSON")
    ap.add_argument("--modules", required=True, help="Modules JSON")
    ap.add_argument("--capabilities", required=False, help="Capabilities JSON")
    ap.add_argument("--strict", action="store_true", help="nonzero exit on schema/logic errors")
    ap.add_argument("--warnings-as-errors", action="store_true", help="treat warnings as errors (nonzero exit)")
    ap.add_argument("--overlay", action="append", default=[], help="Overlay pack to include (repeatable)")
    ap.add_argument("--no-unknown-verbs", action="store_true", help="Error on verbs without overlay mapping")
    ap.add_argument("--enforce-capabilities", action="store_true", help="Block missing overlay capabilities")
    args = ap.parse_args(argv)

    infos: list[str] = []
    warnings: list[str] = []
    errors: list[str] = []

    # Load input JSON
    try:
        program = load_json(Path(args.program))
        modules = load_json(Path(args.modules))
        cap_path = Path(args.capabilities) if args.capabilities else None
        caps = load_json(cap_path) if (cap_path and cap_path.exists()) else None
    except Exception as e:
        print(f"Failed to read input JSON: {e}")
        return 2

    overlay_warnings: List[str] = []
    try:
        overlays = load_overlays(args.overlay)
        expand_opts = ExpandOptions(
            overlay_names=list(args.overlay or []),
            no_unknown_verbs=bool(args.no_unknown_verbs),
            enforce_capabilities=bool(args.enforce_capabilities),
        )
        modules, overlay_warnings = expand_modules_doc(modules, overlays, expand_opts)
    except Exception as e:
        errors.append(f"Overlay expansion failed: {e}")

    # Combine + normalize
    combined = dict(program)
    combined["modules"] = (modules.get("modules") or [])
    combined = _normalize_combined_instance(combined)

    # Name normalization notes
    try:
        mods = combined.get("modules") or []
        norm_to_raws: Dict[str, List[str]] = {}
        for m in mods:
            raw = (m.get("name") or "").strip()
            if not raw: continue
            norm = normalize_module_slug(raw)
            if norm != raw:
                infos.append(f"[name-normalization] Module '{raw}' normalizes to '{norm}'")
            norm_to_raws.setdefault(norm, []).append(raw)
        for norm, raws in norm_to_raws.items():
            if len(raws) > 1:
                pairs = ", ".join(sorted(set(raws)))
                warnings.append(f"[name-collision] {pairs} -> '{norm}'")
    except Exception as e:
        warnings.append(f"[name-normalization] internal warning: {e}")

    # Cheap guards
    if not combined.get("name"):
        errors.append("Program.name missing")
    if not combined.get("modules"):
        errors.append("Program.modules empty (combined)")

    for warn in overlay_warnings:
        warnings.append(f"[overlay] {warn}")

    # Schema validation (offline)
    if jsonschema is None or Draft202012Validator is None:
        infos.append("jsonschema not installed; run: pip install jsonschema")
    else:
        try:
            mod_schema = load_module_schema_with_overlay()
            prog_schema = load_json(SCHEMAS / "loom-program.schema.json")
            prog_schema = _scrub_ids(prog_schema)
            prog_schema["$defs"] = (prog_schema.get("$defs") or {})
            prog_schema["$defs"]["Module"] = mod_schema
            prog_schema = _rewrite_prog_external_refs(prog_schema)
            Draft202012Validator(prog_schema).validate(combined)
            if caps:
                cap_schema = load_json(SCHEMAS / "loom-capabilities.schema.json")
                cap_schema = _scrub_ids(cap_schema)
                Draft202012Validator(cap_schema).validate(caps)
        except Exception as e:
            errors.append(f"Schema validation failed: {e}")

    # Report
    if errors or warnings or infos:
        print("VALIDATION:", "ERRORS" if errors else "WARNINGS/INFO")
        for e in errors:   print(" -", e)
        for w in warnings: print(" -", w)
        for i in infos:    print(" -", i)

    exit_nonzero = bool(errors) or (args.warnings_as_errors and (warnings or infos))
    if (args.strict and bool(errors)) or exit_nonzero:
        return 1
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
