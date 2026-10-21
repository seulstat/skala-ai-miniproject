"""Before/After 공통 정의 (ADR-0009): 테스트셋·심판(LLM-judge)·요약 지표. v1·v2 실행기가 같은 함수를 쓴다.

지표 정의는 10/13 `scripts/run_eval.py`(eval/v1/run_eval.py)를 따른다.
M1 라우팅 정확도 / M2 구조화 출력 성공 / M3 금지 표현 / M4 개인 맥락(LLM-judge) / M5 지연 + Tool 호출 수·재작성 횟수·오류 코드.
이 파일은 v1 venv(10/13)에서도 import되므로 이 프로젝트의 contracts·agent를 import하지 않는다.
"""

import json
import statistics
from pathlib import Path

from langchain.chat_models import init_chat_model
from pydantic import BaseModel, Field

EVAL_DIR = Path(__file__).resolve().parent
RESULTS = EVAL_DIR / "results"
JUDGE_MODEL = "openai:gpt-4o-mini"   # 심판은 고정
GEN_INTENTS = ("express", "answer")


class Judgement(BaseModel):
    personalization: int = Field(ge=1, le=5, description="지원자의 실제 경험·수치·공고 포인트를 반영한 정도")
    interview_fit: int = Field(ge=1, le=5, description="영어 면접에서 그대로 말해도 자연스럽고 적절한 정도")
    reason: str


JUDGE_PROMPT = """당신은 영어 면접 코치입니다. 아래 지원자 정보를 참고해 카드의 영어 표현을 1~5점으로 채점하세요.
5점 = 이 지원자만 할 수 있는 구체적 내용(실제 연구·활동·수치)과 공고 포인트를 정확히 반영
1점 = 누구에게나 해당하는 일반적 번역

[지원자 정보]
{applicant}

[카드]
{card}"""


def load_cases(name: str) -> list[dict]:
    return json.loads((EVAL_DIR / name).read_text(encoding="utf-8"))


def applicant_text(user_dir: Path) -> str:
    """심판에게 줄 지원자 정보 = 프로필 + 경험 문서 + 공고 (v1의 persona·career 대신, 같은 분량 한도)."""
    parts = [(user_dir / "profile.json").read_text(encoding="utf-8")]
    parts += [p.read_text(encoding="utf-8") for p in sorted((user_dir / "docs").glob("*.md"))]
    parts.append((user_dir / "job_posting.md").read_text(encoding="utf-8"))
    return "\n\n".join(parts)[:3700]


async def judge(card: dict, applicant: str) -> dict:
    model = init_chat_model(JUDGE_MODEL).with_structured_output(Judgement)
    prompt = JUDGE_PROMPT.format(applicant=applicant, card=json.dumps(card, ensure_ascii=False))
    return (await model.ainvoke(prompt)).model_dump()


def _avg(xs: list) -> float | None:
    xs = [x for x in xs if x is not None]
    return round(statistics.mean(xs), 2) if xs else None


def summarize(rows: list[dict]) -> dict:
    gen = [r for r in rows if r["expected"] in GEN_INTENTS]
    judged = [r for r in rows if r.get("judge")]
    errors: dict[str, int] = {}
    for r in rows:
        if r.get("error"):
            errors[r["error"]] = errors.get(r["error"], 0) + 1
    return {
        "n": len(rows),
        "M1_routing": f"{sum(r.get('intent') == r['expected'] for r in rows)}/{len(rows)}",
        "M2_structured": f"{sum(bool(r.get('structured_ok')) for r in gen)}/{len(gen)}",
        "M3_banned_final": sum(len(r.get("banned", [])) for r in gen),
        "M4_personalization": _avg([r["judge"]["personalization"] for r in judged]),
        "M4_interview_fit": _avg([r["judge"]["interview_fit"] for r in judged]),
        "M5_avg_seconds_generate": _avg([r["seconds"] for r in gen if r.get("structured_ok")]),   # 성공한 카드만 (실패는 errors)
        "M5_avg_seconds_all": _avg([r["seconds"] for r in rows]),
        "tool_calls_avg": _avg([len(r.get("tools", [])) for r in gen if r.get("structured_ok")]),
        "rewrites_avg": _avg([r.get("rewrites", 0) for r in gen if r.get("structured_ok")]),
        "errors": errors,
    }


def save(name: str, data: dict) -> Path:
    RESULTS.mkdir(exist_ok=True)
    out = RESULTS / name
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return out
