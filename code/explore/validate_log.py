"""Validate root log.txt against AGENTS.md section 5 structure."""
from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
LOG = REPO / "log.txt"

ENTRY_RE = re.compile(
    r"^## \[(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z)\] (.+)$",
    re.MULTILINE,
)
SESSION_START = "SESSION START"
VERBATIM = "User Prompt (verbatim, secrets redacted):"
REQUIRED_SECTIONS = (
    VERBATIM,
    "Agent Response Summary:",
    "Actions:",
    "Context:",
)
CONTEXT_FIELDS = ("tool=", "model=", "branch=", "repo_root=", "worktree=", "parent_agent=")


def main() -> int:
    text = LOG.read_text(encoding="utf-8")
    errors: list[str] = []

    if "User Prompt (technical paraphrase" in text:
        errors.append("Found non-verbatim User Prompt label; AGENTS.md requires verbatim user prompts.")

    headers = list(ENTRY_RE.finditer(text))
    if not headers:
        errors.append("No log entries found.")
        return report(errors)

    session_starts = [m for m in headers if m.group(2).strip() == SESSION_START]
    if not session_starts:
        errors.append("Missing SESSION START entry.")

    turn_headers = [m for m in headers if m.group(2).strip() != SESSION_START]

    for i, match in enumerate(headers):
        title = match.group(2).strip()
        start = match.start()
        end = headers[i + 1].start() if i + 1 < len(headers) else len(text)
        block = text[start:end]

        if title == SESSION_START:
            for req in ("tool=", "model=", "Repo Root:", "Branch:", "Worktree:", "Parent Agent:", "Language:"):
                if req not in block:
                    errors.append(f"SESSION START missing {req}")
            continue

        for sec in REQUIRED_SECTIONS:
            if sec not in block:
                errors.append(f"Turn '{title[:50]}...' missing section: {sec}")

        ctx_pos = block.find("Context:")
        if ctx_pos < 0:
            continue
        ctx = block[ctx_pos:]
        for field in CONTEXT_FIELDS:
            if field not in ctx:
                errors.append(f"Turn '{title[:50]}...' missing Context field {field}")

        if block.count("tool=") != 1 or block.count("model=") != 1:
            errors.append(f"Turn '{title[:50]}...' must have exactly one tool= and one model= line.")

    print(f"Entries: {len(headers)} total ({len(session_starts)} session start, {len(turn_headers)} turns)")
    return report(errors)


def report(errors: list[str]) -> int:
    if errors:
        print("INVALID log.txt:")
        for e in errors:
            print(f"  - {e}")
        return 1
    print("VALID log.txt (AGENTS.md section 5 structure)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
