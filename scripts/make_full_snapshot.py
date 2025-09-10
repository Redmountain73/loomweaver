# scripts/make_full_snapshot.py
# Pack a full repo snapshot (minus junk) and emit a manifest.
import os, sys, time, zipfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

EXCLUDE_DIRS   = {".venv", ".pytest_cache", "__pycache__", ".git"}
EXCLUDE_FILES  = {".DS_Store"}
EXCLUDE_SUFFIX = {".pyc"}

def should_exclude(rel_path: str) -> bool:
    p = rel_path.replace("\\", "/")
    parts = p.split("/")
    # Exclude if any parent directory is in EXCLUDE_DIRS
    if any(part in EXCLUDE_DIRS for part in parts[:-1]):
        return True
    name = parts[-1]
    if name in EXCLUDE_FILES:
        return True
    if any(name.endswith(sfx) for sfx in EXCLUDE_SUFFIX):
        return True
    return False

def gather_files():
    files = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        rel_dir = os.path.relpath(dirpath, ROOT)
        if rel_dir == ".":
            rel_dir = ""
        # prune excluded dirs
        dirnames[:] = [d for d in sorted(dirnames) if d not in EXCLUDE_DIRS and not d.startswith(".git")]
        for f in sorted(filenames):
            rel = os.path.join(rel_dir, f) if rel_dir else f
            if not should_exclude(rel):
                files.append(rel)
    return sorted(files)

def main(outdir=".", name="loomweaver_full"):
    os.makedirs(outdir, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    zip_path = os.path.join(outdir, f"{name}-{stamp}.zip")

    files = gather_files()
    manifest = "SNAPSHOT MANIFEST\n" + "\n".join(files) + "\n"
    # write manifest next to zip and include inside zip
    with open(os.path.join(ROOT, "snapshot_manifest.txt"), "w", encoding="utf-8") as mf:
        mf.write(manifest)

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for rel in files:
            z.write(os.path.join(ROOT, rel), rel)
        z.writestr("snapshot_manifest.txt", manifest)

    print(f"Wrote {zip_path}")
    print(f"Included {len(files)} files. Manifest: snapshot_manifest.txt")

if __name__ == "__main__":
    outdir = sys.argv[1] if len(sys.argv) > 1 else "."
    name   = sys.argv[2] if len(sys.argv) > 2 else "loomweaver_full"
    main(outdir, name)
