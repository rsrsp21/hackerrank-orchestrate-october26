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

## Phase 1 — Setup & Data Exploration (understand before coding)

Goal: know every data shape and every pattern in the samples.

- [ ] Create Python env (`.venv` at repo root, **outside** `code/`), `requirements.txt` (pandas optional, `pdfplumber`/`pypdf`, `pytesseract` or LLM vision for PNGs, `sqlite3` stdlib).
- [ ] Load all CSVs; print schemas, value counts of `event_type`, `source_system`, `target_system`, `reported_result`.
- [ ] Load every SQL snapshot into in-memory SQLite; list tables/columns per file (primary vs regional/reporting/failover/read replica).
- [ ] Extract text from all PDFs and PNGs once; cache to `code/cache/` (keep cache out of zip or regenerate).
- [ ] Read logs/JSON/text records; identify what identifiers appear (emails, hashes, phones, `user_id`, resource IDs).
- [ ] Walk through all 32 sample cases by hand against the evidence: for each, write down *why* each step exists and which evidence proves it. This is the reverse-engineering of the hidden logic.
- [ ] Build a catalogue: `system_id` ↔ `resource_id` prefix ↔ `data_category` ↔ rule (e.g. `account_service/account_*` → USER_PROFILE or ACCOUNT_TOMBSTONE; `search_service/search_*` → SEARCH_INDEX_ENTRY; `analytics_platform/analytics_*` → ANALYTICS_PROFILE; `support_platform/support_*` → message vs attachment …).

Deliverable: `plan/data_notes.md` with schemas, the catalogue, and sample-case explanations.

## Phase 2 — Request Classification (NOT_APPLICABLE detection)

- [ ] Classify `request_text` (multilingual) into: deletion vs non-deletion (access, export, correction, marketing opt-out, etc.).
- [ ] Approach: keyword/rule baseline + LLM fallback for ambiguous/non-English texts (cheap model, batched, cached by text hash).
- [ ] Hand-label ~30 eval request texts to sanity-check (they are inputs, not golden answers).

## Phase 3 — Identity Resolution

- [ ] Map request `email` → `user_id` via current snapshot **or** any historical value in `user_audit_log.csv` (match old/new email).
- [ ] Build full identifier set per user: all names, emails, phones, sha256(email) for every email (verify the hash scheme matches `email_hash`), plus `user_id`.
- [ ] Respect time: identifiers valid before `audit_at` (history after `audit_at` must not be used).
- [ ] Normalize: lowercase emails, strip phone formatting, Unicode name normalization.

## Phase 4 — Evidence Indexing & Resource State Reconstruction (core)

- [ ] Build a global index: identifier → [(source, file_id/activity_id/audit_id, system_id, resource_id, timestamp, field values)].
- [ ] Filter evidence by `captured_at <= audit_at` and activity by `event_time <= audit_at`.
- [ ] For each resource linked to the user, compute the latest known state at `audit_at`:
  - present / absent (deleted) / redacted / anonymized;
  - which identifiers are still exposed (for REDACT/ANONYMIZE categories);
  - SQL replica drift: primary deleted but replica still holds row → finding on the replica resource.
- [ ] Detect **active data flows**: sync/import/export jobs whose source still has (or recreates) the data after deletion → `REPORT_ACTIVE_DATA_FLOW`.
- [ ] Detect **restore risks**: backups containing the user with restore not blocked → `REPORT_RESTORE_RISK`.
- [ ] Never trust `reported_result=SUCCESS` alone — confirm with a later snapshot/evidence.
- [ ] Pick the correct proving `evidence_id` per finding/verification (match sample conventions: which file wins when several prove the same thing — likely latest before `audit_at`).

## Phase 5 — Policy Engine & Step Generation

- [ ] Map each resource → `data_category` → rule → required action:
  - DELETE → `REPORT_REMAINING_RECORD` / `DELETE_RECORD` / `VERIFY_RECORD_ABSENT`
  - REDACT → `REPORT_EXPOSED_PII` / `REDACT_RECORD` / `VERIFY_RECORD_REDACTED`
  - ANONYMIZE → `REPORT_EXPOSED_PII` / `ANONYMIZE_RECORD` / `VERIFY_RECORD_ANONYMIZED`
  - RETAIN → `VERIFY_RECORD_PRESENT` (legal hold, security audit log in retention)
  - BACKUP_ARCHIVE → `REPORT_RESTORE_RISK` / `BLOCK_RESTORE` / `VERIFY_RESTORE_BLOCKED`
  - Data flows → `REPORT_ACTIVE_DATA_FLOW` / `DISABLE_DATA_FLOW` / `VERIFY_DATA_FLOW_DISABLED`
  - ACCOUNT_TOMBSTONE → keep `user_id`, redact name/email/phone/hash.
- [ ] Status: `COMPLETE` iff zero findings; else `INCOMPLETE`.
- [ ] Sort within phase: operation-table order → `system_id` → `resource_id`; renumber `step_no` from 1.
- [ ] Evidence: findings + COMPLETE verifications cite IDs; INCOMPLETE remediation/verification use `""`.
- [ ] Replicate sample conventions (e.g. which extra verifications always appear, like the account record).
- [ ] Serialize JSON deterministically (`sort_keys=True`, compact separators, like the sample).

## Phase 6 — Local Evaluation Harness

- [ ] `code/evaluation/main.py`: run pipeline on the 32 samples, compare to `sample_output.csv`.
- [ ] Metrics: case status accuracy; step-level exact match; field-level accuracy (system_id, resource_id, operation, state, evidence_id); sequence accuracy (exact array match).
- [ ] Print per-case diffs; iterate Phases 3–5 until samples are ~100%.
- [ ] Create **≥3 custom eval cases** (e.g. non-deletion request in another language, historical-email request, sync recreating deleted data, legal-hold retain, tombstone) with hand-derived expected outputs.
- [ ] Guard against overfitting: logic must be generic, not keyed to sample case IDs.

## Phase 7 — LLM Integration (only where it adds value) & Usage Tracking

- [ ] Use LLM for: multilingual intent classification, image/PDF fact extraction (if OCR is weak), ambiguous record categorization.
- [ ] Keep everything else deterministic (cheaper, reproducible).
- [ ] Cache all LLM calls on disk keyed by input hash; temperature 0.
- [ ] Count calls, input/output tokens per model; compute cost → feeds `usage_report.md`.
- [ ] API key from env var (`ANTHROPIC_API_KEY` etc.), `.env` in `.gitignore`.

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
