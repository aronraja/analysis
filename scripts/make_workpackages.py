"""Ingest exhibitor lists, dedupe, skip companies already in the DB or already queued, and write
workpackages (work/queue/WP-xxxx.json). Safe to re-run: it only adds companies not yet seen."""
import csv
import json
import sqlite3
from lib import (ROOT, CONFIG, QUEUE, IN_PROGRESS, DONE, FAILED, DB_PATH, load_config,
                 normalize_name, domain_of, iso, now_utc)


def read_raw(src):
    rows = []
    raw_path = ROOT / src["raw_file"]
    if not raw_path.exists():
        return rows
    lines = raw_path.read_text(encoding="utf-8", errors="replace").splitlines()
    for seg in src["segments"]:
        for ln in range(seg["first_line"], min(seg["last_line"], len(lines)) + 1):
            fields = [f.strip() for f in lines[ln - 1].replace("\r", "").split("\t") if f.strip()]
            if not fields:
                continue
            booth = fields[1].replace("Booth #", "").strip() if len(fields) > 1 else None
            rows.append({"name": fields[0], "event": seg["event"], "booth": booth,
                         "website_hint": None, "source_line": ln})
    return rows


def read_extra(src):
    p = ROOT / src.get("extra_csv", "")
    if not src.get("extra_csv") or not p.exists():
        return []
    with p.open(newline="", encoding="utf-8") as f:
        return [{"name": r["name"].strip(), "event": r.get("event") or None,
                 "booth": r.get("booth") or None, "website_hint": r.get("website_hint") or None,
                 "source_line": None} for r in csv.DictReader(f) if r.get("name", "").strip()]


def known_keys():
    """Normalized names/domains already in the DB or in any workpackage (queued/running/done/failed)."""
    names, domains = set(), set()
    if DB_PATH.exists():
        con = sqlite3.connect(DB_PATH)
        for n, d, aliases in con.execute("SELECT name_norm, domain, aliases_norm FROM companies"):
            names.add(n)
            names.update(json.loads(aliases or "[]"))
            if d:
                domains.add(d)
        con.close()
    for d in (QUEUE, IN_PROGRESS, DONE, FAILED):
        for wp in d.glob("WP-*.json"):
            for c in json.loads(wp.read_text())["companies"]:
                names.add(c["name_norm"])
    return names, domains


def next_wp_number():
    nums = [int(p.stem.split("-")[1]) for d in (QUEUE, IN_PROGRESS, DONE, FAILED)
            for p in d.glob("WP-*.json")]
    return max(nums, default=0) + 1


def main():
    cfg = load_config()
    src = json.loads((CONFIG / "sources.json").read_text())
    rows = read_raw(src) + read_extra(src)
    # 1) dedupe within the input: merge events/booths of the same company
    uniq = {}
    for r in rows:
        key = normalize_name(r["name"])
        if not key:
            continue
        c = uniq.setdefault(key, {"name": r["name"], "name_norm": key, "name_variants": [],
                                  "events": [], "website_hint": None})
        if r["name"] not in c["name_variants"]:
            c["name_variants"].append(r["name"])
        ev = {"event": r["event"], "booth": r["booth"]}
        if r["event"] and ev not in c["events"]:
            c["events"].append(ev)
        c["website_hint"] = c["website_hint"] or r["website_hint"]
    # 2) drop anything already known
    names, domains = known_keys()
    todo = [c for k, c in uniq.items()
            if k not in names and not (c["website_hint"] and domain_of(c["website_hint"]) in domains)]
    # 3) chunk into workpackages
    size, lim = cfg["companies_per_workpackage"], cfg["limits"]
    n, created = next_wp_number(), 0
    for i in range(0, len(todo), size):
        wp_id = f"WP-{n:04d}"
        wp = {"wp_id": wp_id, "created_utc": iso(now_utc()), "attempt": 1,
              "limits": {k: lim[k] for k in ("minutes_per_company", "minutes_per_workpackage",
                                              "max_web_calls_per_company")},
              "companies": todo[i:i + size]}
        (QUEUE / f"{wp_id}.json").write_text(json.dumps(wp, indent=2, ensure_ascii=False))
        n += 1
        created += 1
    print(f"input rows: {len(rows)} | unique companies: {len(uniq)} | already known: "
          f"{len(uniq) - len(todo)} | new: {len(todo)} | workpackages created: {created}")


if __name__ == "__main__":
    main()
