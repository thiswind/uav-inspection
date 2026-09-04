#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
if [[ ! -x .venv-deploy/bin/python ]]; then
  echo 'Please run bash setup.sh first.' >&2
  exit 1
fi
exec .venv-deploy/bin/python deploy.py start "$@"
