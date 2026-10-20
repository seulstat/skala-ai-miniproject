"""계약 테스트 (Lead 소유): import, 스키마 round-trip, fixture가 스키마를 만족하는지, 상수 일관성."""

import json
from datetime import date
from typing import get_args

import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import InMemorySaver

from contracts import api, events, mcp, schemas, state
from contracts.deps import CardStore, DataPaths, Deps, MCPPort
from contracts.fixtures import FIXTURE_DIR, FIXTURE_SCHEMAS, SSE_FIXTURES, load, load_model


def test_every_fixture_file_is_registered():
    on_disk = {p.name for p in FIXTURE_DIR.glob("*.json")}
    assert on_disk == set(FIXTURE_SCHEMAS) | set(SSE_FIXTURES)


@pytest.mark.parametrize("name", sorted(FIXTURE_SCHEMAS))
def test_fixture_matches_schema_and_round_trips(name):
    obj = load_model(name)
    items = obj if isinstance(obj, list) else [obj]
    for item in items:
        assert type(item).model_validate_json(item.model_dump_json()) == item


@pytest.mark.parametrize("name", SSE_FIXTURES)
def test_sse_fixture_is_valid_sequence(name):
    seq = load(name)
    assert seq[-1] == "[DONE]"
    parsed = [events.parse_event(e) for e in seq[:-1]]
    assert events.is_valid_sequence([e.type for e in parsed] + ["[DONE]"])
    for e in parsed:
        line = events.to_sse(e)
        assert line.startswith("data: ") and line.endswith("\n\n")
        assert events.parse_event(json.loads(line[6:])) == e


@pytest.mark.parametrize("types, ok", [
    (["RouteDecided", "FinalAnswer", "[DONE]"], True),
    (["RouteDecided", "CardDrafted", "ReviewDone", "ApprovalRequired", "[DONE]"], True),
    (["RouteDecided", "EvidenceSearched", "CardDrafted", "ReviewDone", "FinalAnswer", "[DONE]"], True),  # 오류 종료
    (["RouteDecided", "ApprovalRequired", "[DONE]"], False),
    (["CardDrafted", "ReviewDone", "ApprovalRequired", "[DONE]"], False),
    (["RouteDecided", "FinalAnswer"], False),
])
def test_sequence_rule(types, ok):
    assert events.is_valid_sequence(types) is ok


def test_invalid_enum_rejected():
    data = load("profile.json") | {"tone_preference": "아무거나"}
    with pytest.raises(ValueError):
        schemas.UserProfile.model_validate(data)


def test_intent_mapping_covers_all_intents():
    assert set(state.INTENT_TO_NODE) == set(get_args(schemas.Intent))
    assert state.MAX_REWRITES == 2


def test_saved_card_stage_bounds():
    card = load("card_express.json")
    with pytest.raises(ValueError):
        schemas.SavedCard(**card, id="C1", created="2026-10-20", next_review="2026-10-21", stage=3)
    assert len(schemas.REVIEW_INTERVALS_DAYS) == 3


def test_mcp_names_and_args():
    assert set(mcp.TOOL_ARGS) == {"search_my_experience", "search_expression_bank"}
    assert mcp.posting_uri("주요 업무") == "posting://주요 업무"
    assert mcp.PROMPT_PERSONA_REVIEW == "persona_review_prompt"
    assert set(mcp.AGENT_TOOL_NAMES) == {"search_my_experience", "search_expression_bank", "get_job_posting"}
    with pytest.raises(ValueError):
        mcp.SearchArgs(query="x", k=9)


def test_routes_unique():
    assert len(set(api.ROUTES.values())) == len(api.ROUTES)


def test_data_paths_fallback_to_templates(data_paths):
    assert data_paths.profile.parent == data_paths.root
    assert data_paths.persona_rules.name == "persona_rules.default.md" and data_paths.persona_rules.exists()
    assert DataPaths.from_env().root.is_absolute()


class _FakeMCP:
    async def call_tool(self, name: str, arguments: dict) -> str:
        return "[experience.md > 고객 이탈 예측 졸업 프로젝트]\n..."

    async def read_resource(self, uri: str) -> str:
        return "[job_posting > 전체]\n..."

    async def get_prompt(self, name: str, arguments: dict) -> str:
        return "검수 규칙"


class _FakeStore:
    async def save_card(self, card, today: date | None = None):
        ...

    async def list_cards(self):
        return []

    async def due_cards(self, today: date | None = None):
        return []

    async def review(self, card_id, outcome, today: date | None = None):
        ...

    async def known_chunks(self):
        return []


async def test_deps_assembles_with_fakes(data_paths):
    llm = GenericFakeChatModel(messages=iter([AIMessage(content="ok")]))
    deps = Deps(fast_llm=llm, quality_llm=llm, mcp=_FakeMCP(), store=_FakeStore(),
                checkpointer=InMemorySaver(), paths=data_paths)
    assert isinstance(deps.mcp, MCPPort) and isinstance(deps.store, CardStore)
    assert (await deps.fast_llm.ainvoke("hi")).content == "ok"
    assert (await deps.mcp.call_tool(mcp.TOOL_SEARCH_MY_EXPERIENCE, {"query": "q"})).startswith("[")
