# Progress log (append-only, newest at bottom)

## 2026-09-30: F1 scaffold
- Built taxonomy: 44 groups, 455 subcategories → config/categories.json
- Ingested input/exhibitors_raw.txt: 2031 rows → 1811 unique companies → 182 WPs (10 each) in work/queue
- tests/selftest.py: ALL CHECKS PASSED (ingest dedupe, claim/deadline, domain dedupe, list union,
  rejection of invalid categories, exports, timeout reaping + requeue)

## 2026-09-30: F3 research run (cloud session), stopped early
- Resumed after the container restarted; 20 claims were orphaned (agents dead after spending limit).
  Force-reaped with `reap_expired.py --all`, merged partials, requeued the rest.
- Fixed dedupe: semi.org directory / LinkedIn URLs used as `website` had become dedupe domains and folded
  SEMI, Banner Industries, Bay Seal and Besi into one row. `lib.NON_COMPANY_DOMAINS` is now never a
  domain; upsert moves such URLs to `sources`. `merge_results.py --repair-domains` dropped the 2 bad rows
  and replayed WP-0043 and WP-0063-R2 (Besi rejoined d:besi.com).
- Rejected records: all 3 were `bad founded_year` for genuinely old firms (Merck 1668, Okaya 1669,
  Kurtz Ersa 1779). Floor lowered 1800 -> 1600; `--retry-rejected` merged all 3. rejected_files=0.
- Stopped: session WebSearch cap (200) hit during the WP-0074..0097 wave, and the egress proxy blocks
  company sites (EGRESS_BLOCKED), so records are search-snippet only, mostly partial, no LinkedIn.
- status.py:
  workpackages  queued=85  running=0/20  done=165  failed=0  awaiting_merge=0  rejected_files=0
  database      companies=928  by_status={'complete': 455, 'not_found': 77, 'partial': 396}
  field fill:  website=565/928  linkedin_url=269/928  hq_country=852/928  primary_category_group=851/928  employee_range=928/928
- init.sh: ALL CHECKS PASSED
- False not_found / unresearched after the search cap (need requeue): WP-0083-R2 (Gilbert Industries,
  Global Advanced Packaging, Global Thermoforming, Glory Energy), WP-0084-R2 (Gore & Associates,
  Greater Sacramento Economic Council, Green Circuits, Green Optics), WP-0080-R2 (Fraunhofer IZM ASSID,
  FRD, Fresno County EDC, Forbo), WP-0076-R2 (EMI, ENGRICH).
