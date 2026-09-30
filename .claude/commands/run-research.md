---
description: Orchestrate parallel company research in waves (max 20 concurrent sub-agents) until the queue is empty or the run budget is spent.
---
You are the ORCHESTRATOR. You never research companies yourself and never edit db/ by hand.

1. Run `./init.sh`. If it fails, stop and report.
2. Note the run start time (`date -u`). The run ends at start + `limits.run_budget_hours`
   (config/harness.json) or when the queue is empty, whichever comes first.
3. Loop in waves:
   a. `python3 scripts/reap_expired.py` then `python3 scripts/merge_results.py`.
   b. `python3 scripts/status.py`. Let free = max_concurrent_agents - running.
   c. Claim up to `free` WPs: call `python3 scripts/claim_wp.py` repeatedly. Each call prints
      one path, and exit code 1 means the queue is empty or the cap has been reached.
   d. In ONE message, launch one `company-researcher` Task per claimed path, all in parallel.
      Prompt: "Workpackage: <path>. Follow your instructions exactly."
   e. When the wave returns, go back to (a). Stop if the run budget is exceeded.
4. Final pass: `reap_expired.py`, `merge_results.py`, `status.py`.
5. Append a dated entry to progress.md with the counts from status.py, and update
   session-handoff.md with the next action. Never mark a feature done without that evidence.

Note: Claude Code may run fewer Tasks at once than you launch. That is fine, because the
cap of 20 is an upper bound. For a hard wall-clock kill per agent, use `scripts/run_parallel.sh`.
