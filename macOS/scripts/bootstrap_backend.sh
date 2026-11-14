#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PYTHON="${PYTHON:-python3}"

"$PYTHON" -m venv "$ROOT_DIR/.venv"
exec "$ROOT_DIR/.venv/bin/python" "$ROOT_DIR/tools/generator_development.py" build

