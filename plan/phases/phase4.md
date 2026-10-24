# Phase 4 — Evidence Indexing & State Reconstruction (core)

**Time box:** Oct 24 evening → Oct 25 morning (~6–8h). This is the phase that decides the score.
**Goal:** for every deletion request, produce a grounded, time-correct **case investigation**:
- the subject's account resource and its state at `audit_at`;
- every other resource linked to the subject, with its category, its state at `audit_at`, and the proving `evidence_id`;
- active data flows, restore risks, and retained records.

Phase 5 turns this into steps. No step formatting happens in this phase.
**Governing docs:** constitution Part II Phase 4; guardrails P4 + §3 Temporal + §4 Evidence; data_notes §2–§4b; sample_walkthrough C1–C20, L1–L6.

---

## 1. Entry gate
- [x] P1 exit gate met (all 94 evidence families understood; data_notes §2–§4b).
- [x] P3 resolver ready (`code/identity.py`, `Subject.link_keys()`, shared normalizers).
- [x] P2 classifier ready (only DELETION requests are investigated).

## 2. Architecture

```
code/
├── evidence/
│   ├── model.py        # Observation, Coverage, State enum
│   ├── sql.py          # 24 .sql → observations (typed tables, record_json, nested document) + coverage
│   ├── records.py      # bundles, service exports, ledgers, single-collection, handover TXT
│   ├── logs.py         # 7 formats → events → trace joins → observations
│   ├── activity.py     # system_activity rows → claims, CHECK_* / repopulated signals, catalog links
│   ├── documents.py    # PDF text (pdfplumber) → observations via field regexes
│   ├── images.py       # image facts JSON (from the Phase 7 vision extractor) → observations
│   └── index.py        # EvidenceIndex: by link key, by resource_id, coverage; two-clock filter
├── linking.py          # L1–L4 identifier links + L5 workflow-timing joint assignment (+ L6 fallback)
└── investigate.py      # per-case: resource set, state at audit_at, evidence choice → CaseInvestigation
```
The `code/explore/*` scripts stay as exploration; the production modules are rewritten cleanly, reusing the proven parsing logic.

### 2.1 Observation model
```python
Observation(
    evidence_id,          # file_id | activity_id | audit_id
    file_captured_at,     # manifest captured_at (activity: event_time)
    observed_at,          # record/line time (two-clock rule)
    system_id,            # emitted system (replica tables → "account_service")
    resource_id,
    category,             # USER_PROFILE | SEARCH_INDEX_ENTRY | ANALYTICS_PROFILE | SUPPORT_MESSAGE | SUPPORT_ATTACHMENT |
                          # USER_EXPORT | DATA_FLOW | BACKUP_ARCHIVE | SECURITY_AUDIT_LOG | LEGAL_HOLD_RECORD |
                          # ACCOUNT_TOMBSTONE | MARKETING_PROFILE | CONTACT_RECORD (analytics keyed by old hash, C18) | None
    state,                # PRESENT | ABSENT | IDENTIFIABLE | ANONYMIZED | REDACTED | FLOW_ACTIVE | FLOW_DISABLED |
                          # RESTORE_ALLOWED | RESTORE_BLOCKED
    link_keys,            # {("email",…),("hash",…),("phone",…),("user",…)} found in the record (incl. free text)
    refs,                 # other resource_ids referenced (source_resource_id, repopulated targets…)
    directness,           # DIRECT (resource named) | OMISSION (absent from an authoritative snapshot)
    source,               # short provenance string for explanations
)
```

