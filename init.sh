#!/usr/bin/env bash
# Session bootstrap + verification gate. Non-destructive.
set -euo pipefail
cd "$(dirname "$0")"
python3 -c 'import sys; assert sys.version_info >= (3,9), "need python>=3.9"'
mkdir -p work/queue work/in_progress work/done work/failed results/raw results/rejected db logs input
[ -f config/categories.json ] || (cd scripts && python3 build_categories.py)
python3 -c 'import json;[json.load(open(f)) for f in ("config/harness.json","config/sources.json","config/categories.json","feature_list.json")]'
python3 tests/selftest.py
python3 scripts/status.py
