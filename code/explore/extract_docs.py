"""Phase 1 task 1.5: extract text and tables from the PDF evidence.

Writes one Markdown file per PDF to code/cache/extracted/<file_id>.md (gitignored) and prints it.
pdfplumber is the primary extractor; pymupdf is the fallback when a page yields no text.
Images (PNG) are transcribed separately into code/cache/extracted/<file_id>.md by viewing them.
Run: uv run python code/explore/extract_docs.py
"""

import csv
from pathlib import Path

import pdfplumber
import pymupdf

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "dataset"
OUT = ROOT / "code" / "cache" / "extracted"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = {r["file_path"]: r for r in csv.DictReader(open(DATA / "evidence_files.csv", encoding="utf-8"))}
    for path in sorted((DATA / "evidence" / "documents").glob("*.pdf")):
        m = manifest[path.relative_to(DATA).as_posix()]
        lines = [f"# {m['file_id']} — {path.name}", f"captured_at: {m['captured_at']}  origin: {m['origin']}", ""]
        with pdfplumber.open(path) as pdf:
            meta = pdf.metadata
            lines.append(f"pdf metadata: { {k: v for k, v in meta.items() if k in ('Title', 'Author', 'Subject', 'CreationDate', 'Producer')} }")
            for i, page in enumerate(pdf.pages, 1):
                text = page.extract_text() or ""
                if not text.strip():
                    text = pymupdf.open(path)[i - 1].get_text()
                lines += [f"\n## page {i} (images on page: {len(page.images)})", text]
                for t in page.extract_tables():
                    lines.append("\nTABLE:")
                    lines += [" | ".join("" if c is None else str(c).replace("\n", " ") for c in row) for row in t]
        doc = "\n".join(lines)
        (OUT / f"{m['file_id']}.md").write_text(doc, encoding="utf-8")
        print(doc, "\n" + "=" * 100)


if __name__ == "__main__":
    main()
