# Progress log (append-only, newest at bottom)

## 2026-09-30: F1 scaffold
- Built taxonomy: 44 groups, 455 subcategories → config/categories.json
- Ingested input/exhibitors_raw.txt: 2031 rows → 1811 unique companies → 182 WPs (10 each) in work/queue
- tests/selftest.py: ALL CHECKS PASSED (ingest dedupe, claim/deadline, domain dedupe, list union,
  rejection of invalid categories, exports, timeout reaping + requeue)
