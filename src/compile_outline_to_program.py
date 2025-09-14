# src/compile_outline_to_program.py
# ELI5:
# 1) Read the agent cover (name + who it is) → Program JSON.
# 2) Read module sections → .program.modules.outline.json.
# 3) Compile simple Flow lines → .modules.ast.json.
from __future__ import annotations

import json
import os
import re
import sys
from typing import Dict, List, Optional, Tuple

# ---------- Agent header parsing ----------

AGENT_NAME_RE = re.compile(r"^\s*Agent\s+Name:\s*(?P<name>.+?)\s*$", re.IGNORECASE)
# Tolerant: "Agent Purpose and Identity" or "Agent Purpose & Identity", colon optional
AGENT_PI_START_RE = re.compile(r"^\s*Agent\s+Purpose\s*(?:and|&)\s*Identity\s*:?\s*$", re.IGNORECASE)

# IMPORTANT: Module header = Roman numeral + name that CONTAINS the word "Module"
MODULE_START_RE = re.compile(
    r"^\s*(?P<num>[IVXLCM]+)\.\s+(?P<name>.+?\bModule)\s*$",
    re.IGNORECASE,
)

# Section headers inside a module: "A. ...", "B) ...", optional trailing colon
SECTION_RE = re.compile(r"^\s*([A-Z])\s*[\.\)]\s+(?P<title>.+?)\s*:?\s*$")

# Strip leading list markers: "- ", "* ", "1. ", "1) "
LEAD_ENUM_RE = re.compile(r"^\s*(?:[-*]|\d+[.)])\s*")


def _strip_enum_prefix(s: str) -> str:
    return LEAD_ENUM_RE.sub("", s.strip())


def parse_outline_header(text: str) -> Dict:
    lines = text.splitlines()
    name: Optional[str] = None
    purpose_and_identity: List[str] = []

    i, n = 0, len(lines)

    # 1) Agent Name
    while i < n:
        m = AGENT_NAME_RE.match(lines[i])
        if m:
            name = m.group("name").strip()
            i += 1
            break
        i += 1

    # 2) Agent Purpose and Identity (collect until first module header or EOF)
    while i < n and not AGENT_PI_START_RE.match(lines[i]):
        i += 1

    if i < n and AGENT_PI_START_RE.match(lines[i]):
        i += 1  # skip the header line
        while i < n:
            line = lines[i].rstrip()
            if MODULE_START_RE.match(line):  # real module header only
                break
            if SECTION_RE.match(line):  # defensive at agent level
                break
            stripped = line.strip()
            if stripped:
                purpose_and_identity.append(_strip_enum_prefix(stripped))
            i += 1

    if not name:
        raise ValueError("Agent Name not found in outline.")
    if not purpose_and_identity:
        raise ValueError("Agent Purpose and Identity is empty or missing.")

    return {
        "type": "Program",
        "name": name,
        "purposeAndIdentity": purpose_and_identity,
        "modules": [],
        "version": "1.0",
        "astVersion": "2.1.0",
    }


# ---------- Module parsing (outline → buckets) ----------

def _collect_list(lines: List[str], start: int, stop_pred) -> Tuple[List[str], int]:
    """Collect enumerated/bulleted OR plain non-empty lines until stop_pred or EOF."""
    out: List[str] = []
    i, n = start, len(lines)
    while i < n and not stop_pred(lines[i]):
        s = lines[i].strip()
        if s:
            out.append(_strip_enum_prefix(s))
        i += 1
    return out, i


