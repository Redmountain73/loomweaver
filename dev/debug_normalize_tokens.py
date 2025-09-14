import sys, re, json
from pathlib import Path
import os

# ---- make 'src' importable no matter where we run this file from ----
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src.outline_normalizer import normalize_loom_outline
from src.tokenizer import tokenize

def visible(s: str) -> str:
    return s.replace(" ", "·").replace("\t", "⇥")

def main(p: str):
    text = Path(p).read_text(encoding="utf-8")
    # Normalize only for Outline-style (I./A./D./F.)
    if re.search(r'^\s*[A-Z]\.\s', text, flags=re.M):
        text = normalize_loom_outline(text)

    print("=== Normalized text (with visible spaces) ===")
    for i, line in enumerate(text.splitlines(), 1):
        print(f"{i:02d}  {visible(line)}")

    print("\n=== Tokens ===")
    toks = tokenize(text)
    for t in toks:
        print(json.dumps(t, ensure_ascii=False))

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: python dev/debug_normalize_tokens.py <module.loom>")
        sys.exit(2)
    main(sys.argv[1])
