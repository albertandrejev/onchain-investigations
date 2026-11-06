#!/usr/bin/env bash
# Create .venv if missing, install requirements.txt, then run verify.py with the given arguments.
#   ./start_venv.sh                # everything, offline
#   ./start_venv.sh 03             # one case
#   ./start_venv.sh 03 --refresh   # any verify.py flags
set -euo pipefail
cd "$(dirname "$0")"

[ -d .venv ] || python3 -m venv .venv
.venv/bin/python -m pip install -q -r requirements.txt
exec .venv/bin/python verify.py "$@"
