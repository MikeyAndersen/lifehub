#!/usr/bin/env bash
# Hurtig manuel kørsel af gpu_agent.py fra denne mappe.
# Uden argumenter: --now (spring GPU-tjekket over og tøm køen straks).
# Egne argumenter overtager, fx:  ./run.sh --once   |   ./run.sh --minutes 25
set -euo pipefail

cd "$(dirname "$0")"

# Find en Python (python / python3 / py).
if command -v python >/dev/null 2>&1; then
  PY=python
elif command -v python3 >/dev/null 2>&1; then
  PY=python3
elif command -v py >/dev/null 2>&1; then
  PY="py -3"
else
  echo "Fandt ingen python på PATH." >&2
  exit 1
fi

if [ "$#" -eq 0 ]; then
  set -- --now
fi

exec $PY gpu_agent.py "$@"
