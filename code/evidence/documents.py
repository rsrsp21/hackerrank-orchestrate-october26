"""PDF evidence → Observations.

Text is extracted with pdfplumber. A document observes every resource it names (resource-id pattern) and
every resource whose external reference it carries according to a data-catalog link (e.g. statement
NST-2026-0718-1842 ↔ export_1842). The record is PRESENT; its identifiers are the document's identifiers.
Documents that name no resource (e.g. the legal retention register, which lists only order references)
produce no observation.
"""

import re

import pdfplumber

from evidence.common import files_under
from evidence.model import RESOURCE_RE, Category, Observation, State, link_keys_from, resource_prefix, system_for

CATEGORY_BY_PREFIX = {
    "account": Category.USER_PROFILE,
    "search": Category.SEARCH_INDEX_ENTRY,
    "export": Category.USER_EXPORT,
    "audit_record": Category.SECURITY_AUDIT_LOG,
    "legal_hold": Category.LEGAL_HOLD_RECORD,
    "analytics": Category.ANALYTICS_PROFILE,
    "marketing": Category.MARKETING_PROFILE,
}


def pdf_text(path):
    with pdfplumber.open(path) as pdf:
        return "\n".join(page.extract_text() or "" for page in pdf.pages)


def _category(prefix, text):
    if prefix == "support":
        return Category.SUPPORT_ATTACHMENT if re.search(r"attachment", text, re.I) else Category.SUPPORT_MESSAGE
    return CATEGORY_BY_PREFIX.get(prefix)


def load(manifest, links=()):
    observations = []
    for ef in files_under(manifest, "documents", {".pdf"}):
        text = pdf_text(ef.path)
        named = set(RESOURCE_RE.findall(text))
        named |= {link.resource_id for link in links if link.label != link.resource_id and link.label and link.label in text}
        keys = link_keys_from(text)
        for rid in sorted(named):
            category = _category(resource_prefix(rid), text)
            if category is None:
                continue
            state = State.IDENTIFIABLE if category in (Category.ANALYTICS_PROFILE, Category.SUPPORT_MESSAGE) else State.PRESENT
            observations.append(Observation(ef.file_id, ef.captured_at, ef.captured_at, system_for(rid), rid,
                                            category, state, keys, frozenset(named - {rid}),
                                            source=f"{ef.path.name}:pdf"))
    return observations