def parse_modules(text: str) -> List[Dict]:
    lines = text.splitlines()
    i, n = 0, len(lines)
    mods: List[Dict] = []

    def at_module(idx: int) -> bool:
        return idx < n and MODULE_START_RE.match(lines[idx]) is not None

    while i < n:
        m = MODULE_START_RE.match(lines[i])
        if not m:
            i += 1
            continue

        mod_name = m.group("name").strip()
        i += 1

        purpose_and_identity: List[str] = []
        inputs: List[str] = []
        outputs: List[str] = []
        flow: List[str] = []
        tests: List[str] = []
        success_criteria: List[str] = []
        version: Optional[str] = None
        ast_version: Optional[str] = None
        examples: List[str] = []

        # Walk sections until next module or EOF
        while i < n and not at_module(i):
            sec = SECTION_RE.match(lines[i])
            if not sec:
                i += 1
                continue

            title_raw = sec.group("title").strip()
            title = title_raw.lower()
            i += 1  # move past section header

            # list sections end at next section or next module
            def stop_here(line: str) -> bool:
                return SECTION_RE.match(line) is not None or MODULE_START_RE.match(line) is not None

            # Inline values support (e.g., "G. Version: 1.0" on the same header line)
            m_ver = re.match(r"(?i)^version\s*:\s*(.+)$", title_raw)
            m_ast = re.match(r"(?i)^ast\s*version\s*:\s*(.+)$", title_raw) or re.match(r"(?i)^astversion\s*:\s*(.+)$", title_raw)
            if m_ver:
                version = m_ver.group(1).strip()
                continue
            if m_ast:
                ast_version = m_ast.group(1).strip()
                continue

            # Also allow single inline item for inputs/outputs/examples/tests/flow
            def maybe_inline_item(into: List[str]) -> bool:
                mm = re.match(r"^(.*?):\s*(.+)$", title_raw)
                if mm:
                    key, val = mm.group(1).strip().lower(), mm.group(2).strip()
                    if key.startswith(("inputs", "outputs", "examples", "tests", "flow")) and val:
                        into.append(val)
                        return True
                return False

            if title.startswith("purpose and identity"):
                purpose_and_identity, i = _collect_list(lines, i, stop_here)
                continue
            if title.startswith("inputs"):
                if not maybe_inline_item(inputs):
                    inputs, i = _collect_list(lines, i, stop_here)
                continue
            if title.startswith("outputs"):
                if not maybe_inline_item(outputs):
                    outputs, i = _collect_list(lines, i, stop_here)
                continue
            if title.startswith("flow"):
                if not maybe_inline_item(flow):
                    flow, i = _collect_list(lines, i, stop_here)
                continue
            if title.startswith("tests"):
                if not maybe_inline_item(tests):
                    tests, i = _collect_list(lines, i, stop_here)
                continue
            if title.startswith("success criteria"):
                success_criteria, i = _collect_list(lines, i, stop_here)
                continue
            if title.startswith("examples"):
                if not maybe_inline_item(examples):
                    examples, i = _collect_list(lines, i, stop_here)
                continue
            if title.startswith("version"):
                if i < n and not stop_here(lines[i]) and lines[i].strip():
                    version = _strip_enum_prefix(lines[i].strip())
                    version = re.sub(r"(?i)^version:\s*", "", version).strip()
                    i += 1
                continue
            if title.startswith("astversion") or title.startswith("ast version"):
                if i < n and not stop_here(lines[i]) and lines[i].strip():
                    ast_version = _strip_enum_prefix(lines[i].strip())
                    ast_version = re.sub(r"(?i)^ast\s*version:\s*", "", ast_version).strip()
                    i += 1
                continue

            # Unknown section: skip until next section/module
            while i < n and not stop_here(lines[i]):
                i += 1

        mods.append({
            "name": mod_name,
            "purposeAndIdentity": purpose_and_identity,
            "inputs": inputs,
            "outputs": outputs,
            "flowLines": flow,
            "tests": tests,
            "successCriteria": success_criteria,
            "version": version or "1.0",
            "astVersion": ast_version or "2.1.0",
            "examples": examples,
        })
    return mods

# ---------- Minimal NL → AST ----------

def _expr_from_text(s: str) -> Dict:
    s = s.strip()
    if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
        return {"type": "String", "value": s[1:-1]}
    if re.fullmatch(r"\d+(?:\.\d+)?", s):
        return {"type": "Number", "value": float(s) if "." in s else int(s)}
    if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_\.]*", s):
        return {"type": "Identifier", "name": s}
    if "name" in s.lower():
        return {"type": "Identifier", "name": "name"}
    return {"type": "String", "value": s}

def _parse_if_then_return(line: str):
    m = re.match(r"^\s*(if|when|unless)\s+(.+?)\s+then\s+return\s+(.+?)\s*$", line, flags=re.IGNORECASE)
    if not m:
        return None
    head, cond_text, ret_text = m.group(1).lower(), m.group(2).strip(), m.group(3).strip()
    # Prefer comparative normalizer if present
    triplet = None
    try:
        from nl_comparatives import parse_comparative
        triplet = parse_comparative(f"{head} {cond_text}")
    except Exception:
        pass
    if triplet:
        left, op, right = triplet
        pred = {"type": "Binary", "op": op, "left": {"type": "Identifier", "name": left}, "right": _expr_from_text(str(right))}
    else:
        if re.search(r"\bno\s+name\b", cond_text, flags=re.IGNORECASE):
            pred = {"type": "Binary", "op": "==", "left": {"type": "Identifier", "name": "name"}, "right": {"type": "String", "value": ""}}
        else:
            pred = {"type": "Identifier", "name": re.sub(r"[^A-Za-z0-9_\.]", "", cond_text) or "cond"}
        if head == "unless":
            pred = {"type": "Unary", "op": "NOT", "expr": pred}
    return pred, _expr_from_text(ret_text)

