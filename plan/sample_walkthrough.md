# Sample Walkthrough (task 1.6)

Every step of all 32 sample answers, explained from participant evidence. Generated with `code/explore/sample_walkthrough.py` (per-case timelines) plus targeted checks. **The samples teach conventions; they are never used as a lookup table.**

---

## 1. Conventions learned (apply to every case)

| # | Convention | Evidence in samples | Confidence |
|---|---|---|---|
| C1 | **Status:** COMPLETE iff no findings at `audit_at`. `reported_status` is irrelevant (case_02, 25, 26, 28 were reported PARTIAL/NOT_STARTED but are COMPLETE; case_05, 07, 10, 11, 12, 14, 15, 18, 22, 24, 30 were reported COMPLETE but are INCOMPLETE). | all | high |
| C2 | **Every deletion case verifies the subject's account** `VERIFY_RECORD_ABSENT account_service/<account>`, even when the account is not a finding. COMPLETE: cites the absence proof. INCOMPLETE: empty evidence. | all 32 | high |
| C3 | **Retained security audit record:** if the subject has a `SECURITY_AUDIT_LOG` record (audit_record_*, subject_reference=user_id) observed at or before audit, add `VERIFY_RECORD_PRESENT security_service/<audit_record>`. Never a finding or remediation. ⚠ For case_18 (audit_record_6645) and case_20 (audit_record_5569) the expected record appears **nowhere** in participant data, so it is unreachable; emit only grounded records. | 03, 09, 11–32 (not the scenario cases 01–08, 10, which have no such record) | high |
| C4 | **COMPLETE cases also verify every already-treated item** with its compliant state and the proving evidence: anonymized analytics → VERIFY_RECORD_ANONYMIZED; redacted support message → VERIFY_RECORD_REDACTED; disabled flow → VERIFY_DATA_FLOW_DISABLED; blocked backup → VERIFY_RESTORE_BLOCKED; redacted tombstone → VERIFY_RECORD_REDACTED. | 03, 04, 21, 25–28, 31 | high |
| C5 | **INCOMPLETE:** each finding gets one remediation and one verification. Verification = remediated items + account ABSENT (C2) + retained audit PRESENT (C3). Remediation and verification evidence = "". | 05–20, 22–24, 29, 30, 32 | high |
| C6 | **Operation mapping:** DELETE category → REPORT_REMAINING_RECORD / DELETE_RECORD / VERIFY_RECORD_ABSENT. REDACT → REPORT_EXPOSED_PII / REDACT_RECORD / VERIFY_RECORD_REDACTED. ANONYMIZE → REPORT_EXPOSED_PII / ANONYMIZE_RECORD / VERIFY_RECORD_ANONYMIZED. Flow → REPORT_ACTIVE_DATA_FLOW / DISABLE_DATA_FLOW / VERIFY_DATA_FLOW_DISABLED. Backup → REPORT_RESTORE_RISK / BLOCK_RESTORE / VERIFY_RESTORE_BLOCKED. | 11, 18, 29, 30 show all kinds | high |
| C7 | **Ordering:** phase, then operation-table index, then `system_id`, then `resource_id` (plain string sort). Example (case_11 findings): REMAINING search → EXPOSED analytics → EXPOSED support → ACTIVE_FLOW; remediation DISABLE → DELETE → REDACT → ANONYMIZE; verification ABSENT(account, search) → PRESENT → REDACTED → ANONYMIZED → DISABLED. | all | high |
| C8 | **Evidence choice:** all findings in a case cite the capture taken closest before `audit_at` that observes the resource (one file per case in practice: evidence_92/01 for 09-15 audits, 05 for 09-21, 94 for 09-26, 03 for 10-01, 93 for 09-16). File-level `captured_at` must be ≤ `audit_at`; **equality is allowed** (case_11/13/14: evidence_03 captured exactly at audit 10-01T12:00). **Refined in P4 planning:** a DIRECT observation (resource named) beats an OMISSION proof even if the omission is later (case_21 cites evidence_92's 404, not the later empty evidence_51). Omission proofs come only from topology DB snapshots (evidence_54) and explicit empty bundle snapshots (evidence_51), never from the empty SQL inventory evidence_90 (case_04 → evidence_54). | all | high (verify in P4) |
| C9 | **Two-clock temporal rule confirmed:** case_09 cites evidence_93 (SQL, 08:37), **not** evidence_06 (log lines at 08:57 < audit 09:00, but file captured 09-18 > audit). | 09 | high |
| C10 | **Recreation after audit is ignored:** case_27: account_3866 is 404 at 09-15 (evidence_92) and present again on 09-17 (evidence_02) → COMPLETE. case_26: account_5684 present 09-09 inside evidence_02 (file exported 09-17 > audit) → not usable; 404 at 09-15 → absent. | 26, 27 | high |
| C11 | **Decoys excluded:** case_28 search_8168 (`smartinez6461.jr@…` ≠ subject); case_06 Jonas Berglund / Joana Berg search docs; case_10 nadia.popescu vs nadia.ionescu; evidence_56 analytics_824 (other user). | 06, 10, 28 | high |
| C12 | **Replication drift → finding on `account_service` with the replica's resource_id**: case_05 account_005 only in the failover table (evidence_54); case_16 account_994 only in the read replica (evidence_05). The system_id stays `account_service`. | 05, 16 | high |
| C13 | **Account record present (200 with identifiers) → REPORT_REMAINING_RECORD account** and the same account in verification (it's also the C2 item, not duplicated). | 05, 16, 24 | high |
| C14 | **Absence proofs:** (a) the resource is missing from a snapshot table that is the authoritative extract (evidence_54 for account_001/002/004); (b) a 404 lookup (evidence_92, 94, 01); (c) an empty account_service snapshot (evidence_51 → case_31 account_4857). | 01, 02, 04, 21, 25–28, 31 | medium-high |
| C15 | **Restore risk** = backup restore_allowed=1/true (SQL inventory evidence_93), or log `restore_candidate_evaluated eligible=true deletion_block=false` (evidence_01), or handover/ledger `BACKUP_ARCHIVE ACTIVE` (evidence_03). Treatment BLOCK_RESTORE; the backup is retained (never deleted). | 09, 14, 17 | high |
| C16 | **Active flow** = connector enabled=true / `DATA_FLOW ACTIVE` / heartbeat. Replication `SYNC_RECORD` checkpoints are **not** reported as flows (case_05). | 11, 15, 18, 20, 29, 30 vs 05 | high |
| C17 | **Support:** SUPPORT_MESSAGE that still exposes PII (IDENTIFIABLE / pii scan / requester_email) → EXPOSED_PII + REDACT (the conversation is retained). SUPPORT_ATTACHMENT / a record belonging only to the subject → REMAINING + DELETE (case_07 attachment PDF support_001; case_13 support_4218 SUPPORT_ATTACHMENT FOUND; case_10 support_002 legacy contact replica with marker_found=false). | 07, 10, 11, 13, 18, 19, 29, 30 | high |
| C18 | **Analytics keyed only by an (old) identifier, e.g. an email hash in a contact lookup → REPORT_REMAINING_RECORD + DELETE** (case_12 analytics_9914 via the old hash, `contact_lookup_completed email_opt_in=true`). An analytics profile with direct identifiers → EXPOSED_PII + ANONYMIZE. | 12 vs 11/18/22/29/30 | medium (one example) |
| C19 | **Tombstone:** `deleted_customer_references` with any of name/email/phone/email_hash → EXPOSED_PII + REDACT; all null → VERIFY_RECORD_REDACTED (COMPLETE). Never DELETE. | 31, 32 | high |
| C20 | Non-deletion (NOT_APPLICABLE) cases do not appear in the samples. | — | — |

---

## 2. How resources are linked to the subject (critical for P4)

| Link mechanism | Example | Notes |
|---|---|---|
| L1 Direct identifier in the record (email, any case; email hash, including old ones; phone; user_id as customer_reference / subject_reference / user_id) | most findings | exact match only |
| L2 Lookup key in an audit-time log trace (`lookup_key`/`match_key`/`subject_key`/`correlation_key`=email or user_id → resource_id + outcome) | case_12 account_9797 404, case_17 account_4092 404, backup_3245 | joins started → completed by trace id |
| L3 Cross-resource reference | case_06 `search_documents_primary.source_resource_id = account_006` | gives the account id |
| L4 Data-catalog link rows (`LINK_RESOURCE_IDENTITY`) | eval scenarios (activity_4000–4011) | resource → email + user_id |
| L5 **Workflow timing**: the request's deletion workflow in `system_activity` (account `DELETE_RECORD` 0–75 min before `reported_at`; `reported_result` ↔ `reported_status`: COMPLETE↔SUCCESS, PARTIALLY_COMPLETE↔PARTIAL, NOT_STARTED↔FAILED), then the policy actions/checks within ~3h | case_21 account_6440 (activity_3661) + analytics_5335 (activity_3665); case_09 account_3960; case_04 analytics_901 (activity_3463) | the **only** link for absent/anonymized records that carry no identifiers. Concurrent workflows collide (up to 6 requests share a `reported_at`): 207/550 requests have a unique candidate; resolve the rest jointly with L1–L4 and elimination |
| L6 Naming convention for hand-built scenario accounts (`user_0N` ↔ `account_00N`) | case_04 account_004 appears **nowhere** in participant data | fallback only; flag as low-confidence |

---

## 3. Per-case explanations

Notation: `ev` = cited evidence. "WF" = workflow-timing link (L5). All audit-time files are ≤ audit_at unless noted.

| case | subject (match) | true status (reported) | steps → why |
|---|---|---|---|
| 01 | user_01 (current) | COMPLETE (COMPLETE) | account_001 ABSENT ← not in evidence_54 primary/failover account tables (captured 09-02 23:00 ≤ audit 09-03); WF activity_3342 SUCCESS |
| 02 | user_02 (current) | COMPLETE (PARTIAL) | account_002 ABSENT ← evidence_54; WF activity_3376 PARTIAL is just a claim |
| 03 | user_43 (current) | COMPLETE | evidence_94 (readback 09-26): account_7566 404 → ABSENT; audit_record_2016 present → PRESENT; analytics_9406 identifiers null → ANONYMIZED (WF activity_3852) |
| 04 | user_04 (current) | COMPLETE | account_004 ABSENT ← evidence_54 (L6: id exists nowhere); analytics_901 all-null in evidence_56 → ANONYMIZED (WF activity_3463); decoy analytics_824 = another user |
| 05 | user_05 (current) | INCOMPLETE (COMPLETE) | account_005 only in `customer_profiles_failover_replica` (evidence_54) → REMAINING/DELETE/ABSENT (C12); SYNC checkpoint activity_3483 is not a flow finding |
| 06 | user_06 (current) | INCOMPLETE | search_001 "Jonas Berg" jonas.berg@… in evidence_57 (source_resource_id=account_006 → L3) → REMAINING/DELETE; verify account_006 + search_001 ABSENT; decoys Berglund/Joana |
| 07 | user_07 (current) | INCOMPLETE | support_001 delivery-correction attachment PDF with name/email/phone (evidence_58, 09-12 07:30 ≤ 08:00) → SUPPORT_ATTACHMENT REMAINING/DELETE; verify account_007 (WF activity_3590) |
| 08 | user_08 (current) | INCOMPLETE | export_001 owner_email = subject, download_available=true (evidence_59, 09-14 15:40) → USER_EXPORT REMAINING/DELETE; account_008 (WF activity_3554) |
| 09 | user_61 (current) | INCOMPLETE (NOT_STARTED) | backup_4978 customer_email = subject, restore_allowed=1 in SQL inventory evidence_93 (09-16 08:37) → RESTORE_RISK/BLOCK; account_3960 (WF activity_3703 FAILED); audit_record_4902 PRESENT. evidence_06 excluded (C9) |
| 10 | user_10 (**historical** via audit_121) | INCOMPLETE (COMPLETE) | support_002 legacy-contact replica hit for the **old** email, `deletion_marker_check marker_found=false` (evidence_61) → REMAINING/DELETE; decoy nadia.popescu → support_5914; account_010 (WF activity_3595) |
| 11 | user_32 (current) | INCOMPLETE (COMPLETE) | handover evidence_03 (10-01 12:00 = audit): search_052 FOUND → REMAINING/DELETE; analytics_2034 IDENTIFIABLE → EXPOSED/ANONYMIZE; support_864 IDENTIFIABLE → EXPOSED/REDACT; data_flow_9522 ACTIVE → FLOW/DISABLE; account_4248 NOT_FOUND → verify ABSENT; audit_record_9394 (user_32) PRESENT |
| 12 | user_12 (current; old email minjun.kim90) | INCOMPLETE (COMPLETE) | evidence_01: analytics_9914 `contact_lookup_completed` keyed by the **old email hash**, email_opt_in=true → REMAINING/DELETE (C18); account_9797 404 (L2); audit_record_2945 PRESENT |
| 13 | user_33 (current) | INCOMPLETE (NOT_STARTED) | evidence_03: search_1308 FOUND → REMAINING; support_4218 SUPPORT_ATTACHMENT FOUND → REMAINING/DELETE; account_9335 NOT_FOUND; audit_record_4816 PRESENT |
| 14 | user_37 (current) | INCOMPLETE (COMPLETE) | evidence_03: backup_3870 BACKUP_ARCHIVE ACTIVE → RESTORE_RISK/BLOCK; account_3677 NOT_FOUND; audit_record_987 PRESENT |
| 15 | user_15 (current) | INCOMPLETE (COMPLETE) | evidence_01: data_flow_9846 enabled (selector = subject email) → FLOW/DISABLE; account_4745 (WF activity_3382); audit_record_1596 PRESENT |
| 16 | user_53 (current) | INCOMPLETE (NOT_STARTED) | evidence_05 (read replica 09-21): account_994 only in the replica table → REMAINING/DELETE (C12); search_1007 present → REMAINING/DELETE; audit_record_9528 PRESENT |
| 17 | user_17 (current) | INCOMPLETE (NOT_STARTED) | evidence_01: backup_3245 `restore_candidate_evaluated eligible=true deletion_block=false` → RESTORE_RISK/BLOCK; account_4092 (404 via L2 + WF activity_3383); account_6523 (belongs to the earlier 03-10 workflow) not used; audit_record_1797 PRESENT |
| 18 | user_50 (current) | INCOMPLETE (COMPLETE) | evidence_94: search_4013, analytics_037 identifiable, support_5569 identifiable, data_flow_4890 enabled → 4 findings; account_5521 (WF activity_3732); audit_record_6645 PRESENT — ⚠ **not in any participant file** (unreachable) |
| 19 | user_19 (current) | INCOMPLETE (PARTIAL) | evidence_01: search_6083 → REMAINING; support_9553 PII in a shared conversation → EXPOSED/REDACT (request text says the conversation involves another customer); account_9102; audit_record_6793 |
| 20 | user_48 (current) | INCOMPLETE (NOT_STARTED) | evidence_94: search_4262 → REMAINING; data_flow_1770 enabled → FLOW; account_5037 (WF activity_3734); audit_record_5569 — ⚠ **not in any participant file** (unreachable) |
| 21 | user_21 (current) | COMPLETE (COMPLETE) | evidence_92: account_6440 404 (WF activity_3661 — no identifier anywhere) → ABSENT; audit_record_3737 (user_21) PRESENT; analytics_5335 all-null (WF activity_3665) → ANONYMIZED |
| 22 | user_51 (current) | INCOMPLETE (COMPLETE) | evidence_05: search_8911 → REMAINING; analytics_4440 identifiable → EXPOSED/ANONYMIZE; account_4990; audit_record_3482 |
| 23 | user_23 (current) | INCOMPLETE (NOT_STARTED) | evidence_92: export_7364 owner_email = subject → REMAINING/DELETE; search_898 (query hit) → REMAINING/DELETE; account_410 (WF activity_3662 FAILED); audit_record_4128 |
| 24 | user_24 (current) | INCOMPLETE (COMPLETE) | evidence_92: account_5334 lookup 200 with the email → REMAINING/DELETE (C13); search_5577 hit → REMAINING; audit_record_7095 |
| 25 | user_25 (current) | COMPLETE (NOT_STARTED) | evidence_92: account_3136 404 (WF, disambiguated from account_5684 = user_26 by elimination) → ABSENT; audit_record_451 PRESENT; analytics_1895 all-null → ANONYMIZED (WF; **ambiguous with analytics_4566** for case_26 — same minute) |
| 26 | user_26 (current) | COMPLETE (NOT_STARTED) | evidence_92: account_5684 404 → ABSENT (the 09-09 presence is inside a file exported 09-17 → unusable, C10); audit_record_5416; support_4715 (customer_reference user_26, excerpt only) → REDACTED; analytics_4566 → ANONYMIZED; data_flow_6244 (user_26, enabled=false) → DISABLED; backup_3120 (user_26, restore_allowed=false) → BLOCKED |
| 27 | user_27 (current) | COMPLETE (COMPLETE) | evidence_92: account_3866 404 → ABSENT (the 09-17 reappearance is ignored, C10); audit_record_3830; support_4707 REDACTED; analytics_4574 ANONYMIZED; data_flow_2295 DISABLED; backup_5970 BLOCKED |
| 28 | user_28 (current) | COMPLETE (NOT_STARTED) | evidence_92: account_5482 404; audit_record_9265; support_2351; analytics_6077; data_flow_2337; backup_838 — all compliant; decoy search_8168 (`.jr` email) excluded (C11) |
| 29 | user_29 (**historical** via audit_284) | INCOMPLETE (NOT_STARTED) | evidence_92 under the **old** email noah.f438085: search_1993 → REMAINING; analytics_5208 email → EXPOSED/ANONYMIZE; support_5281 requester_email → EXPOSED/REDACT; data_flow_3827 enabled → FLOW; account_7012 (WF); audit_record_3954 |
| 30 | user_30 (**historical** via audit_280) | INCOMPLETE (COMPLETE) | evidence_92 (old email camille.bernard86): search_9359, analytics_3697, support_6477, data_flow_8524 → 4 findings; account_4163 (WF); audit_record_1707 |
| 31 | user_541 (current) | COMPLETE (COMPLETE) | evidence_51 (bundle 09-15 12:00 = audit): empty account_service snapshot → account_4857 ABSENT (WF activity_3682); audit_record_6909 (user_541) PRESENT; tombstone_440 all prohibited fields null → REDACTED |
| 32 | user_542 (current) | INCOMPLETE (PARTIAL) | evidence_51: tombstone_9178 still has name/email/phone/hash → EXPOSED/REDACT (C19); account_8858 (WF activity_3685 PARTIAL); audit_record_7068 PRESENT |

---

## 3b. Reachability audit (added in the Phase 1–3 review, 2026-10-24)
Over the 193 expected sample steps: **177** reference a resource present in evidence content (including support_001 inside PDF evidence_58), **13** reference accounts that appear **only in activity rows** (reachable only via workflow timing, L5), and **3** reference resources that appear **nowhere** in participant data (account_004 via the L6 naming fallback only; audit_record_6645 and audit_record_5569 not at all). Ceiling ≈ 98.4% of sample steps from evidence; the L6 fallback can recover account_004. Never fabricate the other two.

## 4. Open questions — status after 1.6
- **Q1** case_id sort → numeric (unchanged; samples are zero-padded and give no signal).
- **Q2** temporal rule → **confirmed** (C9, C10).
- **Q3** linking of background resources → L1–L6 (§2). Workflow timing (L5) is essential and needs a joint assignment.
- **Q4/Q7** evidence choice → C8 (closest capture ≤ audit_at that observes the resource); validate via the P6 metrics.
- **Q5/Q8** support message vs attachment → C17.
- **Q6** empty snapshots → evidence_51's empty account_service snapshot **is** used as an absence proof (case_31). evidence_90 (all-empty SQL, scope account_service, 09-05) is unused by samples; treat the same way when it is the closest capture.
- **Q9** marketing_001 conflict and **Q10** legal-hold resource IDs → still open (eval-only; decide in P4).
- **New Q11:** for colliding workflows with no identifier link (analytics_1895 vs analytics_4566), is there any principled tiebreak? Candidates: joint consistency with linked siblings in the same burst; the record order inside the snapshot bundle follows user order (generator artifact; use only as a last-resort tiebreak and document it).
