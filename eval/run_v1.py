"""Before(v1): 10/13 CLI 그래프(`skala-ai-agent/practice/dapdap`)를 원본 그대로 불러 측정한다 (ADR-0009).

원본 run_eval.py는 결과를 실제 개인 서류 폴더(data/private)에 쓰고 persona.md·career.md를 전제로 해서,
지표 정의는 eval/common.py로 같게 두고 실행 경로만 이 파일에서 바꾼다. 원본 코드는 수정하지 않는다.

실행 (10/13 venv, 이 프로젝트 폴더에서 — 이 프로젝트의 .env(OPENAI_API_KEY)를 쓰게):
    DAPDAP_USER_DIR=<sample_user 복사본> <10/13 venv>/bin/python eval/run_v1.py <테스트셋.json> [반복 번호]
"""

import asyncio
import os
import signal
import sys
import time
from datetime import date, timedelta
from pathlib import Path

PRACTICE = Path(os.getenv("V1_PRACTICE_DIR", "/Users/seul/skala/workspace/skala-ai-agent/practice"))
MODEL = "openai:gpt-4o-mini"
CASE_TIMEOUT = 180   # 초. 넘으면 TIMEOUT 실패로 기록 (10/13 그래프가 Tool 상한에서 무한 반복하는 경우)
sys.path[:0] = [str(PRACTICE), str(Path(__file__).resolve().parents[1])]
os.environ["DAPDAP_MODEL"] = MODEL
os.environ.setdefault("DAPDAP_EMBEDDING", "openai:text-embedding-3-small")

from dapdap.graph import build_graph, card_text, run  # noqa: E402
from dapdap.prompts import banned_hits  # noqa: E402
from dapdap.schemas import ExpressionCard  # noqa: E402

from eval.common import applicant_text, judge, load_cases, save, summarize  # noqa: E402


def _timeout(signum, frame):
    raise TimeoutError(f"{CASE_TIMEOUT}s 초과")


def main(cases_file: str, rep: str) -> None:
    signal.signal(signal.SIGALRM, _timeout)
    user_dir = Path(os.environ["DAPDAP_USER_DIR"])
    assert PRACTICE not in user_dir.resolve().parents, "10/13 폴더(실제 개인 서류 포함)의 데이터는 쓰지 않는다"
    applicant = applicant_text(user_dir)
    graph = build_graph()
    tomorrow = (date.today() + timedelta(days=1)).isoformat()   # 복습 케이스: 이번 실행에서 저장한 카드가 due
    signal.alarm(CASE_TIMEOUT)
    try:   # 예열(지표 제외). 10/13 그래프가 여기서 실패해도 측정은 계속한다 — 실패는 각 케이스 행에 남는다
        run(graph, "그 프로젝트에서 무엇을 배웠는지 말하고 싶어요", f"v1-{rep}-warmup", approve_fn=lambda p: False)
    except Exception as e:
        print(f"warmup 실패: {type(e).__name__}", flush=True)
    signal.alarm(0)
    rows = []
    for c in load_cases(cases_file):
        row = {"id": c["id"], "input": c["input"], "expected": c["intent"]}
        t0 = time.time()
        signal.alarm(CASE_TIMEOUT)
        try:
            today = tomorrow if c["intent"] == "review" else ""
            s = run(graph, c["input"], f"v1-{rep}-{c['id']}", approve_fn=lambda p: True, today=today)
            row.update(intent=s["intent"], seconds=round(time.time() - t0, 1), rewrites=s.get("retry_count", 0),
                       tools=s.get("tools_used", []), warning=s.get("warning"))
            if "card" in s:
                ExpressionCard.model_validate(s["card"])
                row.update(card=s["card"], structured_ok=True, banned=banned_hits(card_text(s["card"])))
        except Exception as e:  # 실패도 지표에 남긴다
            row.update(error="TIMEOUT" if isinstance(e, TimeoutError) else type(e).__name__, detail=str(e)[:300],
                       seconds=round(time.time() - t0, 1))
        signal.alarm(0)
        if row.get("card"):
            row["judge"] = asyncio.run(judge(row["card"], applicant))
        print(f"{c['id']} {row.get('intent')} {row['seconds']}s err={row.get('error', '')}", flush=True)
        rows.append(row)
    summary = summarize(rows)
    print(save(f"v1_{Path(cases_file).stem}_r{rep}.json", {"version": "v1", "model": MODEL, "summary": summary,
                                                           "rows": rows}))
    print(summary)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "1")
    sys.stdout.flush()
    os._exit(0)   # 10/13 코드가 남기는 백그라운드 스레드 때문에 정상 종료가 걸린다
