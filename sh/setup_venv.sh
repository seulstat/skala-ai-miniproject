#!/usr/bin/env bash
# .venv 생성 + requirements.txt 설치. 이미 설치돼 있으면 빠르게 끝난다.
# worktree에서도 실행 가능 (각 worktree가 자기 .venv를 가진다).
set -euo pipefail
cd "$(dirname "$0")/.."

PY=${PYTHON:-python3.11}
if command -v uv >/dev/null 2>&1; then
  [ -d .venv ] || uv venv -q --python "$PY" .venv
  uv pip install -q --python .venv/bin/python -r requirements.txt
else
  [ -d .venv ] || "$PY" -m venv .venv
  .venv/bin/python -m pip install -q -r requirements.txt
fi
echo "[setup_venv] OK: $(.venv/bin/python --version)"
