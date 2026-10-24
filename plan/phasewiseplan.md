# Phase-wise Plan — Ghost Data Still Exists

Sources reviewed: `problem_statement.md`, `AGENTS.md`, `CLAUDE.md` (just `@AGENTS.md`), `README.md`, and a first look at `dataset/`.

**Deadline (from the submission page):** October 26, 2026, 6:00 AM IST = 2026-10-26T00:30Z.
At planning time (2026-10-24T14:13Z) that left **~1d 10h 16m (~34h)**.

### Time-boxed schedule (IST)

| Window (IST) | Phases | Exit criterion |
|---|---|---|
| Oct 24, 19:45 – 23:30 | 1 Exploration | All evidence extracted + cached; 32 samples explained in `data_notes.md` |
| Oct 24, 23:30 – Oct 25, 03:00 | 3, 4, 5 first pass | Pipeline produces steps for the samples |
| Oct 25, 03:00 – 07:00 | Sleep | — |
| Oct 25, 07:00 – 13:00 | 6 evaluation loop + 2 intent | Samples ≥ 90% sequence-exact; NOT_APPLICABLE detection working |
| Oct 25, 13:00 – 16:00 | 7 LLM + 8 full run | Valid 518-row `output.csv` committed (**safety submission candidate**) |
| Oct 25, 16:00 – 21:00 | Refinement on edge cases | Spot checks pass; no regressions on samples |
| Oct 25, 21:00 – Oct 26, 00:00 | 9 reports + README | Both reports written from the final run |
| Oct 26, 00:00 – 03:00 | 10 package + **submit** | Uploaded with ≥3h buffer before 06:00 IST |

Rule: always keep a valid `output.csv` from the latest good run so something can be submitted at any time.

---

## 0. What we are building (one paragraph)

A terminal-runnable deletion-audit agent. For each of the **518** rows in `dataset/deletion_requests.csv` it:
1. decides whether `request_text` actually asks for deletion (otherwise `NOT_APPLICABLE`, `[]`);
2. resolves the subject's `user_id` + every current/historical identifier (email, phone, name, email_hash);
3. finds every record/flow/backup touching that user **as of `audit_at`** across activity + evidence files;
4. applies `deletion_rules.csv` to each finding;
5. emits `COMPLETE` (verification steps with evidence) or `INCOMPLETE` (findings → remediation → verification, empty evidence on the last two).

Output: root `output.csv` → `case_id,deletion_status,steps_json`, sorted by `case_id`.

## 1. Key facts discovered so far

| Item | Fact |
|---|---|
| Requests | 518 eval, 32 sample (sample = 10 COMPLETE, 22 INCOMPLETE, 0 NOT_APPLICABLE) |
| Identities | 850 users in `user_identities.csv`; 306 changes in `user_audit_log.csv` (email/phone/name history) |
| Activity | ~4,011 rows in `system_activity.csv` (`activity_id,event_time,event_type,source_system,target_system,resource_id,reported_result,details`) — global, includes decoys |
| Evidence | 94 files in `evidence_files.csv` → SQL snapshots (24), PDFs, PNG screenshots, logs, JSON/text records |
| Rules | 15 rules: DELETE (profile, secondary id, search, cache, attachment, export, marketing), REDACT (support message, email delivery log, account tombstone), ANONYMIZE (analytics, telemetry), RETAIN (security audit log, legal hold, backup archive w/ restore blocked) |
| Step ordering | phase (FINDING→REMEDIATION→VERIFICATION), then operation order from the table, then `system_id`, then `resource_id` ascending |
| Sample quirk | INCOMPLETE cases also **verify the account record** (e.g. `account_006 ABSENT`) even when the account itself wasn't a finding — study samples for all such patterns |

## 2. Hard rules (do not break)

