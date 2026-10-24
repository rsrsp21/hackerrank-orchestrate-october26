# Phase 1 — Setup & Data Exploration

**Time box:** Oct 24, 19:45 – 23:30 IST
**Goal:** Fully understand every input shape and reverse-engineer the decision logic behind all 32 sample answers *before* writing the pipeline.
**Governing docs:** `plan/constitution.md`, `plan/guardrails.md` (especially §2 Data Access, §3 Temporal, §4 Evidence, §5 Identity).

---

## 1. Inventory (already observed)

| Input | Size / shape | Notes |
|---|---|---|
| `deletion_requests.csv` | 518 rows | `case_id,email,requested_at,reported_status,reported_at,audit_at,request_text`. The texts are probably multilingual. |
| `sample_deletion_requests.csv` / `sample_output.csv` | 32 rows | 10 COMPLETE, 22 INCOMPLETE, **0 NOT_APPLICABLE** |
| `user_identities.csv` | 850 users | `user_id,name,email,phone,email_hash,updated_at` |
| `user_audit_log.csv` | 306 changes | Fields changed: `email` 107, `email_hash` 107, `phone` 92 (no name changes) |
| `system_activity.csv` | 4,011 events | 17 `event_type`s; `reported_result`: SUCCESS 2914 / FAILED 721 / PARTIAL 376 |
| `deletion_rules.csv` | 15 rules | DELETE / REDACT / ANONYMIZE / RETAIN by `data_category` |
| `evidence_files.csv` | 94 files | `file_id,file_path,origin,captured_at` |
| `evidence/databases` | 24 `.sql` | inventory, read/regional/reporting/failover replicas, search primary |
| `evidence/records` | 28 `.json` + 1 `.txt` | snapshot bundles, service resource exports, connector configs, export jobs/manifest, security audit ledger, analytics report, account handover |
| `evidence/logs` | 26 `.log` | service events, app traces, runtime exports, notification delivery, resource lookup traces |
| `evidence/documents` | 4 `.pdf` | account history report, delivery correction attachment, legal retention register, security retention extract |
| `evidence/images` | 11 `.png` | admin consoles: account, analytics, backup restore, connectors, export, deleted-account reference, marketing, object storage, search index, security audit, support ticket |

**Activity event types:** DELETE_RECORD 890, UPDATE_RECORD 672, SYNC_RECORD 447, INDEX_RECORD 400, SEND_EMAIL 368, REFRESH_CACHE 284, RETAIN_RECORD 206, ANONYMIZE_RECORD 204, REDACT_RECORD 173, CREATE_EXPORT 155, CHECK_DATA_FLOW 89, BLOCK_RESTORE 36, DISABLE_DATA_FLOW 36, CHECK_RESTORE_ACCESS 28, LINK_RESOURCE_IDENTITY 12, CLASSIFY_REQUEST 10, RESTORE_BACKUP 1.

**Systems seen:** account_service, search_service, analytics_platform, support_platform, cache_service, email_delivery_service, archive_service, object_store / object_storage, integration_service, backup_service, export_service, account_replication_cluster, legal_service, identity_service, marketing_platform, security_service, privacy_case_management, plus actors such as deletion_worker, profile_service, notification_service, data_catalog, privacy_intake.

**Tooling available:** Python 3.12.8, `sqlite3` (stdlib), `pdfplumber`, `pymupdf`. **No Tesseract.** The 11 PNGs are read with a vision model (Claude reads them directly during exploration; the pipeline can use an LLM vision call, cached).

---

## 2. Tasks

### 1.1 Environment ✅ (done 2026-10-24)
- [x] uv project at the repo root: `pyproject.toml` + `uv.lock` (name `ghost-data-audit`, Python ≥3.12). `.venv` at the repo root, outside `code/`.
- [x] Dependencies: `pdfplumber 0.11.10`, `pymupdf 2.0` (use `import pymupdf`, not the deprecated `fitz`). LLM SDK to be added in Phase 7 via `uv add`.
- [x] `code/requirements.txt` exported for pip users: `uv export --no-hashes --no-dev --format requirements-txt -o code/requirements.txt`. **Re-export after every `uv add`.**
- [x] `.gitignore`: `.venv/`, `__pycache__/`, `.env*`, `code/cache/`, `*.zip`, OS/editor files.
- [x] Created `code/explore/` and `code/cache/`.
- [x] Verified: Python 3.12.8, SQLite 3.45.3, pdfplumber and pymupdf import OK.

