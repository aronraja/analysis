"""SQLite schema for the central database. Single writer: only merge_results.py writes here."""
import sqlite3
from lib import DB_DIR, DB_PATH, load_categories

SCHEMA = """
CREATE TABLE IF NOT EXISTS companies (
  company_id            TEXT PRIMARY KEY,          -- stable id, e.g. 'd:applied-materials.com' or 'n:acme'
  name                  TEXT NOT NULL,
  name_norm             TEXT NOT NULL,
  aliases_norm          TEXT NOT NULL DEFAULT '[]',-- JSON list of normalized name variants (dedupe)
  name_variants         TEXT NOT NULL DEFAULT '[]',-- JSON list, as printed in exhibitor lists
  legal_name            TEXT,
  website               TEXT,
  domain                TEXT UNIQUE,               -- registrable domain = primary dedupe key
  linkedin_url          TEXT,
  linkedin_slug         TEXT UNIQUE,               -- secondary dedupe key
  hq_city               TEXT,
  hq_country            TEXT,                      -- ISO 3166-1 alpha-2
  hq_region             TEXT,                      -- Americas / EMEA / APAC
  other_offices         TEXT NOT NULL DEFAULT '[]',-- JSON list of {city,country,type}
  founded_year          INTEGER,
  employee_range        TEXT,
  ownership_type        TEXT,
  parent_company        TEXT,
  stock_ticker          TEXT,
  primary_category_group TEXT,
  primary_subcategory   TEXT,
  value_chain_role      TEXT,                      -- oem / component_supplier / materials / service / distributor / software / fab_idm / research / association / other
  product_keywords      TEXT NOT NULL DEFAULT '[]',
  end_markets           TEXT NOT NULL DEFAULT '[]',
  description           TEXT,
  status                TEXT NOT NULL,             -- complete / partial / not_found
  confidence            REAL,
  sources               TEXT NOT NULL DEFAULT '[]',
  notes                 TEXT,
  first_researched_utc  TEXT,
  last_researched_utc   TEXT,
  wp_ids                TEXT NOT NULL DEFAULT '[]'
);
CREATE INDEX IF NOT EXISTS ix_companies_name_norm ON companies(name_norm);
CREATE INDEX IF NOT EXISTS ix_companies_country ON companies(hq_country);
CREATE INDEX IF NOT EXISTS ix_companies_group ON companies(primary_category_group);

CREATE TABLE IF NOT EXISTS company_categories (
  company_id  TEXT NOT NULL REFERENCES companies(company_id) ON DELETE CASCADE,
  subcategory_id TEXT NOT NULL,
  is_primary  INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (company_id, subcategory_id)
);
CREATE TABLE IF NOT EXISTS company_events (
  company_id TEXT NOT NULL REFERENCES companies(company_id) ON DELETE CASCADE,
  event      TEXT NOT NULL,
  booth      TEXT NOT NULL DEFAULT '',
  PRIMARY KEY (company_id, event, booth)
);
CREATE TABLE IF NOT EXISTS category_groups (code TEXT PRIMARY KEY, name TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS subcategories (
  id TEXT PRIMARY KEY, group_code TEXT NOT NULL REFERENCES category_groups(code), name TEXT NOT NULL);

CREATE VIEW IF NOT EXISTS v_company_flat AS
SELECT c.*, g.name AS primary_category_group_name, s.name AS primary_subcategory_name,
       (SELECT group_concat(e.event, ' | ') FROM company_events e WHERE e.company_id = c.company_id) AS events_flat
FROM companies c
LEFT JOIN category_groups g ON g.code = c.primary_category_group
LEFT JOIN subcategories s ON s.id = c.primary_subcategory;
"""


def connect():
    DB_DIR.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.execute("PRAGMA foreign_keys = ON")
    con.executescript(SCHEMA)
    cats = load_categories()
    con.executemany("INSERT OR REPLACE INTO category_groups VALUES (?,?)",
                    [(g["code"], g["name"]) for g in cats["groups"]])
    con.executemany("INSERT OR REPLACE INTO subcategories VALUES (?,?,?)",
                    [(s["id"], g["code"], s["name"]) for g in cats["groups"] for s in g["subcategories"]])
    con.commit()
    return con
