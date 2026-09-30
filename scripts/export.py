"""Export the DB to flat files a dashboard can load directly: db/companies.csv and db/companies.json."""
import csv
import json
from lib import DB_DIR
from db import connect

LIST_COLS = {"aliases_norm", "name_variants", "other_offices", "product_keywords", "end_markets",
             "sources", "wp_ids"}


def main(quiet=False):
    con = connect()
    cur = con.execute("SELECT * FROM v_company_flat ORDER BY name COLLATE NOCASE")
    cols = [d[0] for d in cur.description]
    rows = [dict(zip(cols, r)) for r in cur]
    cats = {}
    for cid, sid, prim in con.execute("SELECT company_id, subcategory_id, is_primary FROM company_categories"):
        cats.setdefault(cid, []).append(sid)
    con.close()
    out_json = []
    for r in rows:
        j = {k: (json.loads(v) if k in LIST_COLS and v else v) for k, v in r.items()}
        j["subcategories"] = cats.get(r["company_id"], [])
        out_json.append(j)
    (DB_DIR / "companies.json").write_text(json.dumps(out_json, indent=1, ensure_ascii=False), encoding="utf-8")
    with (DB_DIR / "companies.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols + ["subcategories"])
        w.writeheader()
        for r in rows:
            w.writerow({**r, "subcategories": ";".join(cats.get(r["company_id"], []))})
    if not quiet:
        print(f"exported {len(rows)} companies -> db/companies.csv, db/companies.json")
    try:  # keep the dashboard in step with every export; never let it break a merge
        import build_dashboard
        build_dashboard.main(quiet=True)
    except Exception as e:
        print(f"dashboard build skipped: {e}")


if __name__ == "__main__":
    main()
