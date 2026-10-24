# Phase 10 — Packaging & Submission

**Time box:** ~1h; submit ≥ 3h before 2026-10-26 06:00 IST (00:30Z).
**Goal:** ship exactly the right files, safely, and prove the zip runs from scratch.
**Governing docs:** constitution Part II Phase 10; guardrails P10 + §9.3/§9.4; AGENTS.md §6.9; README "Packaging".

---

## 1. Entry gate
- [x] P8 and P9 exit gates met.
- [x] ≥ 3h before the deadline (≈29h left on 2026-10-25).

## 2. Tasks
- [x] 10.1 `code/package.py`: allow-list, exclusions, secret scan of every included file, deterministic entries. Output: `code.zip` 102 files, 286 KiB.
- [x] 10.2 Listing inspected: README, pyproject.toml, uv.lock, .env.example, code/ (pipeline, evidence, evaluation incl. both reports, prompts, llm_cache, tests, explore), plan/; **no** `.env`, dataset, `code/cache/`, bytecode, or nested archives.
- [x] 10.3 Clean-checkout test (empty dir + unzip + dataset copy + `uv sync`, no API key): `output.csv` **byte-identical** to the root output (sha256 0d80a7d4bad67187…); validator VALID; 152 tests passed; harness status 1.0000, custom 12/12.
- [x] 10.4 Root output validator green; `log.txt` 48 entries, each with exactly one `tool=Claude Code` and one `model=claude-opus-5-5` line and all required sections; no secret patterns.
- [x] 10.5 Committed. Upload (by the participant): `code.zip`, `output.csv`, `log.txt` at https://wwww.hackerrank.com/contests/hackerrank-orchestrate-october26/challenges/ghost-data-still-exists — rebuild `code.zip` with `uv run python code/package.py` right before uploading so it includes the latest `plan/` and `log.txt`-independent files.

## 3. Exit gate ✅ (2026-10-25)
- [x] code.zip built, inspected, clean-checkout reproduces output.csv byte-for-byte.
- [x] All three artifacts validated; committed; upload instructions handed over.
