<!-- prompt_version: intent_fallback/v1 — used by intent.classify_with_fallback for texts the rules mark UNSURE. -->
You classify one customer message sent to an online shop's privacy team. Decide whether the customer **authorizes deletion** of their account or personal data.

- DELETION: the customer asks to delete, erase, or remove their account or personal data (in any language), including asking to finish or verify such a deletion.
- NOT_APPLICABLE: anything else — access or a copy of data, export, correction or update, marketing opt-out or unsubscribe only, login help, invoices, questions, complaints, restoring an account, or an explicit statement that they do **not** want deletion.

Return only JSON: {"label": "DELETION" | "NOT_APPLICABLE", "reason": "<one short sentence>"}

Message:
"""
{text}
"""
