"""End-to-end check of the pipeline in a throwaway copy (never touches the real work/ or db/)."""
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

REAL = Path(__file__).resolve().parent.parent
tmp = Path(tempfile.mkdtemp(prefix="semi-harness-test-"))
for d in ("config", "scripts"):
    shutil.copytree(REAL / d, tmp / d)
for d in ("input", "work/queue", "work/in_progress", "work/done", "work/failed",
          "results/raw", "results/rejected", "db"):
    (tmp / d).mkdir(parents=True, exist_ok=True)
(tmp / "input/exhibitors_raw.txt").write_text(
    "\tEntegris GmbH\tBooth #B1221\t\t\nAcme Photonics B.V.\tH1\nEntegris, Inc.\t5500\t\nOrphan Co\t7\n")
src = json.loads((tmp / "config/sources.json").read_text())
src["segments"] = [{"first_line": 1, "last_line": 2, "event": "EV-A"},
                   {"first_line": 3, "last_line": 4, "event": "EV-B"}]
(tmp / "config/sources.json").write_text(json.dumps(src))
cfg = json.loads((tmp / "config/harness.json").read_text())
cfg["companies_per_workpackage"] = 2
(tmp / "config/harness.json").write_text(json.dumps(cfg))
env = dict(os.environ, HARNESS_ROOT=str(tmp))


def run(script, *args):
    r = subprocess.run([sys.executable, str(tmp / "scripts" / script), *args], env=env,
                       capture_output=True, text=True, cwd=tmp / "scripts")
    assert r.returncode in (0, 1), f"{script} failed:\n{r.stdout}\n{r.stderr}"
    return r


fails = []
def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond:
        fails.append(msg)


out = run("make_workpackages.py").stdout
check("unique companies: 3" in out, f"input dedupe (Entegris GmbH + Entegris, Inc. -> 1): {out.strip()}")
wp1 = Path(run("claim_wp.py").stdout.strip())
wp2 = Path(run("claim_wp.py").stdout.strip())
check(wp1.exists() and wp2.exists() and "deadline_utc" in json.loads(wp1.read_text()), "claim + deadline stamp")
out = run("make_workpackages.py").stdout
check("new: 0" in out, "re-running ingest creates no duplicate WPs")

d1 = json.loads(wp1.read_text())
now = "2026-09-30T12:00:00Z"
recs = []
for c in d1["companies"]:
    if c["name_norm"] == "entegris":
        recs.append({"wp_id": d1["wp_id"], "input_name": c["name"], "name": "Entegris",
                     "name_variants": c["name_variants"], "website": "https://www.entegris.com/de",
                     "linkedin_url": "https://www.linkedin.com/company/entegris", "hq_country": "US",
                     "primary_category_group": "307", "primary_subcategory": "307.09",
                     "secondary_subcategories": ["400.10"], "events": c["events"],
                     "status": "complete", "confidence": 0.9, "sources": ["https://www.entegris.com"],
                     "researched_utc": now})
    else:
        recs.append({"wp_id": d1["wp_id"], "input_name": c["name"], "name": c["name"],
                     "website": "https://acme-photonics.nl", "primary_category_group": "999",
                     "status": "complete", "researched_utc": now})   # invalid category -> reject
# duplicate of Entegris from "another agent", different name spelling, same domain
recs.append({"wp_id": d1["wp_id"], "input_name": "Entegris Korea", "name": "Entegris Korea Ltd",
             "website": "http://entegris.com", "primary_category_group": "307", "status": "partial",
             "confidence": 0.5, "other_offices": [{"city": "Seoul", "country": "KR", "type": "sales"}],
             "events": [{"event": "EV-C", "booth": "9"}], "researched_utc": now})
raw = tmp / "results/raw"
(raw / f"{d1['wp_id']}.jsonl").write_text("\n".join(json.dumps(r) for r in recs) + "\n")
(raw / f"{d1['wp_id']}.done").write_text("{}")
out = run("merge_results.py").stdout
con = sqlite3.connect(tmp / "db/companies.sqlite")
rows = con.execute("SELECT company_id, name, status, other_offices FROM companies").fetchall()
check(len(rows) == 1 and rows[0][0] == "d:entegris.com", f"domain dedupe -> one Entegris row: {rows}")
check(rows and rows[0][2] == "complete" and rows[0][1] == "Entegris", "higher-confidence record wins scalars")
check(rows and "Seoul" in rows[0][3], "list fields are unioned (office from duplicate kept)")
ev = con.execute("SELECT count(*) FROM company_events").fetchone()[0]
check(ev == 3, f"events unioned across shows (expect 3, got {ev})")
check((tmp / f"results/rejected/{d1['wp_id']}.json").exists(), "invalid category rejected, not merged")
check((tmp / f"work/done/{d1['wp_id']}.json").exists(), "merged WP moved to work/done")
check((tmp / "db/companies.csv").exists() and (tmp / "db/companies.json").exists(), "dashboard exports written")
con.close()

# timeout: wp2 wrote nothing and is past deadline -> requeued with attempt 2
d2 = json.loads(wp2.read_text())
d2["deadline_utc"] = "2000-01-01T00:00:00Z"
wp2.write_text(json.dumps(d2))
run("reap_expired.py")
rq = list((tmp / "work/queue").glob(f"{d2['wp_id']}-R2.json"))
check(len(rq) == 1, "expired WP reaped and remaining companies requeued")
run("merge_results.py")
check(not (tmp / f"work/in_progress/{d2['wp_id']}.json").exists(), "reaped WP cleared from in_progress")

shutil.rmtree(tmp)
print(f"\n{'ALL CHECKS PASSED' if not fails else f'{len(fails)} CHECK(S) FAILED'}")
sys.exit(1 if fails else 0)
