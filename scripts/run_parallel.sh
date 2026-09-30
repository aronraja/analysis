#!/usr/bin/env bash
# Headless runner with HARD limits: at most N concurrent `claude -p` processes, each killed by
# `timeout` at the WP time budget, and the whole run stops at run_budget_hours.
# Usage: scripts/run_parallel.sh [max_concurrent]   (default from config/harness.json)
set -uo pipefail
cd "$(dirname "$0")/.."
# Drop auth/session vars inherited from a parent Claude app so headless runs use the CLI's own login.
unset $(env | grep -oE '^(CLAUDE[A-Z_]*|ANTHROPIC[A-Z_]*)') 2>/dev/null
cfg() { python3 -c "import json;c=json.load(open('config/harness.json'));print($1)"; }
MAX=${1:-$(cfg "c['max_concurrent_agents']")}
WP_MIN=$(cfg "c['limits']['minutes_per_workpackage']")
TURNS=$(cfg "c['limits']['max_turns_per_agent']")
BUDGET_H=$(cfg "c['limits']['run_budget_hours']")
CLAUDE=$(cfg "c['headless']['claude_bin']")
TOOLS=$(cfg "c['headless']['allowed_tools']")
MODEL=$(cfg "c['headless'].get('model') or ''")
END=$(( $(date +%s) + $(python3 -c "print(int($BUDGET_H*3600))") ))
mkdir -p logs

run_one() {
  local wp="$1" id; id=$(basename "$wp" .json)
  timeout --kill-after=60 "${WP_MIN}m" "$CLAUDE" -p \
    "You are the company-researcher sub-agent. Read .claude/agents/company-researcher.md and follow it exactly for workpackage: $wp" \
    --max-turns "$TURNS" --allowedTools "$TOOLS" ${MODEL:+--model "$MODEL"} > "logs/$id.log" 2>&1
  echo "$(date -u +%FT%TZ) $id exit=$?" >> logs/runner.log
}

echo "runner: model=${MODEL:-default} max=$MAX wp_timeout=${WP_MIN}m budget=${BUDGET_H}h" | tee -a logs/runner.log
while [ "$(date +%s)" -lt "$END" ]; do
  python3 scripts/reap_expired.py >/dev/null; python3 scripts/merge_results.py >/dev/null
  while [ "$(jobs -rp | wc -l)" -ge "$MAX" ]; do wait -n; done
  WP=$(python3 scripts/claim_wp.py 2>/dev/null); rc=$?
  if [ $rc -ne 0 ]; then
    running_wps=$(ls work/in_progress/WP-*.json 2>/dev/null | wc -l)
    if [ $rc -eq 1 ] && [ "$(jobs -rp | wc -l)" -eq 0 ] && [ "$running_wps" -eq 0 ]; then break; fi
    sleep 30; continue                             # cap reached or waiting for reaper/requeue
  fi
  run_one "$WP" &
  sleep 2                                          # stagger starts (rate limits)
done
wait
python3 scripts/reap_expired.py; python3 scripts/merge_results.py; python3 scripts/status.py
