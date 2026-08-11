#!/bin/zsh
set -euo pipefail
ROOT="${0:A:h:h}"
python3 "$ROOT/scripts/validate_skill_data.py" "$ROOT"
python3 - "$ROOT" <<'PY'
import json
import sys
from pathlib import Path
root = Path(sys.argv[1])
cases = sorted((root / 'cases').glob('**/*.json'))
print('Evaluation fixtures:')
for path in cases:
    case = json.loads(path.read_text(encoding='utf-8'))
    print(f"- {case['id']} [{case['kind']}]")
print('OK: static evaluation completed; use these fixtures for model-vs-label comparison.')
PY