Commands:
```powershell
uv sync                       # create/refresh .venv from uv.lock
uv run python code/main.py    # run the pipeline
```
Packaging note: `code.zip` ships `code/requirements.txt`. Also add `pyproject.toml` and `uv.lock` to the `Compress-Archive` paths so uv users can `uv sync`.

### 1.2 Structured CSV profiling ✅ (done 2026-10-24; script `code/explore/profile_csv.py`, findings in `plan/data_notes.md` §1)
- [x] Parse all timestamps as UTC datetimes. All are ISO `Z`; ordering requested ≤ reported ≤ audit holds.
- [x] `system_activity` pivot, resource prefixes, and details templates. `details` carries no user identifiers except 12 LINK rows.
- [x] `LINK_RESOURCE_IDENTITY` (12) = explicit resource→user links. `CLASSIFY_REQUEST` (10) = non-deletion classifications.
- [x] `email_hash` = sha256(email) (850/850).
- [x] Request emails: eval 418 current + 100 historical-only + 0 unresolved; sample 29 + 3.
- Key extras: 11 non-deletion texts in eval (template-like, so rules will catch them); `case_id` is numeric-sorted, not zero-padded; `CHECK_DATA_FLOW` / `CHECK_RESTORE_ACCESS` details are direct evidence of active flows and restore risks.

### 1.3 SQL snapshots ✅ (done 2026-10-24; script `code/explore/load_sql.py`, findings in `plan/data_notes.md` §2)
- [x] All 24 files loaded, each into its own in-memory SQLite DB (sources untouched). Tables, columns, and row counts printed. 891 observations cached to `code/cache/extracted/sql_observations.jsonl`.
- [x] Four families: inventory (11), replica topology (11), account failover (1), search primary (1). Collection → system → category map in data_notes §2.2.
- [x] Drift = account rows present only in replica tables (13 cases incl. `account_005` in evidence_54). Treated states: analytics all-null, tombstone prohibited-fields-null, support `[REDACTED]`, connector `enabled=0`, backup `restore_allowed=0`.
- Key extras: the file `captured_at` is the observation time (no row is newer). Each resource appears in only one SQL file. evidence_90 is completely empty. There are decoy users not in user_identities, and emails in UPPERCASE and inside free text.

### 1.4 JSON / TXT / LOG records ✅ (done 2026-10-24; scripts `code/explore/parse_records.py`, `code/explore/parse_logs.py`; findings in data_notes §3)
- [x] JSON families: snapshot bundles (12), service resource exports (11), ledgers (3), single-collection (2), handover TXT (1). 931 observations cached.
- [x] **Ledger `record_type` == the rules' `data_category`**; `result` gives the state directly (FOUND/NOT_FOUND/IDENTIFIABLE/ANONYMIZED/REDACTED/ACTIVE/DISABLED/BLOCKED).
- [x] Logs: 7 formats, 26 files, 2,211 events, 0 unparsed. Trace joins (started → completed) give 1,071 resource observations. Outcome vocabulary documented (404=absent, identity_scan=identifiable, heartbeat=active flow, restore_candidate eligible=restore risk, decision=deny=blocked, marker_found=false=replica remnant).
- [x] Temporal decision: **both** the file `captured_at` and the record-level time must be ≤ `audit_at` (trap rows in evidence_13 / evidence_36 linked to case_135 / case_383). Tentative until 1.6 validates it.
- [x] Handover TXT (evidence_03, 2026-10-01) parsed. It's usable only for cases with `audit_at` ≥ 2026-10-01T12:00Z.
- Noise identified: infra services, connection/cache/retry events, and the evidence_53 profile_service flood (300 lookups, no requester emails).

