#!/usr/bin/env bash
# Before/After 측정 일괄 실행 (ADR-0009). v1·v2 각 3회(sample 테스트셋) + 참고용 기존 테스트셋 1회. 순차 실행(지연 측정 간섭 방지).
set -uo pipefail
cd "$(dirname "$0")/.."
V1_PY=${V1_PY:-/Users/seul/skala/workspace/skala-ai-agent/.venv/bin/python}
TMP=$(mktemp -d)
for set in test_cases_sample.json; do
  for rep in 1 2 3; do
    rm -rf "$TMP/v1_user" && cp -R examples/sample_user "$TMP/v1_user"
    echo "== v1 $set r$rep"; DAPDAP_USER_DIR="$TMP/v1_user" "$V1_PY" eval/run_v1.py "$set" "$rep" | grep --line-buffered -E "^S|^T|M1_|warmup"
    echo "== v2 $set r$rep"; .venv/bin/python eval/run_v2.py "$set" "$rep" | grep --line-buffered -E "^S|^T|M1_|warmup"
  done
done
rm -rf "$TMP/v1_user" && cp -R examples/sample_user "$TMP/v1_user"
echo "== v1 참고(기존 10건)"; DAPDAP_USER_DIR="$TMP/v1_user" "$V1_PY" eval/run_v1.py v1/test_cases.json ref | grep --line-buffered -E "M1_"
echo "== v2 참고(기존 10건)"; .venv/bin/python eval/run_v2.py v1/test_cases.json ref | grep --line-buffered -E "M1_"
echo "ALL DONE"
