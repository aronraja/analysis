"""One-screen status: queue/running/done counts, running WPs vs cap and time left, DB completeness."""
import json
import sqlite3
from lib import QUEUE, IN_PROGRESS, DONE, FAILED, RAW, REJECTED, DB_PATH, load_config, parse_iso, now_utc


def main():
    cfg = load_config()
    def n(d): return len(list(d.glob("WP-*.json")))
    print(f"workpackages  queued={n(QUEUE)}  running={n(IN_PROGRESS)}/{cfg['max_concurrent_agents']}"
          f"  done={n(DONE)}  failed={n(FAILED)}  awaiting_merge={len(list(RAW.glob('WP-*.done')))}"
          f"  rejected_files={len(list(REJECTED.glob('*.json')))}")
    for wp in sorted(IN_PROGRESS.glob("WP-*.json")):
        d = json.loads(wp.read_text())
        left = (parse_iso(d["deadline_utc"]) - now_utc()).total_seconds() / 60 if d.get("deadline_utc") else None
        lines = RAW / f"{d['wp_id']}.jsonl"
        got = len(lines.read_text(encoding="utf-8", errors="replace").splitlines()) if lines.exists() else 0
        print(f"  {d['wp_id']}: {got}/{len(d['companies'])} companies, "
              f"{'no deadline' if left is None else f'{left:.0f} min left'}")
    if DB_PATH.exists():
        con = sqlite3.connect(DB_PATH)
        total = con.execute("SELECT count(*) FROM companies").fetchone()[0]
        by = dict(con.execute("SELECT status, count(*) FROM companies GROUP BY status").fetchall())
        fill = {c: con.execute(f"SELECT count(*) FROM companies WHERE {c} IS NOT NULL AND {c} != ''").fetchone()[0]
                for c in ("website", "linkedin_url", "hq_country", "primary_category_group", "employee_range")}
        con.close()
        print(f"database      companies={total}  by_status={by}")
        print("  field fill:  " + "  ".join(f"{k}={v}/{total}" for k, v in fill.items()))
    else:
        print("database      (not created yet)")


if __name__ == "__main__":
    main()
