#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON:-python3}"

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "Python command not found: $PYTHON_BIN" >&2
  echo "Install Python 3.11+ or set PYTHON=/path/to/python." >&2
  exit 1
fi

if [ ! -d ".venv" ]; then
  "$PYTHON_BIN" -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate

python -m pip install --upgrade pip
python -m pip install -r requirements.txt

# The web viewer imports Three.js from crystal_viewer/web/node_modules, which is
# generated and not in the repository. Without it the page still loads but every
# /vendor/three request answers 503 and no structure is drawn.
if command -v npm >/dev/null 2>&1; then
  NPM_CMD=(npm)
elif command -v corepack >/dev/null 2>&1; then
  # Distributions that ship node without npm still provide corepack.
  NPM_CMD=(corepack npm@10)
else
  NPM_CMD=()
fi

if [ ${#NPM_CMD[@]} -gt 0 ]; then
  (cd crystal_viewer/web && "${NPM_CMD[@]}" ci)
else
  echo "warning: neither npm nor corepack was found." >&2
  echo "         The viewer will start but will not draw structures." >&2
  echo "         Install Node.js, then run: cd crystal_viewer/web && npm ci" >&2
fi

python tools/analyze_structure.py examples/cif/Halite.cif >/dev/null
python tools/analyze_molecule.py examples/molecules/water.xyz >/dev/null

cat <<'EOF'
Setup complete.

Start the web viewer:
  scripts/serve.sh

Start directly in puzzle mode:
  scripts/serve.sh --mode puzzle
EOF
