"""Enforce the time limit. For every in_progress WP past deadline + grace that has no .done marker:
  - whatever the agent already wrote (partial jsonl) is kept and marked done so it gets merged;
  - companies with no output line are re-queued as a new WP (attempt+1), or sent to work/failed
    once max_attempts_per_company is reached.
Run it between waves and at the end of a run. Also usable with --all to reap everything (after a crash), or with WP ids to force-reap only those."""
import json
import sys
from datetime import timedelta
from lib import IN_PROGRESS, QUEUE, FAILED, RAW, load_config, parse_iso, now_utc, iso, normalize_name


def main():
    cfg = load_config()
    grace = timedelta(minutes=cfg["limits"]["grace_minutes_before_reap"])
    max_att = cfg["limits"]["max_attempts_per_company"]
    force = "--all" in sys.argv
    only = {a for a in sys.argv[1:] if a.startswith("WP-")}  # force-reap just these (e.g. dead claims)
    reaped = requeued = failed = 0
    for wp_file in sorted(IN_PROGRESS.glob("WP-*.json")):
        wp = json.loads(wp_file.read_text())
        wp_id = wp["wp_id"]
        if (RAW / f"{wp_id}.done").exists():
            continue                           # finished; merge_results will pick it up
        deadline = parse_iso(wp["deadline_utc"]) if wp.get("deadline_utc") else None
        if only and wp_id not in only:
            continue
        if not force and not only and deadline and now_utc() < deadline + grace:
            continue                           # still inside its time budget
        jsonl = RAW / f"{wp_id}.jsonl"
        seen = set()
        if jsonl.exists():
            for ln in jsonl.read_text(encoding="utf-8", errors="replace").splitlines():
                try:
                    seen.add(normalize_name(json.loads(ln).get("input_name") or json.loads(ln)["name"]))
                except Exception:
                    pass
        remaining = [c for c in wp["companies"] if c["name_norm"] not in seen]
        (RAW / f"{wp_id}.done").write_text(json.dumps({"reaped_utc": iso(now_utc()), "timed_out": True}))
        reaped += 1
        if remaining:
            nxt = dict(wp, companies=remaining, attempt=wp["attempt"] + 1, parent_wp=wp_id,
                       created_utc=iso(now_utc()))
            nxt.pop("claimed_utc", None)
            nxt.pop("deadline_utc", None)
            if nxt["attempt"] > max_att:
                nxt["wp_id"] = f"{wp_id}-F"
                (FAILED / f"{nxt['wp_id']}.json").write_text(json.dumps(nxt, indent=2, ensure_ascii=False))
                failed += len(remaining)
            else:
                nxt["wp_id"] = f"{wp_id}-R{nxt['attempt']}"
                (QUEUE / f"{nxt['wp_id']}.json").write_text(json.dumps(nxt, indent=2, ensure_ascii=False))
                requeued += len(remaining)
    print(f"reaped WPs: {reaped} | companies requeued: {requeued} | companies failed: {failed}")


if __name__ == "__main__":
    main()
