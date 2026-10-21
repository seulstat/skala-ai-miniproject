# 출처: skala-ai-agent/practice/scripts/check_inputs.py (Phase 0 복사 후 JSON 응답(ReadinessResponse)으로 이식)
"""준비 점검 (design §5 GET /api/readiness, §6 테스트 8). API 호출 없이 deps.paths의 파일만 본다.

필수 3개(프로필·경험 문서·공고)가 error면 ready=false이고, 개인정보는 항상 warn(차단하지 않는 안내)이다.
v1은 점검 줄마다 따로 냈지만, 체크리스트 화면에 맞춰 항목(프로필·경험 문서·공고·개인정보)당 한 줄로 묶는다.
"""

import asyncio
import re
from typing import Optional

from pydantic import ValidationError

from contracts.api import ReadinessItem, ReadinessResponse
from contracts.deps import DataPaths
from contracts.schemas import POSTING_SECTIONS, REQUIRED_POSTING_SECTIONS, UserProfile
from services.posting import missing_required, parse_sections

PII = {
    "전화번호": r"01[016-9]-?\d{3,4}-?\d{4}",
    "이메일": r"[\w.+-]+@[\w-]+\.[\w.]+",
    "주민등록번호": r"\d{6}-[1-4]\d{6}",
}
MIN_DOC_CHARS = 1000
PLACEHOLDER = "★"

Finding = tuple[str, str]   # (status, message)


def _row(item: str, findings: list[Finding], ok_message: str) -> ReadinessItem:
    """가장 심각한 상태 하나로 묶고, 그 상태의 메시지만 이어 붙인다 (error를 고치면 warn이 보인다)."""
    for status in ("error", "warn"):
        messages = [m for s, m in findings if s == status]
        if messages:
            return ReadinessItem(item=item, status=status, message=" · ".join(messages))
    return ReadinessItem(item=item, status="ok", message=ok_message)


def _read(path) -> Optional[str]:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None


def _pii_scan(name: str, text: str, found: list[str]) -> None:
    found.extend(f"{name}: {label}" for label, pattern in PII.items() if re.search(pattern, text))


def _check_profile(paths: DataPaths, pii: list[str]) -> ReadinessItem:
    text = _read(paths.profile)
    if text is None:
        return _row("프로필", [("error", "profile.json이 없어요 — 프로필을 저장해 주세요")], "")
    findings: list[Finding] = []
    ok_message = ""
    try:
        profile = UserProfile.model_validate_json(text)
        ok_message = f"{profile.target_role} / 자격증 {len(profile.certifications)}개"
    except ValidationError as e:
        first = e.errors()[0]
        where = ".".join(str(p) for p in first["loc"])
        findings.append(("error", f"형식 오류: {where + ': ' if where else ''}{first['msg']}"))
    if PLACEHOLDER in text:
        findings.append(("error", f"{PLACEHOLDER} 표시가 남아 있어요 — 내용으로 바꿔 주세요"))
    _pii_scan("profile.json", text, pii)
    return _row("프로필", findings, ok_message)


def _check_docs(paths: DataPaths, pii: list[str]) -> ReadinessItem:
    files = sorted(paths.docs_dir.glob("*.md")) if paths.docs_dir.exists() else []
    if not files:
        return _row("경험 문서", [("error", "경험 문서가 없어요 — .md 파일을 올려 주세요")], "")
    findings: list[Finding] = []
    total = heads = digits = 0
    for f in files:
        text = f.read_text(encoding="utf-8")
        total += len(text)
        heads += len(re.findall(r"^# ", text, re.M))
        digits += len(re.findall(r"\d", text))
        if PLACEHOLDER in text:
            findings.append(("error", f"{f.name}에 {PLACEHOLDER} 표시가 남아 있어요"))
        _pii_scan(f"docs/{f.name}", text, pii)
    if heads == 0:
        findings.append(("error", "`# 제목`이 없어요 — 제목 단위로 검색하니 활동마다 `# ` 제목을 붙여 주세요"))
    if total < MIN_DOC_CHARS:
        findings.append(("warn", "너무 짧아요 — 활동당 500자 이상 구체적으로 쓰면 결과가 좋아져요"))
    if digits < 10:
        findings.append(("warn", "숫자가 거의 없어요 — 카드는 여기 적힌 수치만 영어 표현에 써요"))
    return _row("경험 문서", findings, f"docs/ {len(files)}개 · 활동·문항 {heads}개 · {total:,}자")


def _check_posting(paths: DataPaths, pii: list[str]) -> ReadinessItem:
    text = _read(paths.job_posting)
    if text is None:
        return _row("공고", [("error", "job_posting.md가 없어요 — 공고를 정리해 저장해 주세요")], "")
    findings: list[Finding] = []
    sections = parse_sections(text)
    if PLACEHOLDER in text:
        findings.append(("error", f"{PLACEHOLDER} 표시가 남아 있어요"))
    missing = missing_required(sections)
    if missing:
        findings.append(("error", f"필수 섹션 없음: {', '.join(missing)} (`## 주요 업무` 형식)"))
    _pii_scan("job_posting.md", text, pii)
    absent = [s for s in POSTING_SECTIONS if s not in sections and s not in REQUIRED_POSTING_SECTIONS]
    ok_message = f"필수 섹션 {len(REQUIRED_POSTING_SECTIONS)}개 모두 있음" + (
        f" (없는 선택 섹션: {', '.join(absent)})" if absent else "")
    return _row("공고", findings, ok_message)


def _check_privacy(pii: list[str]) -> ReadinessItem:
    if pii:
        return ReadinessItem(item="개인정보", status="warn",
                             message=f"{' · '.join(pii)} 패턴이 있어요 — LLM으로 전송되니 지우는 것을 권장해요")
    return ReadinessItem(item="개인정보", status="warn",
                         message="전화번호·이메일 패턴은 없지만, 외부 LLM 사용 시 서류가 전송됩니다")


def check_readiness_sync(paths: DataPaths) -> ReadinessResponse:
    pii: list[str] = []
    items = [_check_profile(paths, pii), _check_docs(paths, pii), _check_posting(paths, pii)]
    items.append(_check_privacy(pii))
    return ReadinessResponse(ready=all(i.status != "error" for i in items), items=items)


async def check_readiness(paths: DataPaths) -> ReadinessResponse:
    """파일을 읽는 동기 점검을 스레드로 돌린다 (ADR-0005)."""
    return await asyncio.to_thread(check_readiness_sync, paths)
