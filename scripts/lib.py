"""Shared helpers. Stdlib only. HARNESS_ROOT env var overrides the project root (used by tests)."""
import json
import os
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(os.environ.get("HARNESS_ROOT", Path(__file__).resolve().parent.parent))
CONFIG = ROOT / "config"
WORK = ROOT / "work"
QUEUE, IN_PROGRESS, DONE, FAILED = (WORK / d for d in ("queue", "in_progress", "done", "failed"))
RAW = ROOT / "results" / "raw"
REJECTED = ROOT / "results" / "rejected"
DB_DIR = ROOT / "db"
DB_PATH = DB_DIR / "companies.sqlite"

LEGAL_SUFFIXES = {
    "inc", "incorporated", "corp", "corporation", "co", "company", "ltd", "limited", "llc", "llp",
    "plc", "gmbh", "ag", "kg", "se", "sa", "sas", "sarl", "srl", "spa", "bv", "nv", "ab", "as", "oy",
    "oyj", "kk", "pte", "pty", "bhd", "sdn", "group", "holding", "holdings", "the",
}
SECOND_LEVEL = {
    "co.uk", "org.uk", "ac.uk", "com.tw", "org.tw", "co.jp", "or.jp", "ne.jp", "com.cn", "net.cn",
    "co.kr", "or.kr", "com.sg", "com.au", "co.il", "com.my", "co.in", "com.hk", "com.br", "com.mx",
    "co.za", "co.nz", "com.tr", "com.ph", "co.th", "com.vn",
}
# Directory / social / data-vendor hosts. A URL on these is a source about a company, never the
# company's own website, so it must not become a dedupe domain (semi.org pages folded 4 firms into one).
NON_COMPANY_DOMAINS = {
    "semi.org", "linkedin.com", "facebook.com", "twitter.com", "x.com", "youtube.com", "instagram.com",
    "wikipedia.org", "crunchbase.com", "pitchbook.com", "zoominfo.com", "dnb.com", "bloomberg.com",
    "sec.gov", "google.com", "mapyourshow.com", "a2zinc.net", "semicon.org", "semiconwest.org",
    "semiconeuropa.org", "globalspec.com", "thomasnet.com", "kompass.com", "opencorporates.com",
    "craft.co", "rocketreach.co", "cbinsights.com", "tracxn.com", "owler.com", "glassdoor.com",
    "indeed.com", "yelp.com", "bizapedia.com", "manta.com", "kiwix.lema.org", "lema.org",
}
STATUSES = {"complete", "partial", "not_found"}
OWNERSHIP = {"public", "private", "subsidiary", "government", "academic", "nonprofit", "unknown"}
EMPLOYEE_RANGES = {"1-10", "11-50", "51-200", "201-500", "501-1000", "1001-5000",
                   "5001-10000", "10001+", "unknown"}


def now_utc():
    return datetime.now(timezone.utc)


def iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_iso(s):
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def load_config():
    return json.loads((CONFIG / "harness.json").read_text())


def load_categories():
    return json.loads((CONFIG / "categories.json").read_text())


def category_ids():
    cats = load_categories()
    groups = {g["code"] for g in cats["groups"]}
    subs = {s["id"] for g in cats["groups"] for s in g["subcategories"]}
    return groups, subs


def normalize_name(name):
    if not name:
        return ""
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    s = s.replace("&", " and ")
    s = re.sub(r"\(.*?\)", " ", s)          # drop "(Taiwan)" style qualifiers
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    tokens = [t for t in s.split() if t not in LEGAL_SUFFIXES]
    return " ".join(tokens)


def domain_of(url):
    if not url:
        return None
    u = url.strip()
    if "://" not in u:
        u = "http://" + u
    host = (urlparse(u).hostname or "").lower().strip(".")
    if not host or "." not in host:
        return None
    if host.startswith("www."):
        host = host[4:]
    parts = host.split(".")
    n = 3 if ".".join(parts[-2:]) in SECOND_LEVEL and len(parts) >= 3 else 2
    dom = ".".join(parts[-n:])
    return None if dom in NON_COMPANY_DOMAINS else dom


def is_non_company_url(url):
    """True for a URL whose host is a directory/social/data site (see NON_COMPANY_DOMAINS)."""
    return bool(url) and domain_of(url) is None and domain_of_raw(url) in NON_COMPANY_DOMAINS


def domain_of_raw(url):
    u = url.strip() if "://" in url else "http://" + url.strip()
    host = (urlparse(u).hostname or "").lower().strip(".")
    parts = host.removeprefix("www.").split(".")
    n = 3 if ".".join(parts[-2:]) in SECOND_LEVEL and len(parts) >= 3 else 2
    return ".".join(parts[-n:])


def linkedin_slug(url):
    if not url:
        return None
    m = re.search(r"linkedin\.com/(?:company|school|showcase)/([^/?#]+)", url, re.I)
    return m.group(1).lower() if m else None


def validate_record(rec, groups, subs):
    """Return list of error strings; empty list = valid."""
    errs = []
    for f in ("name", "status", "wp_id", "researched_utc"):
        if not rec.get(f):
            errs.append(f"missing {f}")
    if rec.get("status") and rec["status"] not in STATUSES:
        errs.append(f"bad status {rec['status']}")
    # Agents mark a record partial precisely when website/category could not be verified,
    # so only complete records must carry them.
    if rec.get("status") == "complete":
        if not rec.get("website"):
            errs.append("complete record needs website")
        if not rec.get("primary_category_group"):
            errs.append("complete record needs primary_category_group")
    if rec.get("website") and not domain_of(rec["website"]) and not is_non_company_url(rec["website"]):
        errs.append("unparseable website")
    if rec.get("linkedin_url") and not linkedin_slug(rec["linkedin_url"]):
        errs.append("linkedin_url is not a linkedin company page")
    g = rec.get("primary_category_group")
    if g and g not in groups:
        errs.append(f"unknown category group {g}")
    for field in ("primary_subcategory",):
        if rec.get(field) and rec[field] not in subs:
            errs.append(f"unknown {field} {rec[field]}")
    for sid in rec.get("secondary_subcategories") or []:
        if sid not in subs:
            errs.append(f"unknown secondary subcategory {sid}")
    if rec.get("ownership_type") and rec["ownership_type"] not in OWNERSHIP:
        errs.append("bad ownership_type")
    if rec.get("employee_range") and rec["employee_range"] not in EMPLOYEE_RANGES:
        errs.append("bad employee_range")
    c = rec.get("confidence")
    if c is not None and not (isinstance(c, (int, float)) and 0 <= c <= 1):
        errs.append("confidence must be 0..1")
    fy = rec.get("founded_year")
    if fy is not None and not (isinstance(fy, int) and 1800 <= fy <= now_utc().year):
        errs.append("bad founded_year")
    for lf in ("other_offices", "secondary_subcategories", "events", "sources", "product_keywords",
               "end_markets"):
        if rec.get(lf) is not None and not isinstance(rec[lf], list):
            errs.append(f"{lf} must be a list")
    return errs
