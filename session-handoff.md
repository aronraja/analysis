# Session handoff
Last updated: 2026-09-30

State: F3 research run paused by user after a 20-agent test wave. 185/250 WPs done, 65 queued, 0 running. DB 1109 companies.
Next action: resume `/run-research` on the local machine via `scripts/run_parallel.sh`
(per-process search budgets, company sites reachable). Do NOT run it from a cloud session: its
proxy blocks company websites and the whole session shares a 200-WebSearch cap.
Then requeue the false not_found companies listed in progress.md (2026-09-30 F3 entry),
e.g. with `scripts/requeue_unresearched.py` / `reset_attempts.py`.
Open questions: none blocking. Quality of cloud-run records (WP-0044-R2 onward) is low; consider a
later enrichment pass for partial records missing website/LinkedIn.