### 1.5 PDFs & images ✅ (done 2026-10-24; script `code/explore/extract_docs.py`; findings in data_notes §4)
- [x] 4 PDFs extracted with pdfplumber (clean text and tables, no OCR needed) → `code/cache/extracted/evidence_{18,27,55,58}.md`.
- [x] All 11 PNGs viewed and their facts transcribed → `code/cache/extracted/evidence_{04,09,14,19,23,28,32,37,42,46,60}.md`.
- [x] Artifact → scenario map built (data_notes §4.2). Each artifact pairs with one eval case (audit ≈ capture + 1 day) and usually a LINK_RESOURCE_IDENTITY row. Only evidence_58 is cited by a sample (case_07).
- [x] Decoys inside screenshots noted (other archives and exports, `search_1874` near-match email). Conflict found: evidence_60 marketing_001 (Q9). The legal register has no resource IDs (Q10).
- Pipeline implication: the transcriptions are test fixtures; production extraction = cached LLM vision (Phase 7).

### 1.6 Sample case reverse-engineering ✅ (done 2026-10-24; script `code/explore/sample_walkthrough.py`; output `plan/sample_walkthrough.md`)
- [x] All 32 cases explained step by step (subject, match type, evidence, rule, timing).
- [x] 20 conventions written (C1–C20): status from findings only; account always verified; retained audit verified present; COMPLETE verifies treated items; operation mapping; ordering; evidence choice = closest capture ≤ audit_at (equality allowed); two-clock rule confirmed (case_09); post-audit recreation ignored (case_27); decoys; replica drift on account_service; absence proofs; restore and flow detection; support message vs attachment; old-hash analytics → DELETE; tombstone.
- [x] Linking mechanisms L1–L6. **Workflow timing (L5)** is the only link for identifier-less absent or anonymized records: the account DELETE sits 0–75 min before reported_at, with reported_result ↔ reported_status. Only 207/550 requests have a unique candidate, so P4 needs joint assignment.
- [x] Q2, Q4/Q7, Q5/Q8, and Q6 resolved; new Q11 (workflow collisions); Q9 and Q10 remain (eval-only).

### 1.7 Mapping catalogue
Build `system_id` → `resource_id` prefix → `data_category` → `rule_id` → (finding op, remediation op, verification op).

---

## 3. Deliverables

| File | Content |
|---|---|
| `plan/data_notes.md` | Schemas, mapping catalogue, conventions (1.6), temporal rules, decoy patterns, open questions |
| `plan/sample_walkthrough.md` | Per-case explanation for all 32 samples |
| `code/explore/` (scripts) | Re-runnable profiling and extraction scripts (`profile_csv.py`, `load_sql.py`, `extract_docs.py`) |
| `code/cache/extracted/` | Cached text/facts from PDFs, images, and logs (gitignored) |

## 4. Exit Criteria

- [ ] Every one of the 94 evidence files has been opened and its structure noted.
- [ ] All 32 sample cases are explained step-by-step, with no unexplained steps.
- [ ] Mapping catalogue complete for every `system_id` that appears in the sample outputs.
- [ ] Evidence-selection and account-verification conventions written down.
- [ ] Open questions listed (to be resolved in Phases 3–5).

## 5. Guardrail Reminders for This Phase

- Exploration only reads `dataset/`. Never search for golden or organizer files.
- Don't copy PII into `log.txt` or the plan files beyond what's needed (use IDs, not full names and emails, in notes where possible).
- Sample answers are for learning conventions, never a lookup table.
- Log every turn to `log.txt`.

## 6. Risks / Watch-outs

- **Decoys:** similar names or emails belonging to other users.
- **Temporal traps:** evidence captured after `audit_at` (e.g. files dated 2026-10-01).
- **False success:** `reported_result=SUCCESS` deletes contradicted by later snapshots.
- **Resurrection:** SYNC_RECORD, INDEX_RECORD, or RESTORE_BACKUP after a DELETE recreates data.
- **Replica drift:** the primary is clean but a read, regional, reporting, or failover replica still holds the row.
- **No NOT_APPLICABLE in the samples:** intent detection has to be validated with custom cases (Phase 2 / 6).
