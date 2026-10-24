# Scoring Plan — maximise every component

Scoring (from the event leaderboard): **Chat transcript /10 · AI judge interview /30 · Output CSV /30 · Code zip /30 = /100**. The current leader scores 77.7 (8.1 / 22.8 / 28.5 / 18.3). The weakest component for most teams is the code zip; the interview and the CSV carry the most weight.

Status audit (2026-10-24, ~30 h before the deadline):

| Component | Max | What is judged (our understanding) | Where we stand | Gap → action |
|---|---|---|---|---|
| Output CSV | 30 | accuracy vs hidden answers: status, identity resolution, discovered records/risks, evidence, policy, step completeness/order | samples: status 1.000, step F1 0.990, sequence 29/32 (= ceiling); valid, deterministic, keyless-reproducible | only last-resort tie-breaks remain (137/508 eval cases). **Do not overfit.** Final run + 20 manual spot checks (P8) |
| Code zip | 30 | runnable solution, README, `evaluation/evaluation_report.md`, `evaluation/usage_report.md`, prompts in .py/.md, code quality, no forbidden files | strong code + 152 tests; **README is still the starter; both reports missing; plain Compress-Archive would ship `code/cache/` (5.2 MB of extracted data)** | P9: README, evaluation_report.md, usage_report.md; P10: packaging script with exclusions + zip inspection + clean-checkout run |
| AI judge interview | 30 | explain architecture, investigation approach, remediation planning, evaluation; probed with **hidden test cases** | everything documented in plan/*.md, but scattered | P9b: `plan/interview_prep.md` — architecture in 2 minutes, key decisions with evidence, numbers, limitations, and worked answers for likely hidden-test scenarios |
| Chat transcript | 10 | `log.txt` per AGENTS.md §5: every turn, verbatim prompt, summary, actions, valid `tool=`/`model=` | 46 entries, all valid; shows planning, verification, honest corrections | keep logging every turn; final validation script before upload; no secrets |

## Actions by phase

### P8 — final run & validation (≈1 h)
- [ ] Clean run (`uv run python code/main.py`), validator, determinism (2 runs), keyless run, test suite, harness.
- [ ] **20 manual spot checks** across statuses, languages, historical emails, image scenarios, retained records, tombstones; each verified against raw evidence and noted in `plan/phases/phase8.md`.
- [ ] Freeze `output.csv` (commit + keep a copy).

### P9 — documentation for the code-zip judge (≈2–3 h)
- [ ] `README.md` (replaces the starter): what it does; quick start (uv / pip); `.env` (names only); run commands (main, validator, evaluation, tests, image extraction); architecture diagram (text); module map; key design decisions; reproducibility without a key; limitations.
- [ ] `code/evaluation/evaluation_report.md`: metrics (case status, step P/R/F1, field-level, sequence), per-case diffs with root causes, ≥3 custom cases (we have 12) with inputs/expectations/results, **failures found and improvements made** (from `plan/eval_history.md`), eval-side confidence analysis, limitations.
- [ ] `code/evaluation/usage_report.md`: provider/model, calls, input/output tokens, total & average per request, cost total & per request (user-provided prices), per-model + overall totals, development vs final-run spend, cache/keyless design.
- [ ] Code polish pass: module docstrings, no dead code, consistent names; explore scripts labelled as exploration.

### P9b — interview preparation (≈1 h)
- [ ] `plan/interview_prep.md`: 2-minute architecture pitch; pipeline walk-through on one case end-to-end; the 10 most important decisions and their evidence (two clocks, request window, membership vs state, workflow timing, two-pass analytics, identity conflict, policy table, evidence choice, COMPLETE-without-evidence decision, LLM-as-fact-extractor); numbers to quote; known limitations; **answers for hidden-test-style questions** (non-English refusal, historical email, re-creation after audit, replica drift, legal hold, tombstone, restore risk, sync re-population, decoy look-alike, evidence after audit_at, ambiguous workflows).

### P10 — package & submit (≈1 h, target ≥3 h before 06:00 IST Oct 26)
- [ ] `code/package.py`: builds `code.zip` from README.md, pyproject.toml, uv.lock, code/ **excluding** `code/cache/`, `__pycache__`, `.env*` (except `.env.example`), nested archives; lists the contents; fails on forbidden files.
- [ ] Clean-checkout test: unzip into a temp dir + copy `dataset/` → `uv sync` → `uv run python code/main.py` → identical output hash.
- [ ] Final `log.txt` validation; upload `code.zip`, `output.csv`, `log.txt` at https://wwww.hackerrank.com/contests/hackerrank-orchestrate-october26/challenges/ghost-data-still-exists

## Principles
- Accuracy work is done: further tuning against 32 samples risks overfitting, which the interview probes. Spend the remaining time on clarity, evidence, and reproducibility.
- Every number in a report comes from a script run, never typed from memory.
