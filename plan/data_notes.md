# Data Notes

Living findings document for Phase 1. Source scripts: `code/explore/`. Uses IDs rather than personal values wherever possible.

---

## 1. Structured CSVs (task 1.2, from `code/explore/profile_csv.py`)

### 1.1 Timestamps
- All are ISO-8601 UTC with a `Z` suffix and parse with `datetime.fromisoformat(s.replace("Z", "+00:00"))`.
- Requests: `requested_at` 2026-01-05 .. 2026-09-24, `audit_at` 2026-01-29 .. 2026-10-01. `requested_at <= reported_at <= audit_at` always holds.
- Activity runs 2026-01-04 .. 2026-10-01. Evidence `captured_at` runs 2026-01-29 .. 2026-10-01.
- The samples cover only late-season dates (audit 2026-09-03 .. 2026-10-01). Eval cases go back to January, so the temporal filter matters far more on eval than on the samples.
- User audit log: 2024-12-14 .. 2026-06-03. Every identity change predates its user's snapshot `updated_at`.

### 1.2 Requests
| | eval (518) | sample (32) |
|---|---|---|
| `reported_status` COMPLETE / PARTIALLY_COMPLETE / NOT_STARTED | 254 / 152 / 112 | 17 / 5 / 10 |
| email resolves to a **current** email | 418 | 29 |
| email resolves **only via history** (audit `old_value`) | 100 | 3 |
| unresolved / ambiguous | 0 | 0 |

- **Case IDs:** eval is `case_33 .. case_550` (not zero-padded), samples are `case_01 .. case_32`, with no overlap. The input file is in **numeric** order. **Decision:** sort output numerically by the integer suffix, which matches the input order. Lexicographic order would put `case_100` before `case_33` (open question Q1).
- One email is shared by two eval cases (`case_33`, `case_52`) with different time windows. They must be audited independently, each at its own `audit_at`.

### 1.3 Request text (intent): very regular
- Texts are 86–252 chars long and built from a template: one **intent sentence** plus one or two boilerplate sentences.
- **Deletion intent sentences:** 12 English variants plus 5 non-English ones (pt, ko, es, ja, fr; 62 texts with non-ASCII characters). Their trailing sentences are generic ("confirm when complete", "review identifiers…").
- **Non-deletion texts in eval: 11.** Each has a unique first sentence (phone update, stop promo emails, download data, login reset, surname fix, marketing-only removal, what info you hold, invoice copy, change email, copy of info). The second sentence often says so explicitly ("not asking for deletion", "don't delete", "keep the account").
  - Watch the traps: "Please **remove** me from marketing lists only" and "This is an information request, **not a request to erase** it" both contain deletion-like words.
- **Implication:** a rule-based classifier (deletion phrase present AND no negation or non-deletion cue) will probably be exact. An LLM is only a fallback.
- `CLASSIFY_REQUEST` activities (10 rows) say "Privacy intake classified request for account_X as non-deletion". They are a supporting signal, not proof; their count of 10 is close to the 11 texts.

### 1.4 Identities
- `email_hash = sha256(email)`. It matches 850/850, and lowercasing changes nothing, so emails are already lowercase.
- Audit log fields: `email` 107, `email_hash` 107 (always the same timestamp as the email change), `phone` 92. **No name changes.**
- 196 users have history, at most 4 changes per user. The newest `new_value` always equals the current snapshot.
- **Historical identifier set** = every `old_value` and `new_value` per user, plus the current snapshot. Hashes in the history give the old email hashes directly.
- Duplicate names: 3 pairs (decoys), so **never link on name alone**. No duplicate current emails.
- Low user IDs (`user_01 .. user_~22`) appear in the hand-crafted scenario events (LINK_RESOURCE_IDENTITY), which suggests the sample and special scenarios use them.

### 1.5 system_activity (4,011 rows)
Columns: `activity_id,event_time,event_type,source_system,target_system,resource_id,reported_result,details`.

**`details` almost never contains user identifiers.** Only 12 rows (all `LINK_RESOURCE_IDENTITY`) have an email or user_id, and none has a hash. **Linking resources to users must come from the evidence files**, plus these 12 catalog links.

