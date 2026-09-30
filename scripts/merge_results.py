"""Merge finished agent output (results/raw/WP-xxxx.jsonl + .done marker) into db/companies.sqlite.
Dedupe order: domain -> linkedin slug -> normalized name/alias. Invalid lines go to results/rejected/.
Then moves the WP to work/done and exports db/companies.csv + db/companies.json for dashboards."""
import json
import shutil
from lib import (RAW, REJECTED, IN_PROGRESS, DONE, QUEUE, validate_record, category_ids,
                 normalize_name, domain_of, is_non_company_url, linkedin_slug, iso, now_utc)
from db import connect
import export

SCALARS = ["legal_name", "website", "linkedin_url", "hq_city", "hq_country", "hq_region",
           "founded_year", "employee_range", "ownership_type", "parent_company", "stock_ticker",
           "primary_category_group", "primary_subcategory", "value_chain_role", "description", "notes"]
LISTS = ["other_offices", "product_keywords", "end_markets", "sources"]
STATUS_RANK = {"not_found": 0, "partial": 1, "complete": 2}


def union(a, b):
    out = list(a)
    for x in b:
        if x not in out:
            out.append(x)
    return out


def find_existing(con, dom, slug, names):
    if dom:
        r = con.execute("SELECT company_id FROM companies WHERE domain=?", (dom,)).fetchone()
        if r:
            return r[0]
    if slug:
        r = con.execute("SELECT company_id FROM companies WHERE linkedin_slug=?", (slug,)).fetchone()
        if r:
            return r[0]
    for n in names:
        # name match only when it cannot contradict a domain (avoid merging two distinct firms)
        for cid, d, aliases in con.execute(
                "SELECT company_id, domain, aliases_norm FROM companies WHERE name_norm=? OR aliases_norm LIKE ?",
                (n, f'%"{n}"%')):
            if n in json.loads(aliases) and not (dom and d and d != dom):
                return cid
    return None


