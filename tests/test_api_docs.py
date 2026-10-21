"""/api/docs · /api/posting (ADR-0007: FileReader → JSON). fake Deps·tmp_path, 네트워크 없음."""

from langchain_core.messages import AIMessage
from test_api_support import deps_factory, error_code, running_app

from contracts.api import ErrorResponse, ReadinessResponse
from contracts.errors import ERROR_CATALOG
from contracts.schemas import PostingDraft

POSTING_OK = "## 주요 업무\n- 데이터 분석\n\n## 자격 요건\n- SQL\n"


async def _posting_status(client) -> str:
    report = ReadinessResponse.model_validate((await client.get("/api/readiness")).json())
    return next(i.status for i in report.items if i.item == "공고")


# ---------- 경험 문서 (ADR-0007) ----------

async def test_docs_upload_list_delete(data_paths):
    async with running_app(deps_factory(data_paths, [], [])) as client:
        assert (await client.get("/api/docs")).json() == []
        content = "# 활동\n한글 내용"
        added = await client.post("/api/docs", json={"name": "내 경험.md", "content": content})
        assert added.status_code == 200 and added.json()["name"] == "내 경험.md" and added.json()["chars"] == len(content)
        listed = (await client.get("/api/docs")).json()
        assert [d["name"] for d in listed] == ["내 경험.md"] and "T" in listed[0]["updated"]
        assert (data_paths.docs_dir / "내 경험.md").read_text(encoding="utf-8") == content
        assert (await client.delete("/api/docs/내 경험.md")).json() == {"ok": True}
        gone = await client.delete("/api/docs/내 경험.md")
        assert (gone.status_code, error_code(gone)) == (404, "NOT_FOUND")
    assert not (data_paths.docs_dir / "내 경험.md").exists()


async def test_docs_reject_paths_and_non_markdown_names(data_paths):
    async with running_app(deps_factory(data_paths, [], [])) as client:
        for name in ("../evil.md", "a/b.md", "..\\evil.md", "notes.txt"):
            r = await client.post("/api/docs", json={"name": name, "content": "x"})
            assert (r.status_code, error_code(r)) == (422, "INPUT_INVALID"), name
        assert (await client.post("/api/docs", json={"name": "ok.md", "content": ""})).status_code == 422
        r = await client.delete("/api/docs/notes.txt")
        assert (r.status_code, error_code(r)) == (422, "INPUT_INVALID")
    assert list(data_paths.root.rglob("*.md")) == []


async def test_docs_do_not_write_through_symlink_leaving_docs_dir(data_paths, tmp_path_factory):
    outside = tmp_path_factory.mktemp("outside") / "secret.md"
    outside.write_text("원래 내용", encoding="utf-8")
    (data_paths.docs_dir / "link.md").symlink_to(outside)
    async with running_app(deps_factory(data_paths, [], [])) as client:
        r = await client.post("/api/docs", json={"name": "link.md", "content": "덮어쓰기"})
    assert (r.status_code, error_code(r)) == (422, "INPUT_INVALID")
    assert outside.read_text(encoding="utf-8") == "원래 내용"


# ---------- 공고 정리·저장 ----------

NORMALIZED = (
    "# [채용공고] 예시 — 분석가\n\n## 회사 소개\n(공고에 명시 없음)\n\n## 주요 업무\n- 데이터 분석\n\n"
    "## 자격 요건\n- SQL\n\n## 우대 사항\n(공고에 명시 없음)\n\n## 전형 절차\n(공고에 명시 없음)\n\n"
    "## 영어 면접 안내\n- 2차 면접 일부 영어\n"
)


async def test_normalize_posting_uses_quality_llm_and_cleans_output(data_paths):
    fenced = AIMessage(content=f"<think>생각 중</think>```markdown\n{NORMALIZED}\n```")
    async with running_app(deps_factory(data_paths, [], [fenced])) as client:
        r = await client.post("/api/posting/normalize", json={"text": "분석가 채용. SQL 필수. 영어 면접 있음"})
    draft = PostingDraft.model_validate(r.json())
    assert r.status_code == 200 and draft.markdown == NORMALIZED.strip()
    assert set(draft.sections) == {"주요 업무", "자격 요건", "영어 면접 안내"}   # "(공고에 명시 없음)"은 섹션으로 치지 않는다
    assert draft.missing_required == []


async def test_normalize_posting_reports_missing_required_sections(data_paths):
    reply = AIMessage(content="## 회사 소개\n어떤 회사\n\n## 주요 업무\n(공고에 명시 없음)\n\n## 자격 요건\n(공고에 명시 없음)")
    async with running_app(deps_factory(data_paths, [], [reply])) as client:
        r = await client.post("/api/posting/normalize", json={"text": "회사 소개만 있는 공고"})
    assert PostingDraft.model_validate(r.json()).missing_required == ["주요 업무", "자격 요건"]


async def test_normalize_posting_skips_llm_when_already_formatted(data_paths):
    async with running_app(deps_factory(data_paths, [], [])) as client:   # LLM 응답 큐가 비어 있어 호출되면 실패한다
        r = await client.post("/api/posting/normalize", json={"text": POSTING_OK})
    draft = PostingDraft.model_validate(r.json())
    assert r.status_code == 200 and draft.markdown == POSTING_OK.strip() and draft.missing_required == []


async def test_normalize_posting_empty_model_output_is_llm_output_invalid(data_paths):
    async with running_app(deps_factory(data_paths, [], [AIMessage(content="")])) as client:
        r = await client.post("/api/posting/normalize", json={"text": "형식 없는 공고 원문"})
    assert r.status_code == ERROR_CATALOG["LLM_OUTPUT_INVALID"].http_status
    error = ErrorResponse.model_validate(r.json()).error
    assert error.code == "LLM_OUTPUT_INVALID" and error.recoverable


async def test_save_posting_writes_job_posting_and_readiness_follows(data_paths):
    async with running_app(deps_factory(data_paths, [], [])) as client:
        assert await _posting_status(client) == "error"
        assert (await client.put("/api/posting", json={"markdown": POSTING_OK})).json() == {"ok": True}
        assert await _posting_status(client) == "ok"
        empty = await client.put("/api/posting", json={"markdown": ""})
        assert (empty.status_code, error_code(empty)) == (422, "INPUT_INVALID")
    assert data_paths.job_posting.read_text(encoding="utf-8") == POSTING_OK
