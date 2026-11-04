#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd -- "$SCRIPT_DIR/../.." && pwd)"
export PYTHONDONTWRITEBYTECODE=1
/usr/bin/python3 -m unittest discover -s "$ROOT/scripts/linux/tests" -v
exec /usr/bin/python3 -m unittest discover -s "$ROOT/apps/linux/prototype/tests" -v
