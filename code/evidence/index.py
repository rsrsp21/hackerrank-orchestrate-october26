"""EvidenceIndex: every observation, coverage, catalog link, and activity, queryable per case at audit_at.

The two-clock rule lives here (Observation.usable / Coverage.usable). A case's state evidence must also be
observed at or after the request (`since=requested_at`): earlier observations describe an earlier episode
(every evidence cited in the samples lies in [requested_at, audit_at]). State at audit_at = the latest such
DIRECT observation; an OMISSION proof (coverage) is used only when no DIRECT observation exists
(sample case_21 cites evidence_92's 404, not the later empty snapshot evidence_51).
"""

from collections import defaultdict
from dataclasses import dataclass

from evidence import activity, documents, images, logs, records, sql
from evidence.common import load_manifest
from evidence.model import Directness, Observation, State, system_for


def _order(o):
    return (o.observed_at, o.file_captured_at, o.evidence_id, o.source)


@dataclass
class EvidenceIndex:
    observations: list
    coverages: list
    links: list
    activities: list
    missing_image_facts: list

    def __post_init__(self):
        self.by_rid = defaultdict(list)
        self.by_key = defaultdict(list)
        for o in self.observations:
            self.by_rid[o.resource_id].append(o)
            for k in o.link_keys:
                self.by_key[k].append(o)
        for lst in self.by_rid.values():
            lst.sort(key=_order)

    def usable(self, resource_id, audit_at, since=None):
        return [o for o in self.by_rid.get(resource_id, [])
                if o.usable(audit_at) and (since is None or o.observed_at >= since)]

    def matching(self, link_keys, audit_at=None):
        """Observations carrying any of the given identifier keys (usable at audit_at, or all if None)."""
        seen, out = set(), []
        for k in link_keys:
            for o in self.by_key.get(k, []):
                if id(o) not in seen and (audit_at is None or o.usable(audit_at)):
                    seen.add(id(o))
                    out.append(o)
        return sorted(out, key=_order)

    def omission(self, resource_id, audit_at, since=None):
        """Latest usable coverage that proves the resource absent, as an OMISSION observation."""
        covs = [c for c in self.coverages if c.usable(audit_at) and c.proves_absent(resource_id)
                and (since is None or c.observed_at >= since)]
        if not covs:
            return None
        c = max(covs, key=lambda c: (c.observed_at, c.file_captured_at, c.evidence_id))
        return Observation(c.evidence_id, c.file_captured_at, c.observed_at, system_for(resource_id), resource_id,
                           None, State.ABSENT, directness=Directness.OMISSION, source=c.source)

    def state_at(self, resource_id, audit_at, since=None):
        """The observation that determines the resource's state at audit_at (None if nothing usable)."""
        direct = self.usable(resource_id, audit_at, since)
        if direct:
            return direct[-1]
        return self.omission(resource_id, audit_at, since)


def build(data_dir, facts_dir=images.FACTS_DIR):
    manifest = load_manifest(data_dir)
    acts = activity.load_activities(data_dir)
    links = activity.catalog_links(acts)
    so, sc = sql.load(manifest)
    ro, rc = records.load(manifest)
    io, missing = images.load(manifest, facts_dir, links)
    observations = so + ro + logs.load(manifest) + activity.observations(acts) + documents.load(manifest, links) + io
    return EvidenceIndex(observations, sc + rc, links, acts, missing)
