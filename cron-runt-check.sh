#!/bin/bash
set -euo pipefail
cd /Users/david/dev/dacrypt/tesla

if [ -x .venv/bin/python3 ]; then
  PY=.venv/bin/python3
else
  PY=python3
fi

rm -f history/last-changes.json history/pending-alert.txt

"$PY" refresh-mission-control.py
CHANGE_OUTPUT=$("$PY" change-detector.py 2>&1 || true)
echo "$CHANGE_OUTPUT"
bash build-activity-log.sh

if echo "$CHANGE_OUTPUT" | grep -q "✅ No changes detected"; then
  echo "NO_CHANGES"
  exit 0
fi

if [ -f history/last-changes.json ]; then
  python3 - <<'PY'
import json
from pathlib import Path
p = Path('history/last-changes.json')
if not p.exists():
    print('NO_CHANGES')
    raise SystemExit(0)
obj = json.loads(p.read_text())
if obj.get('has_changes'):
    print(obj.get('alert','').strip())
else:
    print('NO_CHANGES')
PY
else
  echo "NO_CHANGES"
fi