### 2.2 State rules per source (from data_notes §2–§3, walkthrough C14–C19)
| Source | → state |
|---|---|
| account row in any SQL table/replica, bundle profile, lookup 200 with profile, ledger USER_PROFILE FOUND | PRESENT (USER_PROFILE) |
| lookup 404 / rows=0, ledger USER_PROFILE NOT_FOUND | ABSENT (DIRECT) |
| resource missing from a **topology DB** snapshot table (header `Database topology`) or an **explicit empty bundle snapshot** for that store | ABSENT (OMISSION). **Not** the SQL inventory files (evidence_90 is never used) |
| search doc / index hit / ledger SEARCH_INDEX_ENTRY FOUND | PRESENT |
| analytics with any identifier, identity_scan direct_identifiers=1, ledger IDENTIFIABLE | IDENTIFIABLE |
| analytics with all identifiers null, profile_read direct_identifiers=0, ledger ANONYMIZED | ANONYMIZED |
| analytics `contact_lookup_completed` keyed by email hash | PRESENT (CONTACT_RECORD → DELETE, C18) |
| support conversation with an email in the text / pii scan / ticket with requester_email / ledger IDENTIFIABLE | IDENTIFIABLE (SUPPORT_MESSAGE) |
| support message `[REDACTED]` / ticket with only customer_reference / ledger REDACTED | REDACTED |
| ticket_attachments, attachment_pii_scan, PDF attachment, ledger SUPPORT_ATTACHMENT FOUND, support_replica contact with marker_found=false, object_storage attachment | PRESENT (SUPPORT_ATTACHMENT) |
| export job/export with download_available or available=true, ledger USER_EXPORT FOUND, export console Ready | PRESENT (USER_EXPORT) |
| connector enabled=true / heartbeat / ledger DATA_FLOW ACTIVE / console Continuous Healthy | FLOW_ACTIVE |
| connector enabled=false / config_loaded enabled=false / ledger DISABLED | FLOW_DISABLED |
| backup restore_allowed=true / candidate eligible=true deletion_block=false / ledger BACKUP_ARCHIVE ACTIVE | RESTORE_ALLOWED |
| restore_allowed=false / decision=deny / ledger BLOCKED | RESTORE_BLOCKED |
| security audit record/event/read rows=1 / ledger FOUND | PRESENT (SECURITY_AUDIT_LOG, retained) |
| retained_order_records / retained_order_loaded / ledger LEGAL_HOLD_RECORD FOUND | PRESENT (LEGAL_HOLD_RECORD) |
| deleted_customer_references with any prohibited field | IDENTIFIABLE (ACCOUNT_TOMBSTONE); all null → REDACTED |
| activity rows (DELETE/REDACT/… SUCCESS) | **claims only**, never a state. CHECK_DATA_FLOW "remains enabled" → FLOW_ACTIVE; CHECK_RESTORE_ACCESS "can still be restored" → RESTORE_ALLOWED; "repopulated" → PRESENT of the target (these are observations of state, cited by activity_id) |

### 2.3 Temporal rule (guardrails §3)
An observation is usable for a case iff `file_captured_at <= audit_at` **and** `observed_at <= audit_at` (equality allowed). Enforced in one function (`EvidenceIndex.usable(obs, audit_at)`) with an assertion in the investigator that no chosen evidence violates it.

### 2.4 Linking subject → resources (walkthrough §2)
1. **L1 direct identifiers:** observation `link_keys` ∩ `subject.link_keys()` (exact).
2. **L2 log trace joins:** the started→completed lookup key is part of the observation's `link_keys`.
3. **L3 references:** a linked observation's `refs` (e.g. `source_resource_id=account_006`) pull in that resource.
4. **L4 catalog links:** `LINK_RESOURCE_IDENTITY` activity → resource ↔ (email, user_id).
5. **L5 workflow timing (joint over all 550 requests):**
   - each deletion request's workflow anchors on an account `DELETE_RECORD` in `[reported_at − 90 min, reported_at + 15 min]` whose `reported_result` matches `reported_status` (COMPLETE↔SUCCESS, PARTIALLY_COMPLETE↔PARTIAL, NOT_STARTED↔FAILED);
   - follow-up policy actions and checks (ANONYMIZE/REDACT/DISABLE/BLOCK/DELETE/CHECK_*) in `[anchor, reported_at + 3h]` are candidate members of that workflow;
   - **joint assignment:** candidates already linked by L1–L4 to a *different* subject are removed; then resolve unique candidates and propagate (constraint elimination) until fixpoint; remaining ties → Q11 tie-break.
