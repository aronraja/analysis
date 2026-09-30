# Quick start
1. Open this folder in Claude Code (`claude`). CLAUDE.md is loaded automatically.
2. `./init.sh`
3. Check `config/sources.json` (event labels per line range of input/exhibitors_raw.txt).
4. Run `/run-research` inside Claude Code, or `scripts/run_parallel.sh 20` for headless runs with hard kills.
5. Watch progress with `python3 scripts/status.py`. Results are in `db/companies.sqlite` / `.csv` / `.json`.

To add more exhibitors, append them to `input/exhibitors_extra.csv` (name,event,booth,website_hint), or add
a segment to config/sources.json. Then run `python3 scripts/make_workpackages.py`, which only queues companies it has not seen yet.

Useful dashboard queries (sqlite3 db/companies.sqlite):
  SELECT primary_category_group_name, count(*) FROM v_company_flat GROUP BY 1 ORDER BY 2 DESC;
  SELECT hq_country, count(*) FROM companies GROUP BY 1 ORDER BY 2 DESC;
  SELECT s.name, count(*) FROM company_categories cc JOIN subcategories s ON s.id=cc.subcategory_id GROUP BY 1 ORDER BY 2 DESC;
  SELECT event, count(*) FROM company_events GROUP BY 1;
