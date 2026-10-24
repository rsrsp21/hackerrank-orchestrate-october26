# Ghost Data Still Exists — Deletion-Audit Agent

HackerRank Orchestrate, October 2026. For every request in `dataset/deletion_requests.csv` the agent decides whether the person asked for deletion, reconstructs who they are (current and historical identifiers), finds every copy of their data across databases, replicas, logs, exports, support systems, analytics, backups, PDFs and screenshots **as it stood at `audit_at`**, applies the deletion policy, and writes `output.csv` with `COMPLETE`, `INCOMPLETE`, or `NOT_APPLICABLE` plus an ordered, evidence-backed plan of findings, remediation, and verification steps.

| Result (public samples, 32 cases) | Value |
|---|---|
| Case-level status accuracy | **1.000** |
| Step precision / recall / F1 | 0.995 / 0.985 / **0.990** |
| Exact steps array (sequence) | 0.906 (29/32 — the reachable ceiling, see the evaluation report) |
| Cited evidence agreement | 75/75 |
| Custom evaluation cases | 12/12 |
| Manual spot checks of eval cases against raw evidence | 21/21 |
| LLM cost of the submitted output | $0.085 total, $0.00016 per request (Gemini, 11 cached calls) |

Details: [`code/evaluation/evaluation_report.md`](code/evaluation/evaluation_report.md) · [`code/evaluation/usage_report.md`](code/evaluation/usage_report.md)

---

## Quick start

Requirements: Python ≥ 3.12. The `dataset/` folder (not shipped in `code.zip`) must sit at the repository root next to this README.

**With uv (recommended)**
```bash
uv sync                                    # creates .venv from uv.lock
uv run python code/main.py                 # writes ./output.csv (≈5 s)
uv run python code/validate_output.py      # checks output.csv against the submission contract
uv run python code/evaluation/main.py      # public samples + 12 custom cases
uv run python -m pytest code/tests -q      # 152 tests
```

**With pip**
```bash
python -m venv .venv && . .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r code/requirements.txt pytest
python code/main.py
```

**Configuration (optional).** Copy `.env.example` to `.env`; only needed to call Gemini again:
```
GEMINI_API_KEY=...           # never committed; read from the environment or .env
GEMINI_MODEL=gemini-4-argon
LLM_PRICE_INPUT_PER_MTOK=2   # USD per 1M tokens, for the usage report
LLM_PRICE_OUTPUT_PER_MTOK=10
```
**No key is needed to reproduce the submission.** Every model answer is stored in the committed cache `code/llm_cache/`; a run without a key (or with `--no-llm`) produces a byte-identical `output.csv`. To re-read the screenshots with your own key: `uv run python code/image_extract.py --force`.

---

## How a case is decided

```
deletion_requests.csv ─┐
                       ▼
 intent.py ─────────── deletion? (multilingual rules; LLM only for UNSURE) ── no ──► NOT_APPLICABLE []
                       │ yes
 identity.py ───────── subject = user_id + every email / sha256 hash / phone held at or before audit_at
                       │
 evidence/* ────────── 94 files + system_activity → 3,000+ Observations (SQL, JSON, TXT, 7 log formats,
                       │  PDFs, Gemini-read screenshots), each with file capture time AND record time
 linking.py ────────── resources tied to the subject by exact identifiers, references, catalog links
 workflow.py ───────── identifier-less records (deleted accounts, anonymized analytics) tied by the
                       │  deletion workflow's timing, assigned jointly across all 550 requests
 investigate.py ────── state of each resource at audit_at from evidence in [requested_at, audit_at]
                       │  → action per deletion_rules.csv (DELETE / REDACT / ANONYMIZE / DISABLE / BLOCK / RETAIN)
 policy.py ─────────── findings → remediation → verification, sorted per the contract
                       ▼
 main.py ───────────── output.csv  (validated by validate_output.py)
```