- Use **only** `dataset/` files. No organizer-only/golden files, no hardcoded labels.
- Ignore any evidence/activity with timestamp **> `audit_at`**.
- `reported_status` / `reported_result` are **claims**, not proof.
- Secrets only via env vars / uncommitted `.env`.
- Log every turn to root `log.txt` (§5 of AGENTS.md) with valid `tool=` and `model=`.
- Deterministic output (sorted keys/rows, fixed ordering).

---

## Progress status (updated 2026-10-24, after task 5.2)

| Phase | Status | Key artifacts | Commit |
|---|---|---|---|
| 1 Exploration | ✅ closed | `code/explore/*`, `plan/data_notes.md`, `plan/sample_walkthrough.md` | 1b3c994, dbc59fc |
| 2 Intent | ✅ closed | `code/intent.py`, `code/tests/test_intent.py` | 595e634 |
| 3 Identity | ✅ closed | `code/identity.py`, `code/tests/test_identity.py`, `code/explore/identity_report.py` | 12ac405 … 7664749 |
| 4 Evidence & state | ✅ closed | `code/evidence/*`, `code/linking.py`, `code/workflow.py`, `code/investigate.py` | 997a8f4 … 751def9 |
| 5 Policy & steps | ✅ closed | `code/policy.py`, `code/main.py`, `code/validate_output.py`, `code/evaluation/score.py`, root `output.csv` | de3d507 … (Phase 5 close) |
| 6 Evaluation | ✅ closed | `code/evaluation/{harness,main,custom_cases,score}.py`, `plan/eval_history.md` | (Phase 6 close) |
| 7 LLM & usage | ✅ closed | `code/llm.py`, `code/image_extract.py`, `code/prompts/*`, `code/llm_cache/` | (Phase 7 close) |
| 8 Full run & validation | ⏳ (validator + first valid output already done in P5) | `code/validate_output.py` | — |
| 9 Reports | ⏳ | — | — |
| 10 Package & submit | ⏳ | — | — |

Tests: 152 passing (`uv run python -m pytest code/tests -q`). Branch: `solution`.

**Scoring strategy:** see `plan/scoring_plan.md` (transcript /10, interview /30, output /30, code zip /30) — remaining phases 8, 9 (+9b interview prep), 10.

---

## Phase 1 — Setup & Data Exploration (understand before coding)

Goal: know every data shape and every pattern in the samples.

- [x] Create Python env: uv project at root (`pyproject.toml`, `uv.lock`, `.venv` outside `code/`), `code/requirements.txt` exported; pdfplumber + pymupdf; no Tesseract → PNGs via LLM vision (P7). *(task 1.1)*
- [x] Load all CSVs and profile them → `code/explore/profile_csv.py`, data_notes §1. *(task 1.2)*
- [x] Load all 24 SQL snapshots into in-memory SQLite; 4 families, replica drift found → `code/explore/load_sql.py`, data_notes §2. *(task 1.3)*
- [x] Extract the 4 PDFs (`code/explore/extract_docs.py`); view and transcribe the 11 PNGs → `code/cache/extracted/*.md` (gitignored), data_notes §4. *(task 1.5)*
- [x] Parse records (5 families) and logs (7 formats, trace joins) → `parse_records.py`, `parse_logs.py`, data_notes §3; two-clock temporal rule found. *(task 1.4)*
- [x] Walk through all 32 sample cases → `plan/sample_walkthrough.md` (20 conventions C1–C20, linking mechanisms L1–L6, workflow-timing discovery). *(task 1.6)*
- [x] Build a catalogue (data_notes §4b; 9 systems confirmed, 3 inferred, 2 never emitted): `system_id` ↔ `resource_id` prefix ↔ `data_category` ↔ rule (e.g. `account_service/account_*` → USER_PROFILE or ACCOUNT_TOMBSTONE; `search_service/search_*` → SEARCH_INDEX_ENTRY; `analytics_platform/analytics_*` → ANALYTICS_PROFILE; `support_platform/support_*` → message vs attachment …).

