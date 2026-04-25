#!/bin/bash
# Full local release smoke-check.
#
# The backend scenarios run against pytest temporary SQLite databases. Test
# orders, cash rows, plate payouts, and warehouse rows are created only inside
# those temporary databases and are discarded after pytest finishes.

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_ROOT"

cleanup() {
  find "$PROJECT_ROOT" \
    \( -name '__pycache__' -o -name '*.pyc' -o -name '.pytest_cache' -o -name '.DS_Store' \) \
    -print -exec rm -rf {} + >/dev/null 2>&1 || true
}
trap cleanup EXIT

echo "== Python syntax =="
python3 -m compileall -q backend/app backend/tests alembic

echo "== Backend release scenarios =="
python3 -m pytest -q \
  backend/tests/test_full_order_journey.py \
  backend/tests/test_cash_and_warehouse.py \
  backend/tests/test_auth_and_orders.py \
  backend/tests/test_smoke_roles.py

echo "== Full backend suite =="
python3 -m pytest -q backend/tests

echo "== Frontend JS syntax =="
for file in frontend/*.js frontend/form-page/*.js; do
  node --check "$file"
done

echo "== Frontend asset links =="
python3 - <<'PY'
from pathlib import Path
import re
import sys

missing = []
for html in Path("frontend").glob("*.html"):
    text = html.read_text(encoding="utf-8")
    for attr in re.findall(r'<script[^>]+src="([^"]+)"', text):
        path = attr.split("?", 1)[0]
        if path.startswith(("http://", "https://")):
            continue
        if not (html.parent / path).exists():
            missing.append((str(html), "script", attr))
    for attr in re.findall(r'<link[^>]+href="([^"]+)"', text):
        path = attr.split("?", 1)[0]
        if path.startswith(("http://", "https://")):
            continue
        if path.endswith(".css") and not (html.parent / path).exists():
            missing.append((str(html), "css", attr))

if missing:
    for item in missing:
        print(f"Missing {item[1]} in {item[0]}: {item[2]}", file=sys.stderr)
    sys.exit(1)
print("frontend asset links ok")
PY

echo "Release smoke-check passed"
