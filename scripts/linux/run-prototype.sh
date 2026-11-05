#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd -- "$SCRIPT_DIR/../.." && pwd)"
if [[ -z "${WHISPER_SHORTCUT_ENV_FILE:-}" ]]; then
  COMMON_DIR="$(git -C "$ROOT" rev-parse --path-format=absolute --git-common-dir)"
  export WHISPER_SHORTCUT_ENV_FILE="$(dirname -- "$COMMON_DIR")/env/.env"
fi
exec /usr/bin/python3 "$SCRIPT_DIR/../../apps/linux/prototype/desktop_demo.py" "$@"
