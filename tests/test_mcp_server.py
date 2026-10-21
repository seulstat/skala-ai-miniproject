"""A2 — mcp_server.py: contracts/mcp_spec.py와 이름·시그니처 일치, Tool 결과의 출처 라벨, Resource 섹션 추출(캐시 없음), Prompt 렌더링.

fastmcp in-memory Client로 서버를 직접 호출한다 (subprocess·네트워크 없음). stdio 경로는 test_mcp_client.py가 본다.
"""

import re
import shutil
from pathlib import Path

import pytest
from fastmcp import Client

from agent.prompts import reviewer_prompt
from contracts import mcp_spec
from contracts.deps import DataPaths
from contracts.schemas import POSTING_SECTIONS
from mcp_server import create_server, posting_section
from rag import Retriever

SAMPLE_USER = Path(__file__).resolve().parents[1] / "examples" / "sample_user"


@pytest.fixture
def paths(tmp_path) -> DataPaths:
    root = tmp_path / "user"
    shutil.copytree(SAMPLE_USER, root)
    return DataPaths(root)


@pytest.fixture
def server(paths):
    return create_server(paths, Retriever(paths, model="fake"))


async def _read(client: Client, uri: str) -> str:
    # fastmcp의 Client.read_resource는 AnyUrl 검증 때문에 한글 URI를 거부한다. 운영 경로(MCPClient)와 같은 저수준 세션으로 읽는다
    return (await client.session.read_resource(uri)).contents[0].text


# ---------- 이름·시그니처가 contracts/mcp_spec.py와 일치 ----------

async def test_server_registers_exactly_the_contract_names(server):
    async with Client(server) as c:
        assert {t.name for t in await c.list_tools()} == set(mcp_spec.TOOL_ARGS)
        assert [t.uri_template for t in await c.list_resource_templates()] == [mcp_spec.RESOURCE_POSTING]
        prompts = {p.name: [a.name for a in p.arguments or []] for p in await c.list_prompts()}
        assert prompts == {name: list(args) for name, args in mcp_spec.PROMPT_ARGS.items()}
    assert server.name == mcp_spec.SERVER_NAME


async def test_tool_input_schema_matches_search_args(server):
    expected = mcp_spec.SearchArgs.model_json_schema()
    async with Client(server) as c:
        for tool in await c.list_tools():
            schema = tool.input_schema
            assert sorted(schema["properties"]) == sorted(expected["properties"]) == ["k", "query"]
            assert schema["required"] == expected["required"] == ["query"]
            for name, spec in expected["properties"].items():
                for key in ("type", "minLength", "minimum", "maximum", "default"):
                    assert schema["properties"][name].get(key) == spec.get(key), (tool.name, name, key)


async def test_descriptions_say_when_to_use_and_give_argument_examples(server):
    async with Client(server) as c:
        for tool in await c.list_tools():
            assert "사용하세요" in tool.description                      # 언제 쓰는지
            assert "출처 라벨" in tool.description or "[표현ID" in tool.description   # 결과 형식
            assert "예:" in tool.input_schema["properties"]["query"]["description"]
        template = (await c.list_resource_templates())[0]
        assert "때 읽으세요" in template.description and "posting://주요 업무" in template.description
        prompt = (await c.list_prompts())[0]
        assert "호출하세요" in prompt.description and "인자 없음" in prompt.description


async def test_invalid_arguments_are_rejected_as_tool_errors(server):
    async with Client(server) as c:
        for bad in ({"query": ""}, {"query": "x", "k": 0}, {"query": "x", "k": 6}):
            result = await c.call_tool(mcp_spec.TOOL_SEARCH_MY_EXPERIENCE, bad, raise_on_error=False)
            assert result.is_error, bad


# ---------- Tool: 출처 라벨 ----------

async def test_search_my_experience_returns_labelled_evidence(server):
    async with Client(server) as c:
        result = await c.call_tool(mcp_spec.TOOL_SEARCH_MY_EXPERIENCE, {"query": "배송 지연 민원", "k": 2})
    text = result.content[0].text
    assert text.startswith(mcp_spec.LABEL_EXPERIENCE.format(file="experience.md", heading="물류 스타트업 데이터 분석 인턴 (2개월)"))
    assert text.count("[experience.md > ") == 2


async def test_search_expression_bank_returns_labelled_lines(server):
    async with Client(server) as c:
        result = await c.call_tool(mcp_spec.TOOL_SEARCH_EXPRESSION_BANK, {"query": "입사 후 하고 싶은 일"})
    lines = result.content[0].text.splitlines()
    assert len(lines) == 3                                   # k 기본값 3, 템플릿 표현집의 표현 수도 3
    assert all(re.match(r"^\[E\d+, verified=(true|false)\] ", line) for line in lines)


