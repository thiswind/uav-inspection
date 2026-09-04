#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
exec "${UAV_PYTHON:-python3}" deploy.py install "$@"