| event_type | source → target | resource prefix | results (S/F/P) | meaning |
|---|---|---|---|---|
| DELETE_RECORD | deletion_worker → account_service / search_service / export_service / support_platform / analytics_platform | account / search / export / support / analytics | 302/368/220 | deletion claim (FAILED and PARTIAL are common) |
| REDACT_RECORD | deletion_worker → support_platform / identity_service | support / tombstone | 47/117/9 | redaction claim (support message, account tombstone) |
| ANONYMIZE_RECORD | deletion_worker → analytics_platform | analytics | 132/64/8 | anonymization claim |
| RETAIN_RECORD | security_service → archive_service; deletion_worker → legal_service | audit_record / legal_hold | 185/15/6 | retention |
| DISABLE_DATA_FLOW | deletion_worker → integration_service | data_flow | 36/0/0 | flow disabled |
| CHECK_DATA_FLOW | deletion_worker → integration_service | data_flow | 89 S | "confirmed that data flow X **remains enabled**" → evidence of an **active flow** |
| BLOCK_RESTORE | deletion_worker → backup_service | backup | 36 S | restore blocked |
| CHECK_RESTORE_ACCESS | deletion_worker → backup_service | backup | 28 S | "archive X **can still be restored**" → evidence of a **restore risk** |
| RESTORE_BACKUP | backup_service → search_service | backup (details name search_X) | 1 S | restore **repopulated** a downstream resource |
| SYNC_RECORD | account_service → analytics_platform / account_replication_cluster / account_failover_replica; integration_service → search_service | analytics / account / data_flow (details name search_X) | 381/20/46 | sync; "Active connector repopulated downstream resource search_X" = recreation |
| INDEX_RECORD | account_service → search_service | search | | index refresh (can recreate a search entry) |
| REFRESH_CACHE | account_service → cache_service | cache | | cache refresh |
| UPDATE_RECORD | profile_service → account_service; support_platform → search_service | account / support | | background noise / possible resurrection |
| SEND_EMAIL | notification_service → email_delivery_service | email_delivery | | email delivery log (REDACT rule_11) |
| CREATE_EXPORT | export_service → object_store | export | | user export (DELETE rule_09) |
| LINK_RESOURCE_IDENTITY | data_catalog → various | various | 12 S | **explicit resource → user link** (email + user_id) |
| CLASSIFY_REQUEST | privacy_intake → privacy_case_management | account | 10 S | non-deletion classification |

Details templates are a small fixed set per event type (see the script output). Notable phrasings:
- "Deletion worker reported the requested operation as completed. Target resource: X" (low-numbered sample resources such as `account_001`)
- "…stopped after the target system returned an error…"
- "…completed some internal work but could not confirm the final state…" (PARTIAL)
- "Replication worker reported its final checkpoint. Target resource: account_005" (a replica-sync scenario)

**Resource ID style:** high random numbers (`search_9729`) are bulk background or decoy rows. Zero-padded low numbers (`account_001`, `search_001`, `analytics_901`, `marketing_001`, `audit_record_003`, `tombstone_17`, `object_19`) are scenario-specific. Do not hardcode this; just be aware of it.

**System naming inconsistencies:** `object_store` (exports) vs `object_storage` (attachment object), and `account_replication_cluster` vs `account_failover_replica`. Treat `system_id` values literally, as they appear in evidence and samples.

### 1.6 Evidence manifest
- 94 files, all present on disk, none unlisted. 30 distinct `origin`s.
- No evidence is captured after every eval `audit_at`, but per-case filtering still matters (`captured_at` runs from 2026-01-29).

### 1.7 Rules (`deletion_rules.csv`)
| rule | category | condition | action |
|---|---|---|---|
| 01 | USER_PROFILE | Always | DELETE |
| 02 | SECONDARY_IDENTIFIER | Always | DELETE |
| 03 | SEARCH_INDEX_ENTRY | Always | DELETE |
| 04 | CACHE_ENTRY | Always | DELETE |
| 05 | SUPPORT_MESSAGE | shared customer/agent/order context | REDACT |
| 06 | SUPPORT_ATTACHMENT | belongs only to the subject | DELETE |
| 07 | ANALYTICS_PROFILE | still attributable | ANONYMIZE |
| 08 | PRODUCT_TELEMETRY | still attributable | ANONYMIZE |
| 09 | USER_EXPORT | Always | DELETE |
| 10 | MARKETING_PROFILE | Always | DELETE |
| 11 | EMAIL_DELIVERY_LOG | contains a user email | REDACT |
| 12 | SECURITY_AUDIT_LOG | within the retention period | RETAIN |
| 13 | LEGAL_HOLD_RECORD | legal hold active | RETAIN |
| 14 | BACKUP_ARCHIVE | restore access can be blocked | RETAIN (+ block restore) |
| 15 | ACCOUNT_TOMBSTONE | account deleted; only a stable user_id needed | REDACT |

Provisional system → category map (to confirm in 1.3–1.6):

| system_id | resource prefix | category | finding / remediation / verification |
|---|---|---|---|
| account_service | account | USER_PROFILE | REMAINING / DELETE / ABSENT |
| account_replication_cluster, account_failover_replica | account | USER_PROFILE (replica copy) | REMAINING / DELETE / ABSENT |
| identity_service | tombstone | ACCOUNT_TOMBSTONE | EXPOSED_PII / REDACT / REDACTED |
| search_service | search | SEARCH_INDEX_ENTRY | REMAINING / DELETE / ABSENT |
| cache_service | cache | CACHE_ENTRY | REMAINING / DELETE / ABSENT |
| support_platform | support | SUPPORT_MESSAGE or SUPPORT_ATTACHMENT | EXPOSED_PII / REDACT, or REMAINING / DELETE |
| object_storage | object | SUPPORT_ATTACHMENT? | REMAINING / DELETE / ABSENT |
| analytics_platform | analytics | ANALYTICS_PROFILE / PRODUCT_TELEMETRY | EXPOSED_PII / ANONYMIZE / ANONYMIZED |
| export_service, object_store | export | USER_EXPORT | REMAINING / DELETE / ABSENT |
| marketing_platform | marketing | MARKETING_PROFILE | REMAINING / DELETE / ABSENT |
| email_delivery_service | email_delivery | EMAIL_DELIVERY_LOG | EXPOSED_PII / REDACT / REDACTED |
| archive_service, security_service | audit_record | SECURITY_AUDIT_LOG | — / — / PRESENT |
| legal_service | legal_hold | LEGAL_HOLD_RECORD | — / — / PRESENT |
| backup_service | backup | BACKUP_ARCHIVE | RESTORE_RISK / BLOCK_RESTORE / RESTORE_BLOCKED |
| integration_service | data_flow | (data flow) | ACTIVE_DATA_FLOW / DISABLE / DISABLED |