Deliverable: `plan/data_notes.md` with schemas, the catalogue, and sample-case explanations. ✅ **Phase 1 closed 2026-10-24** (`plan/phases/phase1.md`).

## Phase 2 — Request Classification (NOT_APPLICABLE detection)

- [x] Classify `request_text` (multilingual) → `code/intent.py`: eval 508 DELETION / 10 NOT_APPLICABLE / 0 UNSURE; samples 32/32. *(tasks 2.1–2.3)*
- [~] Approach: rule baseline done (override cues → deletion cues outside boilerplate → non-deletion topics → UNSURE). LLM fallback for UNSURE deferred to Phase 7 (0 UNSURE today).
- [x] Sanity check: all 17 intent sentences + all 10 non-deletion texts catalogued and unit-tested (60 tests); CLASSIFY_REQUEST corroborates 10/10. ✅ **Phase 2 closed 2026-10-24** (`plan/phases/phase2.md`).

## Phase 3 — Identity Resolution

- [x] Map request `email` → `user_id` → `code/identity.py` (`IdentityResolver`): eval 418 current / 100 historical / 0 errors; samples 29/3/0; 32/32 equal to the walkthrough. *(tasks 3.1, 3.4, 3.5)*
- [x] Build the full identifier set per user (emails, sha256 hashes computed and audit-recorded, digits-only phones, user_id; names kept but never linked). The hash scheme is verified 850/850.
- [x] Respect time: as_of-aware value sets; a bug for emails changed after as_of was found by tests and fixed. *(task 3.3, 74 tests)*
- [x] Normalize: shared `norm_email` / `norm_phone` / `extract_emails` / `sha256_email` / `is_sha256` for Phase 4 linking. ✅ **Phase 3 closed 2026-10-24** (`plan/phases/phase3.md`).

## Phase 4 — Evidence Indexing & Resource State Reconstruction (core)

- [x] Build a global index → `code/evidence/*` loaders (SQL, records, logs with trace joins, activity signals, PDFs, image-facts interface) + `EvidenceIndex` (by identifier key, by resource_id, account coverages). 3,077 observations, ≈1 s. *(tasks 4.1–4.4)*
- [x] Temporal filtering: **two clocks** (file captured_at and record time ≤ audit_at) + **request window** (state evidence ≥ requested_at); membership may use post-audit evidence (user-approved, constitution Art. 3.5); `check_temporal` guard. *(4.4, 4.7)*
- [x] For each resource linked to the user (L1–L4 identifiers/references/catalog, L5 joint workflow timing, L6 fallback), compute the latest known state at `audit_at` (direct observation beats omission proof) → `code/linking.py`, `code/workflow.py`, `code/investigate.py`:
  - present / absent (deleted) / redacted / anonymized;
  - which identifiers are still exposed (for REDACT/ANONYMIZE categories);
  - SQL replica drift: primary deleted but replica still holds row → finding on the replica resource.
- [x] Detect **active data flows** (connector enabled / heartbeat / ledger ACTIVE / CHECK_DATA_FLOW / repopulated) → `REPORT_ACTIVE_DATA_FLOW`.
- [x] Detect **restore risks** (restore_allowed / eligible & no deletion block / ledger ACTIVE / CHECK_RESTORE_ACCESS) → `REPORT_RESTORE_RISK`.
- [x] Never trust `reported_result=SUCCESS` alone: activity results are claims; state comes only from observations (plus CHECK_*/repopulated signals).
- [x] Pick the proving `evidence_id`: latest usable direct observation in [requested_at, audit_at], else latest qualifying omission proof → **samples: cited evidence 75/75, status 32/32, resource recall 0.973 / precision 0.991**. Q9/Q10/Q11 decided. ✅ **Phase 4 closed 2026-10-24** (`plan/phases/phase4.md`).

## Phase 5 — Policy Engine & Step Generation