def upsert(con, rec):
    if is_non_company_url(rec.get("website")):  # a directory/LinkedIn page is a source, not the website
        rec["sources"] = union(rec.get("sources") or [], [rec["website"]])
        rec["website"] = None
    dom = domain_of(rec.get("website"))
    slug = linkedin_slug(rec.get("linkedin_url"))
    variants = rec.get("name_variants") or [rec["name"]]
    names = union([normalize_name(rec["name"])], [normalize_name(v) for v in variants])
    names = [n for n in names if n]
    cid = find_existing(con, dom, slug, names)
    now = rec.get("researched_utc") or iso(now_utc())
    if cid is None:
        cid = f"d:{dom}" if dom else f"n:{names[0]}"
        con.execute("""INSERT INTO companies (company_id, name, name_norm, aliases_norm, name_variants,
                       domain, linkedin_slug, status, confidence, first_researched_utc, last_researched_utc, wp_ids)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (cid, rec["name"], names[0], json.dumps(names), json.dumps(variants), dom, slug,
                     rec["status"], rec.get("confidence"), now, now, json.dumps([rec["wp_id"]])))
        existing = None
    else:
        existing = dict(zip([d[0] for d in con.execute("SELECT * FROM companies LIMIT 0").description],
                            con.execute("SELECT * FROM companies WHERE company_id=?", (cid,)).fetchone()))
    new_better = existing is None or (
        STATUS_RANK[rec["status"]], rec.get("confidence") or 0) >= (
        STATUS_RANK[existing["status"]], existing["confidence"] or 0)
    sets = {}
    for f in SCALARS:
        v = rec.get(f)
        if v in (None, "", []):
            continue
        if existing is None or existing.get(f) in (None, "") or new_better:
            sets[f] = v
    for f in LISTS:
        old = json.loads(existing[f]) if existing else []
        sets[f] = json.dumps(union(old, rec.get(f) or []), ensure_ascii=False)
    if existing:
        sets["aliases_norm"] = json.dumps(union(json.loads(existing["aliases_norm"]), names))
        sets["name_variants"] = json.dumps(union(json.loads(existing["name_variants"]), variants), ensure_ascii=False)
        sets["wp_ids"] = json.dumps(union(json.loads(existing["wp_ids"]), [rec["wp_id"]]))
        sets["last_researched_utc"] = now
        if new_better:
            sets["status"], sets["confidence"] = rec["status"], rec.get("confidence")
        if dom and not existing["domain"]:
            sets["domain"] = dom
        if slug and not existing["linkedin_slug"]:
            sets["linkedin_slug"] = slug
    if sets:
        con.execute(f"UPDATE companies SET {', '.join(k + '=?' for k in sets)} WHERE company_id=?",
                    (*sets.values(), cid))
    subs = ([rec["primary_subcategory"]] if rec.get("primary_subcategory") else []) + \
        (rec.get("secondary_subcategories") or [])
    for i, s in enumerate(subs):
        con.execute("INSERT OR IGNORE INTO company_categories VALUES (?,?,?)", (cid, s, 0))
        if i == 0 and new_better:
            con.execute("UPDATE company_categories SET is_primary = (subcategory_id = ?) WHERE company_id=?",
                        (s, cid))
    for e in rec.get("events") or []:
        con.execute("INSERT OR IGNORE INTO company_events VALUES (?,?,?)",
                    (cid, e.get("event") or "unknown", e.get("booth") or ""))
    return cid


def main():
    groups, subs = category_ids()
    con = connect()
    merged_wps = ok = bad = 0
    for marker in sorted(RAW.glob("WP-*.done")):
        wp_id = marker.stem
        jsonl = RAW / f"{wp_id}.jsonl"
        raw = jsonl.read_bytes() if jsonl.exists() else b""
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:  # agent wrote via a Windows shell in cp1252
            text = raw.decode("cp1252", errors="replace")
        lines = text.splitlines()
        rejects = []
        with con:  # one transaction per workpackage
            for ln in lines:
                if not ln.strip():
                    continue
                try:
                    rec = json.loads(ln)
                except json.JSONDecodeError as e:
                    rejects.append({"line": ln, "errors": [f"json: {e}"]})
                    continue
                rec.setdefault("wp_id", wp_id)
                if not rec.get("name"):  # not_found lines may leave name null
                    rec["name"] = rec.get("input_name")
                errs = validate_record(rec, groups, subs)
                if errs:
                    rejects.append({"record": rec, "errors": errs})
                    continue
                upsert(con, rec)
                ok += 1
        if rejects:
            bad += len(rejects)
            (REJECTED / f"{wp_id}.json").write_text(json.dumps(rejects, indent=2, ensure_ascii=False),
                                                    encoding="utf-8")
        for p in (jsonl, marker):
            if p.exists():
                p.rename(p.with_suffix(p.suffix + ".merged"))
        wp_file = IN_PROGRESS / f"{wp_id}.json"
        if wp_file.exists():
            shutil.move(str(wp_file), DONE / wp_file.name)
        merged_wps += 1
    total = con.execute("SELECT count(*) FROM companies").fetchone()[0]
    con.close()
    export.main(quiet=True)
    print(f"merged WPs: {merged_wps} | records ok: {ok} | rejected: {bad} | companies in DB: {total}")


def retry_rejected():
    """Re-validate results/rejected/*.json (after a rule or record fix); merge what now passes,
    keep the rest in the file, delete files that become empty."""
    groups, subs = category_ids()
    con = connect()
    ok = still = 0
    for f in sorted(REJECTED.glob("WP-*.json")):
        raw = f.read_bytes()
        try:
            items = json.loads(raw.decode("utf-8"))
        except UnicodeDecodeError:
            items = json.loads(raw.decode("cp1252", errors="replace"))
        keep = []
        with con:
            for it in items:
                rec = it.get("record")
                if rec and not rec.get("name"):
                    rec["name"] = rec.get("input_name")
                errs = validate_record(rec, groups, subs) if rec else it["errors"]
                if errs:
                    keep.append({**it, "errors": errs})
                    continue
                upsert(con, rec)
                ok += 1
        still += len(keep)
        if keep:
            f.write_text(json.dumps(keep, indent=2, ensure_ascii=False), encoding="utf-8")
        else:
            f.unlink()
    total = con.execute("SELECT count(*) FROM companies").fetchone()[0]
    con.close()
    export.main(quiet=True)
    print(f"retried rejects: merged {ok} | still rejected: {still} | companies in DB: {total}")


def repair_domains():
    """Undo merges keyed on a non-company domain: drop rows whose domain/website is a directory or
    social URL, then replay every merged raw line of the WPs that touched them through the fixed upsert.
    Replaying is idempotent for the other companies in those WPs (lists union, scalars keep the best)."""
    from lib import NON_COMPANY_DOMAINS
    groups, subs = category_ids()
    con = connect()
    bad = [r for r in con.execute("SELECT company_id, domain, website, wp_ids FROM companies")
           if r[1] in NON_COMPANY_DOMAINS or is_non_company_url(r[2])]
    wps = sorted({w for r in bad for w in json.loads(r[3])})
    replay = 0
    with con:
        for cid, *_ in bad:
            for t in ("company_categories", "company_events", "companies"):
                con.execute(f"DELETE FROM {t} WHERE company_id=?", (cid,))
        for wp_id in wps:
            f = RAW / f"{wp_id}.jsonl.merged"
            if not f.exists():
                print(f"  WARNING: {f.name} missing; its companies in the dropped rows are lost")
                continue
            for ln in f.read_bytes().decode("utf-8", errors="replace").splitlines():
                try:
                    rec = json.loads(ln)
                except json.JSONDecodeError:
                    continue
                rec.setdefault("wp_id", wp_id)
                rec["name"] = rec.get("name") or rec.get("input_name")
                if not validate_record(rec, groups, subs):
                    upsert(con, rec)
                    replay += 1
    total = con.execute("SELECT count(*) FROM companies").fetchone()[0]
    con.close()
    export.main(quiet=True)
    print(f"repaired rows: {len(bad)} ({', '.join(r[0] for r in bad)}) | replayed WPs: {wps} | "
          f"records replayed: {replay} | companies in DB: {total}")


if __name__ == "__main__":
    import sys
    if "--retry-rejected" in sys.argv:
        retry_rejected()
    elif "--repair-domains" in sys.argv:
        repair_domains()
    else:
        main()