def compile_flow_lines(flow_lines: List[str]) -> List[Dict]:
    """
    Support:
      - make VAR say EXPR
      - return EXPR
      - if/when/unless COND then return EXPR
      - otherwise return EXPR            (on the next line)
      - multi-actions on one line: "... , then ..." or "... , and then ..."
    """
    steps: List[Dict] = []

    # 0) Expand multi-action lines (but NEVER split conditionals)
    expanded: List[str] = []
    split_re = re.compile(r",\s*(?:and\s+)?then\s+", flags=re.IGNORECASE)
    for raw in flow_lines:
        s = raw.strip()
        if not s:
            continue
        if re.match(r"^\s*(if|when|unless)\b", s, flags=re.IGNORECASE):
            expanded.append(s)  # conditionals handled as a unit
        else:
            parts = split_re.split(s)
            expanded.extend([p for p in (p.strip() for p in parts) if p])

    # 1) Compile each (now simple) action
    i, n = 0, len(expanded)
    while i < n:
        line = expanded[i]

        if re.match(r"^\s*(if|when|unless)\b", line, flags=re.IGNORECASE):
            maybe = _parse_if_then_return(line)
            if maybe:
                pred, then_ret = maybe
                otherwise_steps: List[Dict] = []
                if i + 1 < n:
                    nxt = expanded[i + 1]
                    m2 = re.match(r"^\s*otherwise\s+return\s+(.+?)\s*$", nxt, flags=re.IGNORECASE)
                    if m2:
                        otherwise_steps = [{"verb": "Return", "args": {"expr": _expr_from_text(m2.group(1))}}]
                        i += 1
                steps.append({
                    "verb": "Choose",
                    "args": {
                        "branches": [
                            {"when": pred, "steps": [{"verb": "Return", "args": {"expr": then_ret}}]},
                            *([{"otherwise": True, "steps": otherwise_steps}] if otherwise_steps else [])
                        ]
                    }
                })
                i += 1
                continue
            steps.append({"verb": "Show", "args": {"text": f"[unparsed condition] {line}"}})
            i += 1
            continue

        m_make = re.match(r"^\s*make\s+([A-Za-z_][A-Za-z0-9_]*)\s+say\s+(.+?)\s*$", line, flags=re.IGNORECASE)
        if m_make:
            var, rhs = m_make.group(1), m_make.group(2)
            steps.append({"verb": "Make", "args": {"var": var, "expr": _expr_from_text(rhs)}})
            i += 1
            continue

        m_ret = re.match(r"^\s*return\s+(.+?)\s*$", line, flags=re.IGNORECASE)
        if m_ret:
            steps.append({"verb": "Return", "args": {"expr": _expr_from_text(m_ret.group(1))}})
            i += 1
            continue

        steps.append({"verb": "Show", "args": {"text": line}})
        i += 1

    return steps

def compile_modules_to_ast(mods_outline: List[Dict]) -> List[Dict]:
    compiled: List[Dict] = []
    for m in mods_outline:
        steps = compile_flow_lines(m.get("flowLines", []))
        compiled.append({
            "type": "Module",
            "name": m["name"],
            "purpose": " ".join(m.get("purposeAndIdentity", [])),
            "inputs": m.get("inputs", []),
            "outputs": m.get("outputs", []),
            "flow": steps,
            "successCriteria": m.get("successCriteria", []),
            "version": m.get("version", "1.0"),
            "astVersion": m.get("astVersion", "2.1.0"),
            "examples": m.get("examples", []),
        })
    return compiled


# ---------- CLI ----------

def main(argv: List[str]) -> int:
    if len(argv) != 3:
        print("Usage: python -m compile_outline_to_program <input_outline.md> <output_program.json>")
        return 2
    in_path, out_path = argv[1], argv[2]
    if not os.path.exists(in_path):
        print(f"Input file not found: {in_path}")
        return 2

    text = open(in_path, "r", encoding="utf-8").read()
    program = parse_outline_header(text)
    modules_outline = parse_modules(text)

    # 1) Program JSON
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    open(out_path, "w", encoding="utf-8").write(json.dumps(program, indent=2, ensure_ascii=False))
    print(f"Wrote Program JSON → {out_path}")

    # 2) Modules outline JSON
    base, _ = os.path.splitext(out_path)
    outline_path = f"{base}.modules.outline.json"
    open(outline_path, "w", encoding="utf-8").write(json.dumps({"modules": modules_outline}, indent=2, ensure_ascii=False))
    print(f"Wrote Module Outline JSON → {outline_path}")

    # 3) Minimal AST JSON
    ast_path = os.path.join(os.path.dirname(out_path), os.path.basename(base).replace(".program", "") + ".modules.ast.json")
    open(ast_path, "w", encoding="utf-8").write(json.dumps({"modules": compile_modules_to_ast(modules_outline)}, indent=2, ensure_ascii=False))
    print(f"Wrote Module AST JSON → {ast_path}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
