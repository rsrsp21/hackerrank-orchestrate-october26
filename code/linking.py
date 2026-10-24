"""Subject → resources linking (sample_walkthrough §2).

L1/L2  usable observations carrying one of the subject's exact identifiers (records, free text, log lookup keys)
L3     resources referenced by those observations (e.g. a search document's source_resource_id → account)
L4     data-catalog links whose email or user_id belongs to the subject
L5/L6  workflow timing and the naming fallback live in workflow.py (task 4.6)
`horizon` bounds which evidence may establish *membership* (default: evidence usable at audit_at; None = any
participant evidence). State and citations are decided separately and always respect the two clocks.
Names and unknown user ids never link.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Link:
    resource_id: str
    kind: str          # "L1" identifier, "L3" reference, "L4" catalog, "L5" workflow, "L6" fallback
    evidence_id: str   # the observation / activity that grounds the link
    detail: str = ""


def identifier_links(subject, index, horizon):
    """resource_id → Link for L1–L4. The first (earliest) grounding observation is kept as the reason."""
    keys = subject.link_keys()
    links = {}
    direct = index.matching(keys, horizon)
    for o in direct:
        matched = sorted(f"{k}={v}" for k, v in o.link_keys & keys)
        links.setdefault(o.resource_id, Link(o.resource_id, "L1", o.evidence_id, ",".join(matched)))
    for o in direct:
        for ref in sorted(o.refs):
            links.setdefault(ref, Link(ref, "L3", o.evidence_id, f"referenced by {o.resource_id}"))
    for c in index.links:
        if (horizon is None or c.event_time <= horizon) and (c.user_id == subject.user_id or c.email in subject.emails):
            links.setdefault(c.resource_id, Link(c.resource_id, "L4", c.activity_id, f"catalog {c.label}"))
    return links
