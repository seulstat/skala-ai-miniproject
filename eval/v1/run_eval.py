# 출처: skala-ai-agent/practice/scripts/run_eval.py (Phase 0 복사, 로직 미변경)
"""테스트셋 10개로 Agent를 자동 평가한다 (HITL은 자동 승인).

사용법:
    python scripts/run_eval.py google_genai:gemini-3.5-flash-lite
    python scripts/run_eval.py openai:gpt-4o-mini

지표: M1 라우팅 정확도 / M2 구조화 출력 / M3 금지 표현 / M4 개인 맥락(LLM-judge, baseline 대비) / M5 지연 시간
결과(내 서류 기반 출력 포함)는 data/private/eval_<모델>.json 에 저장한다.
"""

import json
import os
import sys
import time
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ["DAPDAP_MODEL"] = sys.argv[1] if len(sys.argv) > 1 else "google_genai:gemini-3.5-flash-lite"

from pydantic import BaseModel, Field  # noqa: E402

from dapdap import config, tools  # noqa: E402
from dapdap.baseline import run_baseline  # noqa: E402
from dapdap.graph import build_graph, card_text, load_profile, run  # noqa: E402
from dapdap.prompts import banned_hits  # noqa: E402
from dapdap.schemas import ExpressionCard  # noqa: E402

MODEL = os.environ["DAPDAP_MODEL"]
SAFE = MODEL.replace(":", "_").replace("/", "_")
JUDGE_MODEL = "openai:gpt-4o-mini"   # 두 모델 비교 시 심판은 고정

# 평가용 카드 DB를 따로 써서 실제 카드 DB를 건드리지 않는다
tools.CARDS_PATH = config.PRIVATE / f"cards_eval_{SAFE}.json"
tools.CARDS_PATH.unlink(missing_ok=True)


class Judgement(BaseModel):
    personalization: int = Field(ge=1, le=5, description="지원자의 실제 경험·수치·공고 포인트를 반영한 정도")
    interview_fit: int = Field(ge=1, le=5, description="영어 면접에서 그대로 말해도 자연스럽고 적절한 정도")
    reason: str


def judge(card: dict, applicant: str) -> Judgement:
    prompt = f"""당신은 영어 면접 코치입니다. 아래 지원자 정보를 참고해 카드의 영어 표현을 1~5점으로 채점하세요.
5점 = 이 지원자만 할 수 있는 구체적 내용(실제 연구·활동·수치)과 공고 포인트를 정확히 반영
1점 = 누구에게나 해당하는 일반적 번역

[지원자 정보]
{applicant}

[카드]
{json.dumps(card, ensure_ascii=False)}"""
    return config.get_model(JUDGE_MODEL).with_structured_output(Judgement).invoke(prompt)


def main() -> None:
    cases = json.loads((config.DATA / "test_cases.json").read_text(encoding="utf-8"))
    applicant = (config.DOCS_DIR / "persona.md").read_text(encoding="utf-8")[:2500] + "\n\n" + \
                (config.DOCS_DIR / "career.md").read_text(encoding="utf-8")[:1200]
    profile = load_profile()
    graph = build_graph()
    tomorrow = (date.today() + timedelta(days=1)).isoformat()   # 복습 케이스: 어제 저장한 카드가 오늘 due

    rows = []
    for c in cases:
        row = {"id": c["id"], "input": c["input"], "expected": c["intent"]}
        t0 = time.time()
        try:
            today = tomorrow if c["intent"] == "review" else ""
            s = run(graph, c["input"], f"eval-{c['id']}", approve_fn=lambda p: True, today=today)
            row.update(intent=s["intent"], seconds=round(time.time() - t0, 1),
                       retries=s.get("retry_count", 0), tools=s.get("tools_used", []),
                       review_log=s.get("review_log", []), final=s.get("final_message", ""))
            if "card" in s:
                card = s["card"]
                ExpressionCard.model_validate(card)
                row.update(card=card, structured_ok=True, banned=banned_hits(card_text(card)),
                           has_evidence=bool(card.get("evidence")), warning=s.get("warning"))
        except Exception as e:  # 실패도 지표에 남긴다
            row.update(error=f"{type(e).__name__}: {str(e)[:300]}", seconds=round(time.time() - t0, 1),
                       structured_ok=False)
        print(f"{c['id']} {row.get('intent')} ({row['seconds']}s) retries={row.get('retries')} "
              f"err={row.get('error', '')[:80]}", flush=True)

        if c["intent"] == "express" and "card" in row:       # M4: baseline과 같은 심판으로 비교
            _, base_card = run_baseline(profile, c["input"])
            row["baseline_card"] = base_card.model_dump()
            row["judge_agent"] = judge(row["card"], applicant).model_dump()
            row["judge_baseline"] = judge(row["baseline_card"], applicant).model_dump()
        rows.append(row)

    gen = [r for r in rows if r["expected"] in ("express", "answer")]
    judged = [r for r in rows if "judge_agent" in r]
    avg = lambda xs: round(sum(xs) / len(xs), 2) if xs else None
    summary = {
        "model": MODEL,
        "M1_routing": f"{sum(r.get('intent') == r['expected'] for r in rows)}/{len(rows)}",
        "M2_structured": f"{sum(bool(r.get('structured_ok')) for r in gen)}/{len(gen)}",
        "M3_banned_final": sum(len(r.get("banned", [])) for r in gen),
        "M4_personalization_agent": avg([r["judge_agent"]["personalization"] for r in judged]),
        "M4_personalization_baseline": avg([r["judge_baseline"]["personalization"] for r in judged]),
        "M4_interview_fit_agent": avg([r["judge_agent"]["interview_fit"] for r in judged]),
        "M4_interview_fit_baseline": avg([r["judge_baseline"]["interview_fit"] for r in judged]),
        "M4_evidence_rate": f"{sum(bool(r.get('has_evidence')) for r in gen)}/{len(gen)}",
        "M5_avg_seconds_generate": avg([r["seconds"] for r in gen]),
        "M5_avg_seconds_all": avg([r["seconds"] for r in rows]),
        "reflection_retries_total": sum(r.get("retries") or 0 for r in gen),
        "errors": [f"{r['id']}: {r['error']}" for r in rows if "error" in r],
    }
    out = config.PRIVATE / f"eval_{SAFE}.json"
    out.write_text(json.dumps({"summary": summary, "rows": rows}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
