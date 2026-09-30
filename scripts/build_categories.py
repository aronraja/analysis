"""Parse the SEMI taxonomy text (config/semi_categories_source.txt) into config/categories.json.
Group lines look like '207 Process Equipment'; every following line is a subcategory -> id '207.05'."""
import json
import re
import sys
from lib import CONFIG

def main():
    src = CONFIG / "semi_categories_source.txt"
    groups, cur = [], None
    for raw in src.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line:
            continue
        m = re.match(r"^(\d{3})\s+(.+)$", line)
        if m:
            cur = {"code": m.group(1), "name": m.group(2).strip(), "subcategories": []}
            groups.append(cur)
            continue
        if cur is None:
            sys.exit(f"subcategory before any group: {line}")
        idx = len(cur["subcategories"]) + 1
        cur["subcategories"].append({"id": f"{cur['code']}.{idx:02d}", "name": line})
    out = {"source": "SEMI exhibitor product categories", "groups": groups}
    (CONFIG / "categories.json").write_text(json.dumps(out, indent=2, ensure_ascii=False))
    n = sum(len(g["subcategories"]) for g in groups)
    print(f"categories.json: {len(groups)} groups, {n} subcategories")

if __name__ == "__main__":
    main()
