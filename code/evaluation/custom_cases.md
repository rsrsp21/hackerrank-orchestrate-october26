# Custom Evaluation Cases

Hand-written cases that exercise behaviour the public samples do not cover (the samples contain no NOT_APPLICABLE case). Each case lists its input, the expected output, and the reasoning. Phase 6 runs these through the full pipeline and reports the results in `evaluation_report.md`.

Status legend: **drafted** (expected output written) → **automated** (in the harness) → **passing**.

---

## Intent cases (Phase 2)

### CC-01: Spanish refusal with a deletion verb
- **request_text:** `No quiero eliminar mi cuenta, solo cambiar el correo.`
- **Expected:** `NOT_APPLICABLE`, `[]`
- **Why:** the deletion verb *eliminar* is negated (*No quiero*). The request is a correction. Tests override-before-deletion ordering in a non-English language.
- Status: drafted, intent unit test passing.

### CC-02: marketing opt-out phrased with "remove"
- **request_text:** `Please remove me from your mailing list.`
- **Expected:** `NOT_APPLICABLE`, `[]`
- **Why:** "remove me from … mailing list" is a marketing opt-out, which AGENTS.md §6.5 lists as non-deletion. It contains the word *remove*, so it guards against keyword-only classifiers.
- Status: drafted, intent unit test passing.

### CC-03: restore request that mentions deletion
- **request_text:** `My account was deleted by mistake. Could you restore it?`
- **Expected:** `NOT_APPLICABLE`, `[]`
- **Why:** the subject wants the account back, so no destructive action is authorized even though "deleted" appears.
- Status: drafted, intent unit test passing.

### CC-04: deletion with retention clauses (must stay a deletion)
- **request_text:** `I want my account closed and every trace of me removed. Backups may be kept if they cannot restore my profile.`
- **Expected:** a deletion case (status decided by evidence). Backups → BLOCK_RESTORE, never DELETE.
- **Why:** retention wording ("may be kept", "restore") must not flip the intent to non-deletion.
- Status: drafted (intent unit test passing; full-pipeline expectation added in Phase 6).

### CC-05: combined opt-out and deletion
- **request_text:** `Please unsubscribe me and delete my account entirely.`
- **Expected:** a deletion case.
- **Why:** an opt-out topic co-occurs with an explicit deletion request, and the deletion must win.
- Status: drafted, intent unit test passing.

---

Pipeline-level custom cases (historical email, temporal cut-off, tombstone, legal hold, restore risk) are added in Phase 6 with full expected `steps_json`.

---

## Identity cases (Phase 3)

### CC-06: identity invariance, current email of a sample subject that was requested via the old email
- **Input:** `case_id=cc_06, email=noah.f4380@outlook.com` (user_29's **current** email), with every other field copied from sample case_29 (`requested_at 2026-08-27T12:00:00Z, reported_status NOT_STARTED, reported_at 2026-08-30T12:00:00Z, audit_at 2026-09-15T12:00:00Z`) and the same request text.
- **Expected:** the subject resolves to user_29 (`match=current`), and the output is **identical** to sample case_29's expected answer (14 steps: search_1993, analytics_5208, support_5281, data_flow_3827 findings; account_7012; audit_record_3954).
- **Why:** the answer must depend on *who* the subject is, not on which of their emails was used. Evidence in case_29 exists only under the old email, so this checks that the identifier set carries historical emails into evidence linking.
- Status: drafted (identity part verified: resolves to user_29 current); full-pipeline check in Phase 6.

### CC-07: historical email given in different letter case
- **Input:** `email=Camille.Bernard86@Outlook.com` (user_30's old email in mixed case), other fields copied from sample case_30.
- **Expected:** resolves to user_30 (`match=historical`, `audit_280`); output identical to sample case_30's expected answer.
- **Why:** emails in requests and evidence appear in arbitrary case (UPPERCASE rows exist in SQL and ledgers), so normalization must be applied consistently.
- Status: drafted (identity part verified); full-pipeline check in Phase 6.

### CC-08: identity change after audit_at (synthetic)
- **Input:** a synthetic user whose email changes on 2026-05-01. Requests use the *old* email with `audit_at` 2026-04-01 and with `audit_at` 2026-07-01.
- **Expected:** both resolve to the same user. At 2026-04-01 the match is `current` and the identifier set excludes the new email/hash/phone. At 2026-07-01 the match is `historical` and both emails are included. A request with the *new* email and `audit_at` 2026-04-01 must **not** resolve.
- **Why:** temporal correctness of identity (no identity change postdates an audit in the public data, but hidden tests may contain one).
- Status: automated as unit tests `test_change_after_as_of_is_excluded` / `test_change_before_as_of_is_included` (passing).