| Module | Responsibility |
|---|---|
| `code/main.py` | entry point; runs the pipeline, writes `output.csv`, records LLM usage |
| `code/intent.py` | does the text authorize deletion? override cues (negations in 6 languages, "marketing only", restore requests) beat deletion cues; boilerplate is ignored |
| `code/identity.py` | request email → exactly one `user_id`; the identifier set as of `audit_at`; shared normalizers |
| `code/evidence/` | one loader per evidence family → `Observation`s; `interpret.py` holds the record → (category, state) rules; `index.py` is the queryable index with the time rules |
| `code/linking.py` | identifier, reference, and data-catalog links (L1–L4) |
| `code/workflow.py` | joint workflow-timing assignment for records without identifiers (L5) and the naming fallback (L6) |
| `code/investigate.py` | per-case investigation: resource set, state at audit_at, required action, two-pass analytics attribution, temporal guard |
| `code/policy.py` | investigation → ordered steps; the 15 allowed operation/state pairs |
| `code/llm.py`, `code/image_extract.py`, `code/prompts/` | provider-agnostic cached Gemini client; screenshot → structured facts; prompts |
| `code/validate_output.py` | every contract rule, including evidence existence and dates |
| `code/evaluation/` | scoring (`score.py`), harness (`main.py` → `harness.py`), 12 custom cases, the two reports |
| `code/tests/` | 152 unit and integration tests |
| `code/explore/` | exploration scripts used to understand the data (not part of the pipeline) |
| `plan/` | constitution, guardrails, phase plans, data notes, sample walkthrough, evaluation history, interview notes |

---

## Key design decisions (each backed by the data)

1. **Evidence over claims.** `reported_status` and activity results are claims. State comes only from observations; the only activity rows treated as observations are checks that report a state ("data flow remains enabled", "archive can still be restored") or a re-population.
2. **Two clocks.** An observation counts only if both its file's capture time and its own record time are ≤ `audit_at`. Ledgers contain rows recorded *after* their file was captured (evidence_13, evidence_36) — re-creations that must not change the answer.
3. **Request window.** State evidence must also be observed at or after `requested_at`; earlier observations describe an earlier episode (all 75 sample citations lie in `[requested_at, audit_at]`).
4. **Membership vs state.** Which resources belong to the subject may use any evidence (5 retained audit records in the samples are visible only in post-audit files); the state and every citation stay within the window.
5. **Direct beats omission.** A record that names the resource (e.g. a 404 lookup) wins over "missing from a snapshot"; omission proofs come only from topology snapshots and explicitly empty extracts.
6. **Workflow timing.** Deleted accounts and anonymized analytics carry no identifiers. Each request's deletion workflow appears in `system_activity` at fixed offsets from `reported_at`, with the result matching the reported status; all requests are assigned jointly (eliminate candidates owned by other subjects → unique → last-resort case-order tie-break).
7. **Exact identity only.** Emails (case-normalized, including inside free text), sha256 hashes (including old ones), digits-only phones, user ids. Names never link (duplicate names and look-alike decoys exist). A catalog link is rejected when the record's own identifiers name someone else.
8. **Policy table.** `deletion_rules.csv` → one action per category; tombstones are redacted (stable `user_id` kept), backups are blocked (never deleted), security/legal records are verified present.
9. **LLM as a fact extractor only.** Gemini reads screenshots into structured facts validated against a schema; it never decides findings, steps, or evidence ids. Temperature 0, cached, metered.
10. **Determinism.** Same inputs → byte-identical `output.csv` (also without a key).

Known limitations are listed in the evaluation report (ties between concurrent workflows, two sample resources that appear nowhere in the participant data, one audit-record ambiguity).

---

## Submission artifacts

| Item | Where |
|---|---|
| `output.csv` | repository root (518 rows, validated) |
| `code.zip` | built by `uv run python code/package.py` (README, pyproject.toml, uv.lock, code/, plan/; excludes caches, `.env`, `dataset/`) |
| Chat transcript | `log.txt` at the repository root |

Challenge page: https://wwww.hackerrank.com/contests/hackerrank-orchestrate-october26/challenges/ghost-data-still-exists
