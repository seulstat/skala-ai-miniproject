#!/usr/bin/env bash
# 시연용 샘플 데이터(examples/sample_user)를 COACH_DATA_DIR로 복사한다.
# 실제 개인 서류는 쓰지 않는다 (design §8 개인정보). 기존 파일은 덮어쓰지 않는다 (-n).
set -euo pipefail
cd "$(dirname "$0")/.."
[ -f .env ] && set -a && . ./.env && set +a
DEST=${COACH_DATA_DIR:-./data}
mkdir -p "$DEST/docs"
cp -n examples/sample_user/profile.json "$DEST/" || true
cp -n examples/sample_user/job_posting.md "$DEST/" || true
cp -n examples/sample_user/docs/*.md "$DEST/docs/" || true
echo "[seed_sample] $DEST 에 샘플 데이터 준비 완료"
ls -R "$DEST" | head -20
