# SEMI Exhibitor Market-Analysis Harness

Goal: enrich every exhibitor from SEMI shows (input/exhibitors_raw.txt, about 1,800 unique
companies) into ONE deduplicated database, `db/companies.sqlite`, exported as `db/companies.csv`
and `db/companies.json` for dashboards.

## Startup (every session)
1. `./init.sh`: it must print ALL CHECKS PASSED. If it does not, fix that first.
2. Read `session-handoff.md`, then `feature_list.json` (the one active feature), then the tail of `progress.md`.
3. `python3 scripts/status.py`

## Roles
- Orchestrator (main session): runs `/run-research`, or `scripts/run_parallel.sh` for hard timeouts.
  It claims WPs, launches sub-agents, reaps, merges, and records progress. It never researches companies itself.
- `company-researcher` sub-agent (`.claude/agents/`): handles one WP and writes only `results/raw/<WP>.jsonl` + `.done`.
- `scripts/merge_results.py` is the ONLY writer to `db/`. Never edit the DB or `work/` by hand.

## Invariants
- At most 20 concurrent agents (`config/harness.json` → `max_concurrent_agents`; `claim_wp.py` enforces it).
- Time limits come from `config/harness.json`: per company, per WP (deadline stamped at claim), and per run.
  Expired WPs are reaped. Partial output is kept, and the rest is retried once and then goes to `work/failed/`.
- Dedupe key order: website registrable domain → LinkedIn slug → normalized name/aliases.
  Regional subsidiaries fold into the group record.
- Categories are the SEMI taxonomy in `config/categories.json` (group "207", subcategory "207.06"). No other ids.
- Changing the category source means re-running `scripts/build_categories.py`. Ids are positional, so
  never reorder the source after data exists.

## Definition of done (per feature)
Evidence in progress.md: status.py output, and init.sh passing. Rejected records in `results/rejected/`
are either fixed or explained.

## Pipeline
make_workpackages.py → claim_wp.py → sub-agent → reap_expired.py → merge_results.py → export.py (auto)