- [x] Map each resource → `data_category` → rule → required action (`code/investigate.py` ACTIONS + `code/policy.py` ACTION_STEPS; 15 allowed pairs):
  - DELETE → `REPORT_REMAINING_RECORD` / `DELETE_RECORD` / `VERIFY_RECORD_ABSENT`
  - REDACT → `REPORT_EXPOSED_PII` / `REDACT_RECORD` / `VERIFY_RECORD_REDACTED`
  - ANONYMIZE → `REPORT_EXPOSED_PII` / `ANONYMIZE_RECORD` / `VERIFY_RECORD_ANONYMIZED`
  - RETAIN → `VERIFY_RECORD_PRESENT` (legal hold, security audit log in retention)
  - BACKUP_ARCHIVE → `REPORT_RESTORE_RISK` / `BLOCK_RESTORE` / `VERIFY_RESTORE_BLOCKED`
  - Data flows → `REPORT_ACTIVE_DATA_FLOW` / `DISABLE_DATA_FLOW` / `VERIFY_DATA_FLOW_DISABLED`
  - ACCOUNT_TOMBSTONE → keep `user_id`, redact name/email/phone/hash.
- [x] Status: `COMPLETE` iff zero findings; else `INCOMPLETE` (samples 32/32).
- [x] Sort within phase: operation-table order → `system_id` → `resource_id`; renumber `step_no` from 1 (tested over all 550 cases).
- [x] Evidence: findings + COMPLETE verifications cite IDs; INCOMPLETE remediation/verification use `""`. *Task 5.4 user decision: account step without citable evidence kept with `""`; retained record known only post-audit omitted in COMPLETE cases.*
- [x] Replicate sample conventions (account always verified, retained record verified present, compliant items only in COMPLETE) → **samples sequence-exact 29/32 = ceiling**.
- [x] Serialize JSON deterministically (`sort_keys=True`, compact separators). Note: the sample file mixes key orders; the grader parses JSON, so equality is semantic. *(5.1–5.6 done)* ✅ **Phase 5 closed 2026-10-24** (`plan/phases/phase5.md`): valid deterministic 518-row `output.csv`.

## Phase 6 — Local Evaluation Harness

- [x] `code/evaluation/main.py` (logic in `harness.py`): samples + custom cases in one command; Markdown summary for the report.
- [x] Metrics: case status accuracy; step-level P/R/F1 (multiset); field-level accuracy (all 7 fields); sequence exact → `score.py` (samples: status 1.000, step F1 0.990, sequence 0.906).
- [x] Print per-case diffs; samples at the ceiling (status 32/32, sequence 29/32; remaining diffs unreachable or a genuine tie).
- [x] Create **≥3 custom eval cases**: 12 (intent x5, identity x3, temporal trap, re-creation after deletion, legal hold, two-clock rule), **12/12 passing**; `plan/eval_history.md` started.
- [x] Guard against overfitting: no case-id logic in the pipeline; the one generator-order heuristic (case-number tie-break) is documented, last-resort, and its sensitivity was exposed by cc_05/cc_06. ✅ **Phase 6 closed 2026-10-24** (`plan/phases/phase6.md`).

## Phase 7 — LLM Integration (only where it adds value) & Usage Tracking