async def test_user_bank_overrides_template_and_edits_are_picked_up(server, paths):
    (paths.root / "expression_bank.json").write_text(
        '{"expressions": [{"id": "U1", "situation": "내 표현", "phrase": "My own phrase.", "verified": true}]}', encoding="utf-8")
    async with Client(server) as c:
        result = await c.call_tool(mcp_spec.TOOL_SEARCH_EXPRESSION_BANK, {"query": "내 표현"})
    assert result.content[0].text == "[U1, verified=true] 내 표현 — My own phrase."


# ---------- Resource: 섹션 추출, 캐시 없음 ----------

@pytest.mark.parametrize("section, expected, not_expected", [
    ("회사 소개", "가상의 이커머스 기업", "물류 병목 구간 탐지"),
    ("주요 업무", "물류 병목 구간 탐지", "SQL과 Python"),
    ("자격 요건", "OPIc IM1 이상", "지표 설계"),
    ("우대 사항", "지표 설계·개선 경험", "코딩·SQL 테스트"),
    ("전형 절차", "코딩·SQL 테스트", "약 8분"),
    ("영어 면접 안내", "약 8분은 영어로 진행", "가상의 이커머스 기업"),
])
async def test_posting_resource_extracts_one_section(server, section, expected, not_expected):
    assert section in POSTING_SECTIONS
    async with Client(server) as c:
        text = await _read(c, mcp_spec.posting_uri(section))
    assert text.startswith(mcp_spec.LABEL_POSTING.format(section=section) + "\n")
    assert expected in text and not_expected not in text
    assert "## " not in text                                 # 다음 섹션 제목이 딸려 오지 않는다


async def test_posting_resource_all_returns_whole_document(server, paths):
    async with Client(server) as c:
        text = await _read(c, mcp_spec.posting_uri("전체"))
    assert text == "[job_posting > 전체]\n" + paths.job_posting.read_text(encoding="utf-8")
    assert all(f"## {s}" in text for s in POSTING_SECTIONS)


async def test_posting_resource_unknown_section_says_so(server):
    async with Client(server) as c:
        assert await _read(c, mcp_spec.posting_uri("없는 섹션")) == "'없는 섹션' 섹션이 없습니다."


async def test_posting_resource_is_read_fresh_every_time(server, paths):
    async with Client(server) as c:
        before = await _read(c, mcp_spec.posting_uri("주요 업무"))
        paths.job_posting.write_text(
            paths.job_posting.read_text(encoding="utf-8").replace("물류 병목 구간 탐지", "수요 예측 모델 운영"), encoding="utf-8")
        after = await _read(c, mcp_spec.posting_uri("주요 업무"))
    assert "물류 병목 구간 탐지" in before and "수요 예측 모델 운영" in after


def test_posting_section_handles_crlf_and_last_section_without_trailing_newline():
    text = "# 공고\r\n## 주요 업무\r\n- A\r\n- B\r\n## 자격 요건\r\n- C"
    assert posting_section(text, "주요 업무") == "[job_posting > 주요 업무]\n- A\r\n- B"
    assert posting_section(text, "자격 요건") == "[job_posting > 자격 요건]\n- C"


# ---------- Prompt: 렌더링 ----------

async def test_persona_prompt_renders_default_rules_with_reviewer_prompt(server, paths):
    default_rules = paths.persona_rules.read_text(encoding="utf-8")
    assert paths.persona_rules.name == "persona_rules.default.md"
    async with Client(server) as c:
        result = await c.get_prompt(mcp_spec.PROMPT_PERSONA_REVIEW)
    text = result.messages[0].content.text
    assert text == reviewer_prompt(default_rules)
    assert "R1" in text and "[검사 방법]" in text            # 규칙 표와 검사 지시문이 모두 들어 있다


async def test_persona_prompt_uses_user_rules_and_is_not_cached(server, paths):
    async with Client(server) as c:
        first = (await c.get_prompt(mcp_spec.PROMPT_PERSONA_REVIEW)).messages[0].content.text
        (paths.root / "persona_rules.md").write_text("# 내 규칙\n| R1 | 금지: very | 대신: quite |\n", encoding="utf-8")
        second = (await c.get_prompt(mcp_spec.PROMPT_PERSONA_REVIEW)).messages[0].content.text
    assert "내 규칙" not in first
    assert second == reviewer_prompt("# 내 규칙\n| R1 | 금지: very | 대신: quite |\n")