6. **L6 fallback:** a subject with no account candidate at all → `account_{NNN}` derived from `user_{NN}` (scenario convention, case_04). Flagged low-confidence.
7. Names never link. Unknown user_ids (user_8741 …) never link.

### 2.5 Per-case investigation
For each resource linked to the subject:
- usable observations → **state at audit_at = the latest usable DIRECT observation**; OMISSION only if no DIRECT observation exists (case_21 vs case_31);
- **evidence choice (C8, refined):** the evidence_id of the observation that determines the state (latest usable DIRECT; else latest usable OMISSION from topology DB / explicit empty bundle);
- activity claims are used only for linking (L5), never as the state, except the CHECK_* / repopulated signals listed above.

Output:
```python
CaseInvestigation(case_id, subject, account: ResourceState, resources: [ResourceState], notes: [str])
ResourceState(system_id, resource_id, category, state, evidence_id, link: "L1".."L6", confidence)
```

## 3. Decisions to make in this phase (open questions)
- **Q9 marketing_001** (evidence_60 vs activity_4008): proposed rule: an L4 catalog link is a grounded link, so the marketing profile is linked to user_09. The state comes from evidence_60 (PRESENT, Live) → finding cited with evidence_60. Record the rationale and confidence; revisit if it conflicts with a general rule.
- **Q10 legal holds:** proposed rule: only `retained_order_records` / `retained_order_loaded` / ledger rows give `legal_hold_*` resources. The PDF register (evidence_27) has no resource IDs, so it is used only as corroboration. Verify the retained-record convention (C3-like `VERIFY_RECORD_PRESENT legal_service/...`) against eval data volume.
- **Q11 workflow ties:** measure how many requests remain tied after joint elimination. Candidate tie-breaks, in order: (1) temporal proximity to the anchor; (2) the record order inside the snapshot bundle (generator artifact, last resort, documented). Pick by sample accuracy, not by guess.

## 4. Tasks
- [x] 4.1 `code/evidence/model.py` (2026-10-24): Observation (two-clock `usable()`), Coverage (`proves_absent`), State/Category/Directness enums, `SYSTEM_BY_PREFIX`/`system_for`, `link_keys_from` (nested, free-text emails, user ids, sha256, phones; integrity seals excluded), `resource_refs_from`. `code/tests/test_evidence_model.py`: 5 tests (trap rows evidence_13 and case_09/evidence_06 included). Suite: 79 passed.
- [x] 4.2 Source loaders (2026-10-24): `code/evidence/{common,interpret,sql,records,logs,activity,documents}.py`. `interpret.py` holds the shared collection → (category, state) rules used by SQL and record files. Totals: SQL 891, records 931, logs 1,071 (trace-joined, carried lookup keys), activity signals 181 (CHECK_DATA_FLOW / CHECK_RESTORE_ACCESS / repopulated), PDFs 3; 14 account Coverages (11 topology tables, 3 explicit empty snapshots; inventory never used); 12 catalog links (incl. the NST-2026-0718-1842 → export_1842 label and object_19 "belongs only to"). Full load ≈ 0.3 s. `code/tests/test_evidence_loaders.py`: 14 tests pinned to Phase 1 rows (evidence_54 drift + coverage, evidence_51 empty snapshot, evidence_92 404/anonymized/present, tombstones, evidence_13 trap times, log trace joins incl. old-hash contact record, evidence_61 marker, handover states, uppercase inventory email, search→account ref, activity signals, PDFs). Suite: **93 passed**.
  - Assumptions to validate in 4.9: export with `download_available=false` → ABSENT; a support conversation without an email in its text → REDACTED; a support_replica contact record → CONTACT_RECORD (DELETE, sample case_10).
