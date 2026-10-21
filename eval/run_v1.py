"""Before(v1): 10/13 CLI 그래프(`skala-ai-agent/practice/dapdap`)를 원본 그대로 불러 측정한다 (ADR-0009).

원본 run_eval.py는 결과를 실제 개인 서류 폴더(data/private)에 쓰고 persona.md·career.md를 전제로 해서,
지표 정의는 eval/common.py로 같게 두고 실행 경로만 이 파일에서 바꾼다. 원본 코드는 수정하지 않는다.

실행 (10/13 venv, 이 프로젝트 폴더에서 — 이 프로젝트의 .env(OPENAI_API_KEY)를 쓰게):
    DAPDAP_USER_DIR=<sample_user 복사본> <10/13 venv>/bin/python eval/run_v1.py <테스트셋.json> [반복 번호]
"""

import asyncio
import json
import os
import subprocess
import sys
import time
from datetime import date, timedelta
from pathlib import Path

PRACTICE = Path(os.getenv("V1_PRACTICE_DIR", "/Users/seul/skala/workspace/skala-ai-agent/practice"))
MODEL = "openai:gpt-4o-mini"
CASE_TIMEOUT = 120   # 초. 넘으면 프로세스를 끊고 TIMEOUT으로 기록 (10/13 그래프가 무한 반복하며 예외도 삼키는 경우가 있어 프로세스 단위로 끊는다)
sys.path[:0] = [str(PRACTICE), str(Path(__file__).resolve().parents[1])]
os.environ["DAPDAP_MODEL"] = MODEL
os.environ.setdefault("DAPDAP_EMBEDDING", "openai:text-embedding-3-small")

from eval.common import applicant_text, judge, load_cases, save, summarize  # noqa: E402


def run_one(cases_file: str, rep: str, case_id: str) -> None:
    """자식 프로세스: 질문 하나를 10/13 그래프로 실행하고 결과 행을 `ROW:` 한 줄로 출력한다."""
    from dapdap.graph import build_graph, card_text, run
    from dapdap.prompts import banned_hits
    from dapdap.schemas import ExpressionCard

    c = next(c for c in load_cases(cases_file) if c["id"] == case_id)
    row = {"id": c["id"], "input": c["input"], "expected": c["intent"]}
    graph = build_graph()
    today = (date.today() + timedelta(days=1)).isoformat() if c["intent"] == "review" else ""  # 저장한 카드가 due
    t0 = time.time()
    try:
        s = run(graph, c["input"], f"v1-{rep}-{c['id']}", approve_fn=lambda p: True, today=today)
        row.update(intent=s["intent"], rewrites=s.get("retry_count", 0), tools=s.get("tools_used", []),
                   warning=s.get("warning"))
        if "card" in s:
            ExpressionCard.model_validate(s["card"])
            row.update(card=s["card"], structured_ok=True, banned=banned_hits(card_text(s["card"])))
    except Exception as e:  # 실패도 지표에 남긴다
        row.update(error=type(e).__name__, detail=str(e)[:300])
    row["seconds"] = round(time.time() - t0, 1)
    print("ROW:" + json.dumps(row, ensure_ascii=False), flush=True)


def main(cases_file: str, rep: str) -> None:
    user_dir = Path(os.environ["DAPDAP_USER_DIR"])
    assert PRACTICE not in user_dir.resolve().parents, "10/13 폴더(실제 개인 서류 포함)의 데이터는 쓰지 않는다"
    applicant = applicant_text(user_dir)
    rows = []
    for c in load_cases(cases_file):
        try:
            done = subprocess.run([sys.executable, __file__, "--one", cases_file, rep, c["id"]], capture_output=True,
                                  text=True, timeout=CASE_TIMEOUT)
            line = next((ln for ln in done.stdout.splitlines() if ln.startswith("ROW:")), None)
            row = json.loads(line[4:]) if line else {"id": c["id"], "input": c["input"], "expected": c["intent"],
                                                      "error": "CRASH", "detail": done.stderr[-300:], "seconds": None}
        except subprocess.TimeoutExpired:
            row = {"id": c["id"], "input": c["input"], "expected": c["intent"], "error": "TIMEOUT",
                   "seconds": CASE_TIMEOUT}
        if row.get("card"):
            row["judge"] = asyncio.run(judge(row["card"], applicant))
        print(f"{c['id']} {row.get('intent')} {row['seconds']}s err={row.get('error', '')}", flush=True)
        rows.append(row)
    summary = summarize(rows)
    print(save(f"v1_{Path(cases_file).stem}_r{rep}.json", {"version": "v1", "model": MODEL, "summary": summary,
                                                           "rows": rows}))
    print(summary)


if __name__ == "__main__":
    if sys.argv[1] == "--one":
        run_one(*sys.argv[2:5])
    else:
        main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "1")
    sys.stdout.flush()
    os._exit(0)   # 10/13 코드가 남기는 백그라운드 스레드 때문에 정상 종료가 걸린다
