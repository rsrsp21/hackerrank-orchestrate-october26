"""Build code.zip for submission (plan/phases/phase10.md).

    uv run python code/package.py [--out code.zip]

Includes README.md, pyproject.toml, uv.lock, .env.example, code/ and plan/. Excludes scratch caches
(code/cache/), bytecode, the local .env, the dataset, virtual environments, and nested archives. Entries are
written in sorted order with a fixed timestamp so the archive is reproducible. Fails if a forbidden file
would be included, then prints the contents.
"""

import argparse
import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INCLUDE_FILES = ["README.md", "pyproject.toml", "uv.lock", ".env.example"]
INCLUDE_DIRS = ["code", "plan"]
EXCLUDE = re.compile(r"(^|/)(__pycache__|\.pytest_cache|\.ruff_cache|\.venv|venv|node_modules)(/|$)|^code/cache/|\.pyc$")
FORBIDDEN = re.compile(r"(^|/)\.env$|^dataset/|\.(zip|tar|gz|tgz|7z|rar)$")
SECRET = re.compile(rb"AIza[0-9A-Za-z_-]{20,}|sk-[A-Za-z0-9]{20,}")
FIXED_TIME = (2026, 10, 25, 0, 0, 0)


def collect():
    files = [ROOT / f for f in INCLUDE_FILES if (ROOT / f).exists()]
    for d in INCLUDE_DIRS:
        files += [p for p in (ROOT / d).rglob("*") if p.is_file()]
    rel = sorted({p.relative_to(ROOT).as_posix() for p in files})
    return [r for r in rel if not EXCLUDE.search(r)]


def build(out):
    entries = collect()
    problems = [r for r in entries if FORBIDDEN.search(r)]
    problems += [r for r in entries if SECRET.search((ROOT / r).read_bytes())]
    if problems:
        sys.exit(f"refusing to package forbidden or secret-bearing files: {problems}")
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for rel in entries:
            info = zipfile.ZipInfo(rel, date_time=FIXED_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            zf.writestr(info, (ROOT / rel).read_bytes())
    return entries


def main():
    parser = argparse.ArgumentParser(description="Build code.zip")
    parser.add_argument("--out", default=str(ROOT / "code.zip"))
    args = parser.parse_args()
    entries = build(Path(args.out))
    size = Path(args.out).stat().st_size
    top = {}
    for e in entries:
        key = "/".join(e.split("/")[:2]) if e.count("/") else e
        top[key] = top.get(key, 0) + 1
    print(f"wrote {args.out}: {len(entries)} files, {size / 1024:.0f} KiB")
    for k, n in sorted(top.items()):
        print(f"  {n:4d}  {k}")


if __name__ == "__main__":
    main()
