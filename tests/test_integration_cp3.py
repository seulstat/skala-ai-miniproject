"""CP3 브라우저 E2E에서 발견한 문제의 회귀 테스트 (Lead 소유)."""

from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import InMemorySaver

from agent.graph import build_graph
from agent.llm import ToolCallingFakeChatModel, make_llm
from agent.store import SQLiteCardStore
from contracts import events, schemas
from contracts.deps import DataPaths, Deps
from contracts.fixtures import load
from services.posting import normalize_posting

REAL_STYLE_POSTING = """[정규직 전환형] 비즈니스 데이터 분석가 인턴
[담당하시게 될 업무를 소개합니다]
• 문제 정의, 가설 설정, 실험 설계
[이런 분을 찾습니다]
• SQL, Python 활용 능력
[이런 분이면 더 좋아요]
• A/B 테스트 경험"""


async def test_posting_falls_back_to_rules_when_llm_returns_empty():
    empty = ToolCallingFakeChatModel(messages=iter([AIMessage(content="")]))   # thinking 모드에서 본문이 빈 상황
    draft = await normalize_posting(empty, REAL_STYLE_POSTING)
    assert {"주요 업무", "자격 요건", "우대 사항"} <= set(draft.sections)
    assert draft.missing_required == []


def test_ollama_models_disable_thinking():
    assert make_llm("ollama:qwen3.5:4b").reasoning is False


async def test_review_intent_shows_saved_cards_when_nothing_is_due(tmp_path):
    paths = DataPaths(tmp_path)
    store = SQLiteCardStore(paths.coach_db)
    await store.save_card(schemas.ExpressionCard.model_validate(load("card_express.json")))   # 내일 복습 예정
    route = AIMessage(content="", tool_calls=[{"name": "Route", "args": {"intent": "review", "reason": "r"}, "id": "r"}])
    deps = Deps(fast_llm=ToolCallingFakeChatModel(messages=iter([route])), quality_llm=None, mcp=None, store=store,
                checkpointer=InMemorySaver(), paths=paths)
    got = [events.parse_event(e) async for e in build_graph(deps).astream(
        {"user_input": "오늘 복습할 카드 보여줘"}, {"configurable": {"thread_id": "r"}}, stream_mode="custom")]
    reply = got[-1].reply
    assert "C0001" in reply and "최근 저장한 카드" in reply
