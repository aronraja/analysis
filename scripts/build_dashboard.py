"""Build db/dashboard.html: a self-contained dashboard over db/companies.json (data embedded).
Runs automatically after every merge (via export.py); also writes db/dashboard-data.json for live mode.
Serve live: python3 -m http.server 8765 --directory db  -> http://localhost:8765/dashboard.html
Usage: build_dashboard.py"""
import json
from pathlib import Path
from lib import load_config, now_utc, iso

ROOT = Path(__file__).resolve().parent.parent
FIELDS = ["name", "website", "linkedin_url", "hq_city", "hq_country", "hq_region", "employee_range",
          "ownership_type", "parent_company", "stock_ticker", "primary_category_group",
          "primary_category_group_name", "primary_subcategory", "primary_subcategory_name",
          "value_chain_role", "description", "status", "confidence", "events_flat", "founded_year"]


def total_exhibitors():
    """Companies in the original workpackages (retries -R/-F excluded, so nobody is counted twice)."""
    n = 0
    for d in ("queue", "in_progress", "done", "failed"):
        for f in (ROOT / "work" / d).glob("WP-*.json"):
            if "-" in f.stem[3:]:
                continue
            n += len(json.loads(f.read_text(encoding="utf-8"))["companies"])
    return n


def main(quiet=False):
    rows = json.loads((ROOT / "db" / "companies.json").read_text(encoding="utf-8"))
    slim = [{k: r.get(k) for k in FIELDS} for r in rows]
    cats = json.loads((ROOT / "config" / "categories.json").read_text(encoding="utf-8"))
    payload = {
        "generated_utc": iso(now_utc()),
        "total_exhibitors": total_exhibitors(),
        "max_agents": load_config()["max_concurrent_agents"],
        "groups": {g["code"]: g["name"] for g in cats["groups"]},
        "companies": slim,
    }
    tpl = (ROOT / "dashboard" / "template.html").read_text(encoding="utf-8")
    data = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
    out = ROOT / "db" / "dashboard.html"
    out.write_text(tpl.replace("/*__DATA__*/null", data), encoding="utf-8")
    (ROOT / "db" / "dashboard-data.json").write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    if not quiet:
        print(f"dashboard: {len(slim)} companies -> {out}")


if __name__ == "__main__":
    main()
