"""Phase 1 task 1.4 (logs): parse every evidence log format into uniform events and join traces.

Formats seen (see plan/data_notes.md §3.3):
  bracket   2026-..Z [DEBUG] [service] [trace] event: k="v" ...
  pipe      2026-..Z | DEBUG | service | trace | event | k="v" ...
  cloud     2026-..Z requestId=trace level=X function=service message="k=\"v\" ..."
  json      2026-..Z {"severity": ..., "service": ..., "event": ...}
  syslog    2026-..Z <15>1 node service trace - - level=X k="v" ...
  logfmt    2026-..Z level=X service=svc ... event=... k=v
Every line becomes {ts, service, trace, event, fields}. Lines sharing a trace id are merged so the
identifier on *_started lines joins the resource_id/outcome on *_completed lines.
Run: uv run python code/explore/parse_logs.py
"""

import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "dataset"

TS = r"(?P<ts>\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ)"
KV = re.compile(r'(\w+)=("(?:[^"\\]|\\.)*"|\S+)')


def kv(text):
    out = {}
    for k, v in KV.findall(text):
        if v.startswith('"'):
            v = v[1:-1].replace('\\"', '"')
        out[k] = None if v == "null" else v
    return out


def parse_line(line):
    line = line.rstrip("\n")
    m = re.match(TS + r" \[(?P<lvl>\w+)\] \[(?P<svc>[^\]]+)\] \[(?P<tr>[^\]]+)\] (?P<ev>\w+): ?(?P<rest>.*)$", line)
    if m:
        return dict(fmt="bracket", ts=m["ts"], service=m["svc"], trace=m["tr"], event=m["ev"], fields=kv(m["rest"]))
    m = re.match(TS + r" \| (?P<lvl>\w+) \| (?P<svc>[^|]+?) \| (?P<tr>[^|]+?) \| (?P<ev>[^|]+?) \| (?P<rest>.*)$", line)
    if m:
        return dict(fmt="pipe", ts=m["ts"], service=m["svc"], trace=m["tr"], event=m["ev"], fields=kv(m["rest"]))
    m = re.match(TS + r' requestId=(?P<tr>\S+) level=\w+ function=(?P<svc>\S+) message="(?P<msg>.*)"$', line)
    if m:
        f = kv(m["msg"].replace('\\"', '"'))
        return dict(fmt="cloud", ts=m["ts"], service=m["svc"], trace=m["tr"], event=f.pop("event", None), fields=f)
    m = re.match(TS + r" (?P<js>\{.*\})$", line)
    if m:
        f = json.loads(m["js"])
        return dict(fmt="json", ts=m["ts"], service=f.get("service"), trace=f.get("trace_id") or f.get("instance"),
                    event=f.get("event"), fields={k: v for k, v in f.items() if k not in ("service", "event")})
    m = re.match(TS + r" <\d+>\d+ (?P<node>\S+) (?P<svc>\S+) (?P<tr>\S+) - - (?P<rest>.*)$", line)
    if m:
        f = kv(m["rest"])
        return dict(fmt="syslog", ts=m["ts"], service=m["svc"], trace=m["tr"], event=f.pop("event", None), fields=f)
    m = re.match(TS + r" (?P<rest>.*)$", line)
    if m:
        f = kv(m["rest"])
        return dict(fmt="logfmt", ts=m["ts"], service=f.pop("service", None),
                    trace=f.get("trace_id") or f.get("seq") or f.get("instance"), event=f.pop("event", None), fields=f)
    return None