---

## 2. SQL snapshots (task 1.3, from `code/explore/load_sql.py`)

All 24 files execute cleanly with `sqlite3.executescript` into an in-memory DB. The flattened rows are cached at `code/cache/extracted/sql_observations.jsonl` (891 observations).

### 2.1 Four file families

| Family | Files (file_id) | Shape | Capture time |
|---|---|---|---|
| **Inventory** `customer_data_inventory_*` | 11 (evidence_63, 66, 69, 72, 75, 78, 81, 84, 87, 90, 93) | 8 typed tables + `snapshot_scope(origin_system, captured_at)` | `snapshot_scope.captured_at` == manifest `captured_at` (all 11) |
| **Replica topology** `customer_data_{read_replica,regional_replicas,reporting_replica,failover_replica}_*` | read: evidence_24, 20, 15, 10, 05 · regional: 38, 33, 29 · reporting: 47, 43 · failover: 52 | `customer_data_primary` + one or more replica tables; columns `resource_id, origin_system, collection_name, record_json, updated_at` | `-- Captured at:` header == manifest |
| **Account failover** `customer_accounts_failover_replica_20260902` | evidence_54 | `customer_profiles_primary` / `customer_profiles_failover_replica` (typed, with `user_id`) | 2026-09-02T23:00Z |
| **Search primary** `customer_search_primary_20260910` | evidence_57 | `search_documents_primary(resource_id, display_name, email, source_resource_id, indexed_at)` | 2026-09-10T08:45Z |

- Topology roles come from the table names: `primary`, `read_replica`, `reporting_replica`, `failover_replica`, `replica_ap_south`, `replica_eu_west`. Replica tables are **separate resource copies**.
- No row has `updated_at` after its file's capture time. **The file's `captured_at` is the observation time.**
- Each `(collection, resource_id)` appears in **one file only** (no multi-snapshot timeline in SQL). The state over time must be combined with the activity log and the JSON/log evidence.
- `customer_data_inventory_20260905` (evidence_90) has **all tables empty** (possible "absence" proof, or a trap; check against the samples).

### 2.2 Collections → system / category / identity fields

| collection (table) | origin_system | resource prefix | likely category (rule) | identity fields | "treated" representation |
|---|---|---|---|---|---|
| customer_profiles (inventory) | account_service | account | USER_PROFILE (01) | email (often UPPERCASE), customer_reference, full_name, phone, email_hash | `account_status` DELETION_PENDING with only the email left |
| customer_profiles (record_json) | account_service | account | USER_PROFILE (01) | customer_reference=user_id, full_name, email, phone | present only in **replicas** (drift; see 2.3) |
| customer_profiles_primary / _failover_replica | (account_service) | account | USER_PROFILE (01) | user_id, full_name, email, phone | row absent from primary but present in failover = drift |
| customer_search_documents | search_service | search | SEARCH_INDEX_ENTRY (03) | inventory: email; record_json: `document{customer_reference, display_name, email}` | — |
| search_documents_primary | search_service | search | SEARCH_INDEX_ENTRY (03) | display_name, email, `source_resource_id` (→ account) | — |
| customer_analytics_profiles (inventory) / customer_analytics_reports | analytics_platform | analytics | ANALYTICS_PROFILE (07) | user_id, email, phone, email_hash | **all identity fields NULL = anonymized**; any present = still attributable |
| support_records (inventory) | support_platform | support | SUPPORT_MESSAGE (05) | requester_email / customer_reference | — |
| support_conversations | support_platform | support | SUPPORT_MESSAGE (05, REDACT) | subject_reference=user_id; **email embedded in `message_text`** (50 rows) | `message_text = "[REDACTED]"` = redacted |
| ticket_attachments | support_platform | support | SUPPORT_ATTACHMENT (06, DELETE) | `uploaded_by` = email | — |
| customer_exports (inventory) / customer_export_jobs | export_service | export | USER_EXPORT (09) | owner_email, owner_phone, customer_reference | `download_available`, `expires_at` |
| connector_subscriptions (inventory) / connector_configurations | integration_service | data_flow | data flow (→ REPORT_ACTIVE_DATA_FLOW) | customer_email / customer_reference; `subject_selector` (email in 43/54) | `enabled` 1/true = active; 0/false = disabled (`last_delivery_status` stopped) |
| backup_restore_entries (inventory) / backup_catalog | backup_service | backup | BACKUP_ARCHIVE (14) | customer_email / customer_reference; `subject_reference` = **email (13) or user_id (11)** | `restore_allowed` 1/true = restore risk; 0/false = blocked |
| security_audit_records (inventory) / security_audit_events | security_service | audit_record | SECURITY_AUDIT_LOG (12, RETAIN) | subject_reference=user_id only | `retention_until` 2031–2034 (inventory) → within retention → VERIFY_RECORD_PRESENT |
| retained_order_records | legal_service | legal_hold | LEGAL_HOLD_RECORD (13, RETAIN) | subject_reference=user_id | `retained_until`, `retention_reason` |
| deleted_customer_references | identity_service | tombstone | ACCOUNT_TOMBSTONE (15, REDACT) | subject_reference=user_id (allowed), name/email/phone/email_hash (prohibited) | **all four prohibited fields NULL = compliant**; any present = REPORT_EXPOSED_PII |

