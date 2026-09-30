"""Requeue companies from finished (merged) WPs that were never actually researched:
  - companies with no output line at all, and
  - not_found lines whose notes say the search budget ran out / "not researched".
They go back to work/queue as <WP>-R<attempt> (same format as reap_expired.py), or to work/failed
once max_attempts_per_company is reached. A later successful record outranks the not_found one on merge.
Usage: requeue_unresearched.py [--dry-run]"""
import json
import re
import sys
from lib import QUEUE, FAILED, DONE, RAW, load_config, now_utc, iso, normalize_name

UNRESEARCHED = re.compile(r"budget|not researched|before research|retry", re.I)


def read_lines(path):
    b = path.read_bytes()
    try:
        t = b.decode("utf-8")
    except UnicodeDecodeError:
        t = b.decode("cp1252", errors="replace")
    out = []
    for ln in t.splitlines():
        try:
            out.append(json.loads(ln))
        except json.JSONDecodeError:
            pass
    return out


def main():
    dry = "--dry-run" in sys.argv
    max_att = load_config()["limits"]["max_attempts_per_company"]
    already = {p.stem for p in list(QUEUE.glob("WP-*.json")) + list(FAILED.glob("WP-*.json"))}
    requeued = failed = 0
    for wp_file in sorted(DONE.glob("WP-*.json")):
        wp = json.loads(wp_file.read_text(encoding="utf-8"))
        wp_id = wp["wp_id"]
        out = RAW / f"{wp_id}.jsonl.merged"
        if not out.exists():
            continue
        researched = set()
        for r in read_lines(out):
            key = normalize_name(r.get("input_name") or r.get("name") or "")
            if r.get("status") == "not_found" and UNRESEARCHED.search(r.get("notes") or ""):
                continue
            researched.add(key)
        remaining = [c for c in wp["companies"] if c["name_norm"] not in researched]
        if not remaining:
            continue
        nxt = dict(wp, companies=remaining, attempt=wp["attempt"] + 1, parent_wp=wp_id, created_utc=iso(now_utc()))
        nxt.pop("claimed_utc", None)
        nxt.pop("deadline_utc", None)
        to_failed = nxt["attempt"] > max_att
        nxt["wp_id"] = f"{wp_id}-F" if to_failed else f"{wp_id}-R{nxt['attempt']}"
        if nxt["wp_id"] in already:
            continue
        print(f"{wp_id}: {len(remaining)} -> {nxt['wp_id']}: " + ", ".join(c["name"][:28] for c in remaining))
        if not dry:
            (FAILED if to_failed else QUEUE).joinpath(f"{nxt['wp_id']}.json").write_text(
                json.dumps(nxt, indent=2, ensure_ascii=False), encoding="utf-8")
        failed += len(remaining) if to_failed else 0
        requeued += 0 if to_failed else len(remaining)
    print(f"{'DRY RUN ' if dry else ''}companies requeued: {requeued} | companies failed: {failed}")


if __name__ == "__main__":
    main()
