"""/api/profile · /api/docs · /api/posting · /api/readiness (design §6 테스트 8·9). fake Deps·tmp_path, 네트워크 없음."""

import json

from test_api_support import deps_factory, error_code, running_app, seed

from contracts.api import ErrorResponse, ReadinessResponse
from contracts.errors import ERROR_CATALOG
from contracts.fixtures import load
from contracts.schemas import UserProfile


def _item(report: ReadinessResponse, name: str):
    return next(i for i in report.items if i.item == name)


async def _readiness(client) -> ReadinessResponse:
    r = await client.get("/api/readiness")
    assert r.status_code == 200
    return ReadinessResponse.model_validate(r.json())


# ---------- 테스트 8: 준비 점검이 필수 항목 누락·개인정보 패턴을 잡는다 ----------

async def test_readiness_ok_for_sample_user(tmp_path):
    async with running_app(deps_factory(seed(tmp_path), [], [])) as client:
        report = await _readiness(client)
    assert report.ready
    assert [i.item for i in report.items] == ["프로필", "경험 문서", "공고", "개인정보"]
    assert [i.status for i in report.items[:3]] == ["ok", "ok", "ok"]
    assert _item(report, "개인정보").status == "warn"   # 외부 LLM 전송 안내는 항상 나오지만 차단하지 않는다


async def test_readiness_reports_every_missing_required_input(data_paths):
    async with running_app(deps_factory(data_paths, [], [])) as client:
        report = await _readiness(client)
    assert not report.ready
    assert [i.status for i in report.items[:3]] == ["error", "error", "error"]
    assert "profile.json" in _item(report, "프로필").message


async def test_readiness_flags_each_input_problem(tmp_path):
    paths = seed(tmp_path)
    profile = json.loads(paths.profile.read_text(encoding="utf-8"))
    profile["goal"] = "★ 내용으로 바꾸세요"
    paths.profile.write_text(json.dumps(profile, ensure_ascii=False), encoding="utf-8")
    (paths.docs_dir / "experience.md").write_text("제목 없이 숫자 없는 짧은 글", encoding="utf-8")
    paths.job_posting.write_text("## 회사 소개\n어떤 회사\n\n## 주요 업무\n(공고에 명시 없음)\n", encoding="utf-8")
    async with running_app(deps_factory(paths, [], [])) as client:
        report = await _readiness(client)
    assert not report.ready
    assert "★" in _item(report, "프로필").message
    assert "# 제목" in _item(report, "경험 문서").message
    posting = _item(report, "공고")
    assert posting.status == "error" and "주요 업무" in posting.message and "자격 요건" in posting.message


async def test_readiness_warns_but_stays_ready_on_short_docs_without_numbers(tmp_path):
    paths = seed(tmp_path)
    (paths.docs_dir / "experience.md").write_text("# 인턴\n배송 지연 원인을 분석했다.", encoding="utf-8")
    async with running_app(deps_factory(paths, [], [])) as client:
        report = await _readiness(client)
    docs = _item(report, "경험 문서")
    assert report.ready and docs.status == "warn" and "숫자" in docs.message


async def test_readiness_detects_personal_info_patterns(tmp_path):
    paths = seed(tmp_path)
    phone = "-".join(("010", "1234", "5678"))   # 소스에 실제 번호 모양이 남지 않게 조립한다
    rrn = "-".join(("900101", "1234567"))
    (paths.docs_dir / "experience.md").write_text(
        f"# 인턴\n담당자 연락처 {phone}, 메일 someone@example.com, 주민번호 {rrn}. 매출 100건, 2025년 12월.\n" * 30,
        encoding="utf-8")
    async with running_app(deps_factory(paths, [], [])) as client:
        report = await _readiness(client)
    privacy = _item(report, "개인정보")
    assert report.ready and privacy.status == "warn"   # 경고일 뿐 차단하지 않는다
    for label in ("전화번호", "이메일", "주민등록번호"):
        assert f"experience.md: {label}" in privacy.message


# ---------- 테스트 9: /api/profile 잘못된 enum → 422 ErrorResponse(INPUT_INVALID) ----------

async def test_put_profile_invalid_enum_returns_422_input_invalid(data_paths):
    body = {**load("profile.json"), "tone_preference": "아무말"}
    async with running_app(deps_factory(data_paths, [], [])) as client:
        r = await client.put("/api/profile", json=body)
    assert r.status_code == ERROR_CATALOG["INPUT_INVALID"].http_status == 422
    error = ErrorResponse.model_validate(r.json()).error
    assert (error.code, error.layer, error.recoverable) == ("INPUT_INVALID", "application", False)
    assert error.user_message == ERROR_CATALOG["INPUT_INVALID"].user_message
    assert error.trace_id and "아무말" not in r.text   # 내부 원인은 응답에 싣지 않는다
    assert not data_paths.profile.exists()


async def test_profile_roundtrip_and_missing_is_404(data_paths):
    profile = load("profile.json")
    async with running_app(deps_factory(data_paths, [], [])) as client:
        missing = await client.get("/api/profile")
        assert (missing.status_code, error_code(missing)) == (404, "NOT_FOUND")
        assert (await client.put("/api/profile", json=profile)).json() == {"ok": True}
        got = await client.get("/api/profile")
    assert got.status_code == 200 and UserProfile.model_validate(got.json()) == UserProfile.model_validate(profile)
    assert UserProfile.model_validate_json(data_paths.profile.read_text(encoding="utf-8")).target_role


async def test_get_profile_with_broken_file_is_422(data_paths):
    data_paths.profile.write_text("{ not json", encoding="utf-8")
    async with running_app(deps_factory(data_paths, [], [])) as client:
        r = await client.get("/api/profile")
    assert (r.status_code, error_code(r)) == (422, "INPUT_INVALID")