### 2.3 Replication drift observed (replica has an account row the primary lacks)
- evidence_54: `account_005` only in `customer_profiles_failover_replica`. A low-number scenario ID; matches sample case_05's finding.
- evidence_24: account_3150, account_9608 (read_replica) · evidence_20: account_4348 · evidence_15: account_8023 · evidence_10: account_6345 · evidence_05: account_994
- evidence_38: account_5389 (ap_south) · evidence_33: account_6539, account_8105 (eu_west) · evidence_29: account_585 (ap_south)
- evidence_47: account_1035 · evidence_43: account_3183 (reporting_replica)
- Every other collection is identical between the primary and the replicas within a file. **Drift = account rows surviving only in a replica.**
- Open: is the finding's `system_id` `account_service` (sample case_05 uses `account_service/account_005` citing evidence_54) or a replica-specific system? The sample says **`account_service`**, with the resource ID unchanged.

### 2.4 Linking rows to users (identity resolution inputs)
- Link keys: `user_id` / `customer_reference` / `subject_reference` (user_id **or email**), emails (case-insensitive: 9 non-lowercase values, e.g. UPPERCASE), `email_hash`, phones (compare digits only), emails **inside free text** (support `message_text`), `uploaded_by`, `owner_email`, `subject_selector`, `source_resource_id` (search → account).
- **Decoys:** `customer_profiles_primary`/`failover` contain users such as `user_8741`, `user_9116`, `user_7204`, which are **not in user_identities**, with near-duplicate names. `search_documents_primary` has "Jonas Berglund", "Joana Berg" next to "Jonas Berg". So link only on exact identifiers.
- Many inventory rows carry **only an email** (often uppercase) and no user_id, so email normalization is mandatory.
- 289 rows have no identity fields at all (anonymized analytics etc.). They can't be linked to a user by content; possibly via the activity resource_id or the samples' conventions.

### 2.5 Takeaways for later phases
- P3: the identifier set must include lowercase emails, and old emails are needed for inventory rows written before an email change.
- P4: the parsers need one flattener for typed tables, `record_json`, and nested `document`. Regex-extract emails from free text. Normalize booleans (1/0/true/false).
- P5: per-collection "is compliant" predicates: analytics all-null; tombstone prohibited-fields-null; support `[REDACTED]`; connector `enabled=0`; backup `restore_allowed=0`; audit/legal present.

---

## 3. JSON / TXT / LOG evidence (task 1.4)

Scripts: `code/explore/parse_records.py` (931 record observations → `code/cache/extracted/record_observations.jsonl`) and `code/explore/parse_logs.py` (2,211 log events → `log_events.jsonl`, 1,071 trace joins → `log_traces.jsonl`). All files parse, with 0 unparsed log lines.