- [x] LLM used only for: screenshot fact extraction (11 images, Gemini `gemini-4-argon`, prompt v2) and an UNSURE-only intent fallback (0 eval texts today). PDFs need no LLM (pdfplumber).
- [x] Everything else deterministic; the LLM only extracts facts, never findings/steps/evidence ids.
- [x] Committed cache `code/llm_cache/` keyed by provider/model/task/prompt version/prompt/image hashes; temperature 0; keyless and `--no-llm` runs byte-identical; keyed re-run = 0 live calls.
- [x] Calls, tokens, and cost metered (`code/llm_cache/usage_last_run.json`): final output = 11 answers, 22,576 in / 3,943 out tokens = $0.0846 ($2 / $10 per 1M, user-provided). ✅ **Phase 7 closed 2026-10-24**.
- [x] API key from env var, `.env` in `.gitignore`. **Decision (2026-10-24, user): provider = Google Gemini** → `GEMINI_API_KEY` in an uncommitted root `.env`; SDK `google-genai` added via `uv add` in P7; model set by the user in `.env`: `GEMINI_MODEL=gemini-4-argon` (2026-10-24); P7 first verifies this ID exists by listing the available models via the API and fails loudly if it does not. Uses: screenshot fact extraction (11 PNGs → image facts JSON), UNSURE intent fallback. **Reproducibility design:** a provider-agnostic `llm.py` interface; every LLM result is cached as structured JSON keyed by (model, prompt, input hash), and that cache is **shipped in code.zip** so a clean run *without any API key* reproduces output.csv byte-for-byte. With a key, a missing cache entry is regenerated. Without a key and without a cache entry, the pipeline falls back deterministically (images skipped, UNSURE → rule default). Swapping providers = one adapter class.

## Phase 8 — Full Run & Output Validation

- [ ] `python code/main.py` → root `output.csv`.
- [ ] Validator script checks: exact header, 518 rows, sorted, unique case_ids matching input, valid JSON arrays, consecutive `step_no`, phase order, allowed op/state pairs, evidence rules (non-empty where required, empty for future steps, no evidence after `audit_at`), `NOT_APPLICABLE` ⇔ `[]`.
- [ ] Spot-check ~20 eval cases manually against evidence.

## Phase 9 — Reports & Documentation

- [ ] `code/evaluation/evaluation_report.md`: case/step/field/sequence accuracy, the ≥3 custom cases (inputs + expected + actual), failures found and fixes made.
- [ ] `code/evaluation/usage_report.md`: providers, model names, call counts, input/output tokens, total & avg tokens/request, estimated total & per-request cost, per-model + overall totals (from the final full run).
- [ ] `README.md`: setup (venv, deps, env vars), run command, architecture overview, where outputs go.
- [ ] Keep prompts in `.py` or `.md` (judges ignore `.json/.csv`).

## Phase 10 — Packaging & Submission

- [ ] Remove `code/__pycache__`, caches containing data, any `.env`.
- [ ] Package (PowerShell): `Compress-Archive -Path README.md, code -DestinationPath code.zip -Force`
- [ ] Ensure no `dataset/`, venv, nested archives, secrets, or real PII in `code.zip`.
- [ ] Submit: `code.zip`, root `output.csv`, `log.txt` as chat transcript, then the AI interview.
- [ ] Submission link: https://wwww.hackerrank.com/contests/hackerrank-orchestrate-october26/challenges/ghost-data-still-exists
- [ ] Interview prep: be ready to explain architecture, identity/time reconstruction, policy mapping, remediation ordering, evaluation & token costs.

---

## Suggested code layout

```text
code/
├── main.py              # entry: load → classify → resolve → investigate → plan → write output.csv
├── loaders.py           # CSVs, SQL→sqlite, PDF/PNG/log/JSON extraction (+cache)
├── intent.py            # deletion vs non-deletion (rules + LLM fallback)
├── identity.py          # user_id + historical identifier set as of audit_at
├── investigate.py       # evidence index, resource state at audit_at, flows, restore risks
├── policy.py            # rule mapping, step generation, ordering, serialization
├── llm.py               # client wrapper, caching, token/cost accounting
├── validate_output.py   # contract checks on output.csv
├── prompts/             # prompt templates (.md)
└── evaluation/
    ├── main.py          # sample + custom-case scoring
    ├── custom_cases.md  # (or embedded in report)
    ├── evaluation_report.md
    └── usage_report.md
```

## Priority order if time is short

1. Phases 1, 3, 4, 5 on the samples (correctness drives score).
2. Phase 8 validator (an invalid file scores zero).
3. Phase 2 intent classification.
4. Phases 6, 9, 10 (required deliverables).
5. LLM refinements (Phase 7) last.
