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
