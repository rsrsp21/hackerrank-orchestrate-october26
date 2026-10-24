<!-- prompt_version: image_facts/v2 — used by code/image_extract.py. Changing this text invalidates cached answers. -->
You are reading one screenshot of an internal business console of an online shop. Extract **facts only**, exactly as shown. Do not judge whether anything is compliant, deleted correctly, or belongs to anyone in particular.

Return one JSON object:

```
{"records": [
  {"resource_id": "...", "labels": ["..."], "category": "...", "state": "...",
   "emails": ["..."], "phones": ["..."], "user_ids": ["..."], "references": ["..."]}
]}
```

Include **one record for every data row or record shown on the screen**, including rows in tables and lists, not only the highlighted one. Ignore navigation menus, charts, and summary tiles.

Field rules:
- `resource_id`: an identifier printed on screen that has the form `<prefix>_<digits>` with prefix one of account, search, support, analytics, export, data_flow, backup, audit_record, legal_hold, tombstone, marketing, object. Copy it exactly. If the record shows no such identifier, use "".
- `labels`: other printed references of that record exactly as shown: file names (for example `something_12.pdf`), ticket or case numbers, statement or order numbers, and bare user ids like `user_12` when the record is identified only by them. Use [] if none.
- `emails`, `phones`: every email address and phone number displayed for that record, exactly as shown. Use [] if none.
- `user_ids`: every `user_<digits>` value displayed for that record. Use [] if none.
- `references`: other `<prefix>_<digits>` identifiers shown as linked to this record (for example a support ticket id listed on a customer page). Use [] if none.
- `category` — choose exactly one:
  - USER_PROFILE: a customer account or profile page or row.
  - SEARCH_INDEX_ENTRY: a document or hit in a search index.
  - ANALYTICS_PROFILE: a user profile in an analytics tool.
  - SUPPORT_MESSAGE: a support ticket or conversation.
  - SUPPORT_ATTACHMENT: a file attached to a support case or stored as a support attachment.
  - USER_EXPORT: a customer data export or download package.
  - MARKETING_PROFILE: a profile in a marketing or audience tool.
  - DATA_FLOW: a connector, sync, or integration that sends data to another system.
  - BACKUP_ARCHIVE: a backup or archive that can be restored.
  - SECURITY_AUDIT_LOG: a security or audit event record.
  - LEGAL_HOLD_RECORD: a record kept for legal, tax, or dispute reasons.
  - ACCOUNT_TOMBSTONE: a retained reference to a deleted or closed account.
- `state` — choose exactly one that matches the category:
  - PRESENT: the record exists (any category except the ones below).
  - ABSENT: the screen says the record is deleted, expired, or no longer available.
  - IDENTIFIABLE: for ANALYTICS_PROFILE when a name, email, phone, or user id of a person is displayed; for SUPPORT_MESSAGE or ACCOUNT_TOMBSTONE when a name, email, or phone of a person is displayed.
  - ANONYMIZED: for ANALYTICS_PROFILE when no name, email, phone, or user id is displayed.
  - REDACTED: for SUPPORT_MESSAGE or ACCOUNT_TOMBSTONE when no name, email, or phone is displayed (an internal reference such as a user id may remain).
  - FLOW_ACTIVE / FLOW_DISABLED: for DATA_FLOW when it is running, healthy, enabled, or continuous / paused, stopped, or disabled.
  - RESTORE_ALLOWED / RESTORE_BLOCKED: for BACKUP_ARCHIVE when nothing on screen blocks restoring it / when restore is shown as blocked or denied.

Return only the JSON object.