### 3.1 ⚠️ Temporal rule (most important finding of 1.4)
Observations carry a **record-level time** that can differ from the file's manifest `captured_at`:
- snapshot bundles: `snapshots[].captured_at` (up to ~2 weeks **before** `exported_at`)
- service exports: `observed_at` per row (hours before export)
- ledgers / handover: `recorded_at` per row
- logs: the line timestamp (lines can start days before the file's `captured_at`; the max line time == `captured_at`)
- SQL: no row is newer than the file's capture time

**Trap found:** two ledgers contain rows *after* their own manifest `captured_at`:
- `evidence_13` (captured 2026-08-12T09:00Z): `account_1417` is NOT_FOUND @08-12 but **FOUND @08-14**. Requester `case_135` has `audit_at` = 2026-08-12T09:00Z.
- `evidence_36` (captured 2026-04-09T12:00Z): `account_5043` is **FOUND @04-11**. Requester `case_383` has `audit_at` = 2026-04-09T12:00Z.

These are recreations after the audit that must **not** change the answer.

**Rule (tentative until validated on samples in 1.6):** an observation is usable for a case iff `file.captured_at <= audit_at` **and** `observation_time <= audit_at`. The latest usable observation per resource wins. Cite the observation's `file_id`.

### 3.2 Record files (JSON/TXT)

| Family | file_ids | Structure | Time field |
|---|---|---|---|
| `customer_data_snapshot_bundle_*` (12) | 49, 45, 40, 35, 31, 26, 22, 17, 12, 07, 51, 02 | `{exported_at, source, snapshots[{captured_at, data_store, collection, records[]}]}`; the same collections as the SQL record_json, plus `operational_record_history` (ledger rows with `lookup_value`) | `snapshots[].captured_at` / `recorded_at` |
| `service_resource_export_*` (11) | 62, 65, 68, 71, 74, 77, 80, 83, 86, 89, 92 | `{exported_at, region, service_exports{system{collection[]}}}`. Collections: account `profile_lookups` (**status_code 200 with profile / 404 with profile=null**), analytics `profiles`, backup `restore_entries`, export `exports`, integration `connectors`, search `index_queries` (query email → hits.documents), security `audit_records`, support `tickets` | `observed_at` per row |
| Ledger (3): `connector_configurations_20260812` (13), `customer_export_manifest_20260409` (36), `security_audit_ledger_20261001` (50) | | `{exported_at, origin, record_count, records[{recorded_at, system, resource_id, record_type, result, subject_reference}]}` | `recorded_at` |
| Handover TXT `customer_account_handover_20261001` (03) | | `- ts \| system \| resource_id \| record_type \| result \| identifier` (identifier may be "no direct identifier") | the line ts (all 2026-10-01T12:00Z) |
| Single collection: `customer_analytics_report_20260907` (56), `customer_export_jobs_20260914` (59) | | `{captured_at, source, collection, records[]}` (source = `analytics_identity_store` / `user_export_store`; the system is analytics_platform / export_service) | `captured_at` |

**Ledger vocabulary.** `record_type` **is the `data_category` from `deletion_rules.csv`**, and `result` is the state:

| record_type | system | results seen | meaning |
|---|---|---|---|
| USER_PROFILE | account_service | FOUND / NOT_FOUND | present / absent |
| SEARCH_INDEX_ENTRY | search_service | FOUND | present |
| ANALYTICS_PROFILE | analytics_platform | IDENTIFIABLE / ANONYMIZED | exposed / compliant |
| SUPPORT_MESSAGE | support_platform | IDENTIFIABLE / REDACTED | exposed / compliant |
| SUPPORT_ATTACHMENT | support_platform | FOUND | present (DELETE rule) |
| USER_EXPORT | export_service | FOUND | present |
| DATA_FLOW | integration_service | ACTIVE / DISABLED | flow active / disabled |
| BACKUP_ARCHIVE | backup_service | ACTIVE / BLOCKED | restore possible / blocked |
| SECURITY_AUDIT_LOG | security_service | FOUND | retained (verify present) |
| LEGAL_HOLD_RECORD | legal_service | FOUND | retained (verify present) |

The identifier is `subject_reference` / `lookup_value`: an email (173, sometimes UPPERCASE), a user_id (86), or none (11).

**Empty snapshots** (possible absence proofs): account_service `customer_profiles` is empty in evidence_31 @2026-05-09, evidence_07 @2026-09-11, and evidence_51 @2026-09-15. Plus SQL evidence_90 is entirely empty.

**Search `index_queries`:** always exactly one hit, and the hit's email equals the query (58/58).

### 3.3 Logs (26 files, 7 formats)

| Format | Example files (file_id) | Grammar |
|---|---|---|
| bracket | application_trace_* (16, 44) | `TS [LVL] [service] [trace] event: k="v" …` |
| pipe | operations_stream_* (21, 48) | `TS \| LVL \| service \| trace \| event \| k="v" …` |
| cloud | cloud_runtime_export_* (53, 25) | `TS requestId=trace level=X function=service message="k=\"v\" …"` |
| json | structured_service_events_* (34, 06) | `TS {"severity","service","trace_id","event",…}` |
| syslog | syslog_archive_* (39, 11) | `TS <15>1 node service trace - - level=X k="v" …` |
| logfmt | service_events_* (01, 30), resource_lookup_trace_* (64, 67, 70, 73, 76, 79, 82, 85, 88, 91, 94), support_replica (61) | `TS level=X service=… trace_id=… event=… k=v` |
| logfmt ledger | notification_delivery (41), search_index_diagnostic (08) | `TS INFO service=… event=record_lookup seq=N system= resource_id= record_type= result= subject_reference=` |

**Trace joining is required.** The identifier appears on `*_started` (`lookup_key`, `match_key`, `subject_key`, `subject_ref`, `owner_key`) and the resource and outcome on `*_completed` with the same trace id. Some single lines carry both (`correlation_key`).

**Outcome semantics:**
- account `profile_lookup_completed`: `http_status=404 rows=0` = **absent**; `200 rows=1` = present (sometimes with the remaining fields email/customer_reference/phone)
- search `index_query_completed result=hit` = present
- analytics: `analytics_profile_read direct_identifiers=0` = anonymized; `analytics_identity_scan direct_identifiers=1 matched_value=<email>` = **identifiable**; `analytics_profile_read_completed` with fields shows the raw state
- support: `message_pii_scan detector=direct_identifier matched_value=<email>` = **identifiable message**; `message_read message_text="[REDACTED]"` = redacted; `attachment_pii_scan … file=…pdf` = attachment holds PII; `support_ticket_read_completed` shows the fields
- integration: `connector_heartbeat enabled=true scheduler_registered=true last_run=success` = **active flow**; `connector_config_loaded enabled=false scheduler_registered=false` = disabled; `connector_config_read_completed enabled=…`
- backup: `restore_candidate_evaluated eligible=true deletion_block=false` = **restore risk**; `restore_authorization_completed decision=deny policy=privacy_deletion` = **restore blocked**; `restore_policy_read_completed restore_allowed=true|false archive_present=…`
- export: `export_download_check_completed available=true` / `export_metadata_read_completed available=true` = export present
- security: `audit_record_read_completed rows=1 integrity_check=passed` (+`retention_until`) = retained audit record present
- legal: `retained_order_loaded access=allowed` = legal hold record present
- support_replica (evidence_61): `deletion_marker_check resource_id=support_002 marker_found=false last_write=2026-09-07` = **the replica still holds the record without a deletion marker**. Also a decoy lookup (`nadia.popescu` vs `nadia.ionescu`).

**Noise to ignore:** `connection_acquired` (pool `*_replica` / `*_primary`; not a data-state signal), `dependency_retry/recovered` (route always `primary`), `cache_lookup result=miss`, and infra services (dns_cache, secret_agent, webhook_delivery, systemd, cert_agent, kernel_monitor, thread_pool, runtime_config, http_client, feature_flags, circuit_breaker, scheduler, checkpoint_writer, lambda_extension, queue_consumer, log_router, readback_collector).

**Decoy flood:** evidence_53 has 300 `profile_service` lookups with 5-digit account IDs (e.g. `account_66777`). Their emails belong to known users, but **none is a requester email**. Treat as noise. Linking stays exact, so they never match.

### 3.4 Observation model for Phase 4 (derived from 1.3 + 1.4)
Every evidence source normalizes to:
```
Observation(evidence_id, file_captured_at, observed_at, system_id, resource_id, data_category?, state, exposed_identifiers{}, link_identifiers{}, raw)
```
- `state` ∈ {PRESENT, ABSENT, IDENTIFIABLE, ANONYMIZED, REDACTED, ACTIVE, DISABLED, RESTORE_ALLOWED, RESTORE_BLOCKED}
- link identifiers: emails (lowercased, including emails inside free text), email hashes, phones (digits), user_ids, plus `source_resource_id` / account links
- Activity rows become a second observation stream (claims plus CHECK_* and "repopulated" signals).

---

## 4. PDFs and images (task 1.5)

The PDFs were extracted with `code/explore/extract_docs.py` (pdfplumber; text and tables are clean, with no OCR needed). The PNGs were viewed directly and their facts transcribed. All outputs are `code/cache/extracted/<file_id>.md` (gitignored).

### 4.1 Key observations
- **No sample case cites a PDF or image** (samples cite evidence_01, 03, 05, 51, 54, 56, 57, 58, 59, 61, 92, 93, 94). Exception: evidence_58 (PDF) is cited by case_07. So these artifacts drive **eval-only scenarios** and must be correct without sample feedback.
- **Each artifact pairs with one eval request whose `audit_at` is ~1 day after the capture.** Most are also tied to a `LINK_RESOURCE_IDENTITY` activity row (activity_4000–4011) that grounds resource → user_id + email.
- The images carry **decoys**: other rows in the same screen belong to other people (other backups, other exports, `search_1874` g.silva76**.jr**@…, staff-owned exports).
- **The pipeline cannot rely on manual transcriptions.** It needs a reproducible extractor: an LLM vision call in Phase 7, cached by file hash, prompt in `code/prompts/`. These transcriptions become the **expected values for testing that extractor**.

### 4.2 Artifact → scenario map

| file_id | artifact (captured) | resource / subject | fact shown | catalog link | eval case (audit_at) | implied treatment |
|---|---|---|---|---|---|---|
| evidence_04 | account admin console (09-26 11:00) | account_5762 / user_11 Haruka Sato | live profile with email, phone, orders, support_9538 | activity_4000 (09-26) | case_34 (09-27 13:00) | USER_PROFILE present → REPORT_REMAINING_RECORD |
| evidence_09 | search index inspector (09-01 06:00) | search_428 / user_13 | indexed doc with name and email (+ decoy search_1874) | activity_4001 (09-01) | case_35 (09-02 08:00) | SEARCH_INDEX_ENTRY present |
| evidence_14 | connector console (08-07 08:00) | data_flow_1121 / user_14 | continuous sync selector=email, Healthy | activity_4002 (08-07) | case_39 (08-08 10:00) | REPORT_ACTIVE_DATA_FLOW |
| evidence_18 (PDF) | account history statement (07-18 11:00) | statement NST-2026-0718-1842 / user_18 Ingrid Dahl | customer statement with name, email, address, order | activity_4009 links export_1842 (NST-2026-0718-1842) → user_18 | case_33 (07-19 13:00) | USER_EXPORT export_1842 present |
| evidence_19 | analytics profile view (07-13 10:00) | analytics_7438 / user_20 | identifiable analytics profile | activity_4003 (07-13) | case_50 (07-14 12:00) | ANALYTICS_PROFILE → REPORT_EXPOSED_PII / ANONYMIZE |
| evidence_23 | export console (06-18 12:00) | export_1260 / user_18 | Ready export (+ decoy staff exports) | activity_4004 (06-18) | case_52 (06-19 14:00) | USER_EXPORT present |
| evidence_27 (PDF) | legal retention register (05-29 08:00) | orders of user_08, 12, 17, 21, 24, 29 | disputed orders retained until 2033 | — | (users 08/12/21/24/29 are sample subjects with audit in Sept; user_17 → case_46 / case_17) | LEGAL_HOLD_RECORD → RETAIN (VERIFY_RECORD_PRESENT?). No legal_hold_* id is printed; order refs ORD-2026xxxx |
| evidence_28 | support ticket console (05-24 07:00) | support_1034 / user_22 | shared conversation (customer + agent + order) | activity_4005 (05-24) | case_53 (05-25 09:00) | SUPPORT_MESSAGE → REDACT |
| evidence_32 | backup restore console (04-29 09:00) | backup_9287 / user_16 | archive of the subject, restorable (+ decoy archives) | activity_4006 (04-29) | case_55 (04-30 11:00) | BACKUP_ARCHIVE → REPORT_RESTORE_RISK / BLOCK_RESTORE. Later activity_3387 (08-22) restores backup_9287 → search_4882 (after the audit) |
| evidence_37 + evidence_55 (PDF) | security audit explorer + compliance journal (09-05) | audit_record_003 / user_03 | account closure recorded 08-25, integrity valid, retain until 2027-08-25 | activity_4010 (09-05) | case_45 (09-06 09:00) | SECURITY_AUDIT_LOG → RETAIN → VERIFY_RECORD_PRESENT |
| evidence_42 | deleted account reference (03-10 06:00) | user_17 "Retained reference" (tombstone_17) | only the stable key, no PII | activity_4011 (03-10) | case_46 (03-11 08:00) | ACCOUNT_TOMBSTONE compliant → VERIFY_RECORD_REDACTED. Same-day evidence_67: account_6523 404 |
| evidence_46 | object storage browser (02-13 08:00) | delivery_confirmation_19.pdf = object_19 / user_07 | attachment present in support-attachments bucket | activity_4007 (02-13, "belongs only to" the subject) | case_61 (02-14 10:00) | SUPPORT_ATTACHMENT → DELETE (system `object_storage`) |
| evidence_58 (PDF) | delivery correction attachment (09-12 07:30) | support_001 / user_07 Priya Raman | attachment with name, email, phone, order | — | **sample case_07** (09-12 08:00): REPORT_REMAINING_RECORD support_001 cites evidence_58 | SUPPORT_ATTACHMENT → DELETE (validated ✔) |
| evidence_60 | marketing profile console (09-16 07:20) | marketing_001 | shows "Soo-jin Park / sj.park@naver.com", **not a known user** | activity_4008 (09-16 **07:27**, after the capture) links marketing_001 → kwame-mensah / user_09 | case_63 (09-17 09:20) | MARKETING_PROFILE → DELETE? **conflict: Q9** |

### 4.3 Observed sample conventions (preview of 1.6; confirmed by sample_output)
- Scenario sample cases use zero-padded resources (`account_001..010`, `search_001`, `support_001/002`, `export_001`) that match `case_NN` ↔ `user_NN` in **some** cases (case_07 ↔ user_07 Priya), but **not always**: case_11's subject is not user_11.
- Every INCOMPLETE and COMPLETE case verifies the subject's **account** (`VERIFY_RECORD_ABSENT account_service/account_X`), even when the account isn't a finding.
- Bulk-template cases also verify a **security audit record present** (`VERIFY_RECORD_PRESENT security_service/audit_record_X`).

---

## 4b. Final catalogue (task 1.7): system → category → operations

✔ = confirmed by sample outputs; ◇ = inferred from rules + evidence (no sample).

| system_id (as emitted) | resource prefix | evidence sources | category → rule | non-compliant state → FINDING / REMEDIATION / VERIFICATION | compliant state → COMPLETE verification | status |
|---|---|---|---|---|---|---|
| account_service | account | SQL profiles (incl. replica tables), profile_lookups 200/404, ledgers USER_PROFILE, log profile lookups, empty snapshots | USER_PROFILE → 01 DELETE | present (any table/replica) → REMAINING / DELETE / ABSENT | absent → VERIFY_RECORD_ABSENT (always emitted, C2) | ✔ |
| search_service | search | SQL/bundle search docs, index_queries, log index hits, ledgers SEARCH_INDEX_ENTRY, search_documents_primary | SEARCH_INDEX_ENTRY → 03 DELETE | present → REMAINING / DELETE / ABSENT | (absent → not listed unless remediated; no COMPLETE sample shows search) | ✔ |
| analytics_platform | analytics | analytics reports/profiles, log analytics reads and scans, ledgers | ANALYTICS_PROFILE → 07 ANONYMIZE; **keyed only by an old identifier (contact lookup by hash) → DELETE** (C18) | identifiable → EXPOSED_PII / ANONYMIZE / ANONYMIZED; contact-hash record → REMAINING / DELETE / ABSENT | all identifiers null → VERIFY_RECORD_ANONYMIZED | ✔ |
| support_platform | support | conversations, tickets, attachments, pii scans, support_replica log, ledgers SUPPORT_MESSAGE / SUPPORT_ATTACHMENT, PDF attachment | SUPPORT_MESSAGE → 05 REDACT; SUPPORT_ATTACHMENT / subject-only contact record → 06 DELETE | message identifiable → EXPOSED_PII / REDACT / REDACTED; attachment or contact present → REMAINING / DELETE / ABSENT | message `[REDACTED]` / no identifiers → VERIFY_RECORD_REDACTED | ✔ |
| export_service | export | export jobs/exports (owner_email), export download logs, ledgers USER_EXPORT, export console image, statement PDF | USER_EXPORT → 09 DELETE | present/available → REMAINING / DELETE / ABSENT | — | ✔ |
| integration_service | data_flow | connector configs/subscriptions (enabled), heartbeats, ledgers DATA_FLOW, connector console image, CHECK_DATA_FLOW activity | data flow (no rule row) | enabled/ACTIVE → ACTIVE_DATA_FLOW / DISABLE / DISABLED | enabled=false/DISABLED → VERIFY_DATA_FLOW_DISABLED | ✔ |
| backup_service | backup | backup catalog / restore entries (restore_allowed), restore logs, ledgers BACKUP_ARCHIVE, backup console image, CHECK_RESTORE_ACCESS activity | BACKUP_ARCHIVE → 14 RETAIN + block | restorable/ACTIVE → RESTORE_RISK / BLOCK_RESTORE / RESTORE_BLOCKED | restore_allowed=false/BLOCKED/deny → VERIFY_RESTORE_BLOCKED | ✔ |
| security_service | audit_record | audit events/records, audit reads, ledgers SECURITY_AUDIT_LOG, Sentinel image, compliance PDF | SECURITY_AUDIT_LOG → 12 RETAIN | — (never remediated) | present → VERIFY_RECORD_PRESENT (COMPLETE: cited; INCOMPLETE: "") | ✔ |
| identity_service | tombstone | deleted_customer_references, reference-registry image, catalog link | ACCOUNT_TOMBSTONE → 15 REDACT | any of name/email/phone/hash → EXPOSED_PII / REDACT / REDACTED | all null → VERIFY_RECORD_REDACTED | ✔ |
| legal_service | legal_hold | retained_order_records, retained_order_loaded log, ledgers LEGAL_HOLD_RECORD, legal register PDF (no IDs) | LEGAL_HOLD_RECORD → 13 RETAIN | — | present → VERIFY_RECORD_PRESENT | ◇ (no sample) |
| marketing_platform | marketing | evidence_60 screenshot + activity_4008 only | MARKETING_PROFILE → 10 DELETE | present → REMAINING / DELETE / ABSENT | — | ◇ (Q9) |
| object_storage | object | evidence_46 screenshot + activity_4007 only | SUPPORT_ATTACHMENT → 06 DELETE ("belongs only to the subject") | present → REMAINING / DELETE / ABSENT | — | ◇ |
| cache_service | cache | **activity only** (REFRESH_CACHE), no state evidence | CACHE_ENTRY → 04 DELETE | not groundable → do not emit | — | ◇ never emitted |
| email_delivery_service | email_delivery | **activity only** (SEND_EMAIL) | EMAIL_DELIVERY_LOG → 11 REDACT | not groundable → do not emit | — | ◇ never emitted |
| (account_replication_cluster, account_failover_replica) | account | activity SYNC only | — | replica rows are reported as `account_service` (C12) | — | ✔ (via case_05/16) |

---

## 5. Open questions
- **Q1.** Output sort is numeric vs lexicographic `case_id`. Using numeric (matches the input file); the grader most likely joins on `case_id`.
- **Q2.** ~~Which time is the cutoff?~~ Tentatively resolved in §3.1: an observation is usable iff `file.captured_at <= audit_at` and `observation_time <= audit_at`; activity uses `event_time <= audit_at`. Validate on the samples (1.6).
- **Q3.** How are high-numbered background resources linked to users? Expected to come through SQL, JSON, and log evidence (tasks 1.3–1.4).
- **Q4.** Which evidence ID is cited when an activity row and a file both prove a fact? To learn from the samples (task 1.6).
- **Q5.** How is SUPPORT_MESSAGE (REDACT) told apart from SUPPORT_ATTACHMENT (DELETE) on support_platform?
- **Q6.** Do empty snapshots (evidence_90 SQL; empty account_service collections in evidence_31/07/51) prove absence for *every* account, or are they just empty extracts? Resolve in 1.6 against the samples.
- **Q7.** When several usable observations prove the same state, which `evidence_id` is cited (latest before `audit_at`? most specific source? file vs activity)? Resolve in 1.6.
- **Q8.** How are support messages (REDACT) vs attachments (DELETE) identified when only a `support_*` resource ID is seen (ticket_attachments / attachment_pii_scan / SUPPORT_ATTACHMENT ledger = attachment)? Resolve in 1.6.
- **Q9.** marketing_001 (evidence_60) displays identifiers of an unknown person ("Soo-jin Park", sj.park@naver.com) while activity_4008 (7 minutes *after* the screenshot) links it to user_09 / kwame-mensah@proton.me (case_63). Is it the subject's remaining MARKETING_PROFILE (cite activity_4008 and/or evidence_60) or a decoy to exclude because no subject identifier appears in the record? Decide in P4 with the general linking rule (catalog link = grounded link?), and record the rationale.
- **Q10.** The legal retention register (evidence_27) lists order refs with user_ids but no `legal_hold_*` resource IDs. How do LEGAL_HOLD_RECORD steps get their resource_id (retained_order_records rows `legal_hold_NNNN` ↔ `ORD-2026NNNN`)? Resolve in 1.6/P4.
