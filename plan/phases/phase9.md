# Phase 9 — Reports, Documentation & Interview Preparation (incl. 9b)

**Time box:** ~3–4h
**Goal:** make the work evaluable and explainable — the code-zip judge reads README, `code/evaluation/evaluation_report.md`, `code/evaluation/usage_report.md`, source, and prompts (raw .json/.csv are ignored); the AI interviewer probes understanding with hidden test cases.
**Governing docs:** constitution Part II Phase 9; guardrails P9; AGENTS.md §6.8; plan/scoring_plan.md.

---

## 1. Entry gate
- [x] Final P8 run done (output.csv sha256 0d80a7d4bad67187…, 21/21 spot checks).
- [x] Metrics and usage captured from that run (`code/evaluation/main.py --markdown`, `code/llm_cache/usage_last_run.json`).

## 2. Tasks
- [x] 9.1 Code polish: `ruff check` (E, F, W) clean after fixing 5 findings (4 ambiguous `l` names, 1 unused import); module docstrings present; `code/explore/README.md` labels the exploration scripts; 152 tests green; output hash unchanged (0d80a7d4bad67187…).
- [x] 9.2 `README.md` rewritten: purpose, results, quick start (uv + pip), `.env` (names only) and keyless reproducibility, commands, pipeline diagram, module map, 10 design decisions, limitations, submission artifacts.
- [x] 9.3 `code/evaluation/evaluation_report.md`: method; status 1.0000; step P/R/F1 0.9948/0.9845/0.9896; field accuracy (7 fields); sequence 0.9062; per-case diffs with root causes; reachability ceiling (177/13/3); 12 custom cases with inputs/expectations/results; 11 failures-found/improvements-made entries (2 reverted/rejected); eval-side validation, confidence census, 21 spot checks; limitations.
- [x] 9.4 `code/evaluation/usage_report.md`: gemini-4-argon; tasks; final run 11 cached calls, 22,576 in / 3,943 out = 26,519 tokens, $0.084582, 51.2 tokens and $0.000163 per request, 0 live calls in the final run; development total 22 calls, 54,401 tokens, $0.184818; per-model = overall (single model); prices dated and sourced.
- [x] 9b.1 `plan/interview_prep.md`: pitch, worked cases (case_21, case_29), decisions with evidence and code locations, numbers, 21 hidden-test scenarios, limitations, process story.
- [x] 9.5 Numbers cross-checked against script output (harness markdown, usage json, census, spot-check log); committed.

## 3. Exit gate ✅ (2026-10-25)
- [x] All AGENTS.md §6.8 report bullets present; no placeholders; no secrets.
- [x] README instructions verified by the Phase 10 clean-checkout run (uv sync + run, keyless).
- [x] Tests green; output hash unchanged; committed.
