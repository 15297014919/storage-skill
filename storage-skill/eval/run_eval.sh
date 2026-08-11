#!/bin/zsh
set -euo pipefail
ROOT="${0:A:h:h}"
python3 "$ROOT/scripts/validate_skill_data.py" "$ROOT"
python3 "$ROOT/scripts/evaluate_cases.py" --root "$ROOT"