def main():
    manifest = {r["file_path"]: r for r in csv.DictReader(open(DATA / "evidence_files.csv", encoding="utf-8"))}
    all_events, unparsed = [], []
    print("=" * 80, "\nPer-file format, line-time range vs manifest captured_at\n" + "=" * 80)
    for path in sorted((DATA / "evidence" / "logs").glob("*.log")):
        rel = path.relative_to(DATA).as_posix()
        m = manifest[rel]
        events = []
        for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            e = parse_line(line)
            if e is None:
                unparsed.append((path.name, i, line[:160]))
                continue
            e.update(file_id=m["file_id"], file=path.name, line=i, captured_at=m["captured_at"])
            events.append(e)
        fmts = Counter(e["fmt"] for e in events)
        tmin, tmax = min(e["ts"] for e in events), max(e["ts"] for e in events)
        flag = "AFTER-CAPTURE" if tmax > m["captured_at"] else "ok"
        print(f"{m['file_id']} {path.name:52s} fmt={dict(fmts)} lines={tmin}..{tmax} captured={m['captured_at']} [{flag}] origin={m['origin']}")
        all_events.extend(events)
    print("unparsed lines:", len(unparsed))
    for u in unparsed[:10]:
        print("   ", u)

    print("\n" + "=" * 80, "\nServices x events\n" + "=" * 80)
    se = Counter((e["service"], e["event"]) for e in all_events)
    for (s, ev), n in sorted(se.items(), key=lambda x: (str(x[0][0]), str(x[0][1]))):
        print(f"{n:5d}  {str(s):28s} {ev}")

    print("\n" + "=" * 80, "\nField keys per (service, event) for outcome-bearing events\n" + "=" * 80)
    keys = defaultdict(Counter)
    for e in all_events:
        if e["event"] and re.search(r"completed|lookup$|read|query|result|failed|error|skipped|purge|delete|restore|sync", e["event"]):
            keys[(e["service"], e["event"])].update(e["fields"].keys())
    noise = {"instance", "pod", "region", "trace_id", "attempt", "level", "severity", "logger", "seq"}
    for k in sorted(keys, key=str):
        print(f"{str(k):70s} {sorted(set(keys[k]) - noise)}")

    print("\n" + "=" * 80, "\nTrace joins: identifier keys and outcomes\n" + "=" * 80)
    traces = defaultdict(list)
    for e in all_events:
        traces[(e["file"], e["trace"])].append(e)
    id_keys = ("lookup_key", "match_key", "subject_key", "subject_ref", "correlation_key", "subject_reference",
               "customer_email", "email", "customer_reference")
    joined, outcome_kinds = [], Counter()
    for (fname, tr), evs in traces.items():
        merged = {}
        for e in sorted(evs, key=lambda e: e["line"]):
            merged.update({k: v for k, v in e["fields"].items() if v is not None})
        rid = merged.get("resource_id")
        ident = next((merged[k] for k in id_keys if merged.get(k)), None)
        if not rid:
            continue
        outcome = {k: merged[k] for k in ("http_status", "rows", "result", "enabled", "total_hits", "restore_allowed",
                                           "record_type", "integrity_check", "status", "outcome", "state",
                                           "retention_until", "event_code", "last_delivery_status") if k in merged}
        joined.append(dict(file_id=evs[0]["file_id"], file=fname, trace=tr, service=evs[0]["service"],
                           events=[e["event"] for e in evs], ts=max(e["ts"] for e in evs), resource_id=rid,
                           identifier=ident, outcome=outcome, fields=merged))
        outcome_kinds[(evs[-1]["service"], tuple(sorted(outcome.items())) if len(outcome) <= 3 else "multi")] += 1
    print(f"traces with a resource_id: {len(joined)}; without identifier: {sum(1 for j in joined if not j['identifier'])}")
    for k, n in outcome_kinds.most_common(45):
        print(f"   {n:4d}  {k}")

    print("\n" + "=" * 80, "\nEvent sequences per trace (patterns)\n" + "=" * 80)
    seqs = Counter((j["service"], " > ".join(j["events"])) for j in joined)
    for (s, q), n in seqs.most_common(40):
        print(f"   {n:4d}  {s}: {q[:170]}")

    print("\n" + "=" * 80, "\nUnusual events (not started/completed/connection/cache/export noise)\n" + "=" * 80)
    boring = re.compile(r"_started$|_completed$|connection_acquired|cache_lookup|export_started|export_finished|cache_refresh|heartbeat|record_lookup|batch_")
    odd = Counter((e["service"], e["event"]) for e in all_events if e["event"] and not boring.search(e["event"]))
    for k, n in odd.most_common():
        ex = next(e for e in all_events if (e["service"], e["event"]) == k)
        print(f"   {n:4d}  {k}  e.g. {ex['file_id']}:{ex['line']} {json.dumps(ex['fields'], ensure_ascii=False)[:220]}")

    out = ROOT / "code" / "cache" / "extracted"
    out.mkdir(parents=True, exist_ok=True)
    with open(out / "log_events.jsonl", "w", encoding="utf-8") as f:
        for e in all_events:
            f.write(json.dumps(e, sort_keys=True, ensure_ascii=False) + "\n")
    with open(out / "log_traces.jsonl", "w", encoding="utf-8") as f:
        for j in joined:
            f.write(json.dumps(j, sort_keys=True, ensure_ascii=False) + "\n")
    print(f"\nwrote {len(all_events)} events and {len(joined)} joined traces to {out}")


if __name__ == "__main__":
    main()