- [x] 4.3 `code/evidence/images.py` (2026-10-24): validated facts schema → Observations. Facts live in the **committed** `code/llm_cache/image_facts/<file_id>.json` (shipped in code.zip; `code/cache/` stays scratch). Missing facts → the image contributes nothing (currently 11/11 missing until P7). Tests: conversion + validation (bad resource id / bad category rejected), images enter only via facts files.
- [x] 4.4 `code/evidence/index.py` (2026-10-24): `EvidenceIndex` (by_rid, by_key), `state_at(rid, audit_at, since)` = latest usable DIRECT, else the latest qualifying OMISSION coverage; `build(data_dir)` loads everything (~1 s). **New rule (sample-proven): request window** — state evidence must be observed in `[requested_at, audit_at]` (every cited sample evidence is 6.4–30 days after requested_at and ≤5.6 days before audit_at). Tests: direct beats later omission (case_21), omission picks evidence_54 not inventory (case_04) and evidence_51 (case_31), the evidence_13 trap, evidence_06 excluded (case_09), recreation after audit ignored (case_27), earlier-episode evidence dropped (account_6523).
- [x] 4.5 `code/linking.py` L1–L4 (2026-10-24) with a `horizon` for membership. **User-approved amendment (constitution Art. 3.5):** membership may use post-audit evidence; state/citations never. On the samples (non-account resources, with "has in-window state or is a retained audit record"): strict horizon recall 0.823 / precision 1.000; membership-any **0.886 / 1.000** (+5 retained audit records only visible post-audit). Tests: L3 search→account (case_06) with Berglund/Joana decoys excluded, old hash (case_12), old email + popescu decoy (case_10), `.jr` decoy (case_28), catalog link (case_34), horizon effect (case_23 audit_record_4128).
  - Note for 4.7/P5: subjects with an earlier episode (user_17, user_07, user_18) have linked resources whose only in-window state is an OMISSION proof (e.g. account_6523 for case_17). Make sure COMPLETE-case verifications (C4) are not inflated by such stale resources; the workflow account (L5) is the account to verify.
- [ ] 4.6 `linking.py` L5 joint workflow assignment + L6 fallback. Report: unique / resolved-by-elimination / tied counts over all 550 requests; accuracy on the 32 samples' accounts and identifier-less resources.
- [ ] 4.7 `investigate.py`: per-case resource set, state at audit_at, evidence choice. A temporal assertion guards every chosen evidence.
- [ ] 4.8 Decide Q9/Q10/Q11 with data; write the rationale into data_notes §5.
- [ ] 4.9 `code/explore/investigation_report.py`: for the 32 samples, compare the investigated resource set + states + evidence with the expected steps (precision, recall, evidence agreement) and list every miss. For the 518 eval cases: counts by category/state, cases with no account, tied workflows, low-confidence links.
- [ ] 4.10 Performance: the full investigation over 550 requests runs in < 60 s, deterministically (run twice → identical results).

## 5. Exit gate
- [ ] Samples: resource-set recall ≥ 95% and precision ≥ 95% vs expected steps; state agreement 100% on matched resources; evidence_id agreement reported (target ≥ 90%).
- [ ] Every miss is explained in phase4.md (and fixed or accepted with a reason).
- [ ] No temporal violations (assertion active; trap rows excluded).
- [ ] Q9/Q10/Q11 decided and documented.
- [ ] Tests green; deterministic double run; committed.

## 6. Guardrail reminders
- Evidence first: activity results are claims; only observations (and CHECK_*/repopulated signals) give a state.
- Two clocks, always. Never read post-`audit_at` data for a case.
- Exact links only; decoys (`.jr`, popescu, Berglund, user_8741…) must never match.
- No per-case special-casing; every rule must be stated generically and justified by the data.
- State is computed per case (no shared mutable state across cases).
