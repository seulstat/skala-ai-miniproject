# 출처: skala-ai-agent/practice/scripts/check_inputs.py (Phase 0 복사, 로직 미변경)
"""입력 폴더가 Agent를 돌릴 준비가 됐는지 점검한다 (API 호출 없음).

사용법: python scripts/check_inputs.py [내 폴더]      # 생략하면 DAPDAP_USER_DIR 또는 data/private
종료 코드: 오류(❌)가 있으면 1
"""

import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
if len(sys.argv) > 1:
    os.environ["DAPDAP_USER_DIR"] = sys.argv[1]

from dapdap import config  # noqa: E402
from dapdap.schemas import UserProfile  # noqa: E402

REQUIRED_SECTIONS = ["주요 업무", "자격 요건"]
OPTIONAL_SECTIONS = ["회사 소개", "우대 사항", "전형 절차", "영어 면접 안내"]
PII = {
    "전화번호": r"01[016-9]-?\d{3,4}-?\d{4}",
    "이메일": r"[\w.+-]+@[\w-]+\.[\w.]+",
    "주민등록번호": r"\d{6}-[1-4]\d{6}",
}

rows: list[tuple[str, str, str]] = []   # (상태, 항목, 설명)


def add(ok: str, item: str, msg: str) -> None:
    rows.append((ok, item, msg))


def pii_scan(name: str, text: str) -> None:
    for label, pat in PII.items():
        if re.search(pat, text):
            add("⚠️", name, f"{label}로 보이는 값이 있습니다 — LLM API로 전송되므로 지우는 것을 권장합니다")


def main() -> int:
    add("ℹ️", "폴더", str(config.USER_DIR))

    # 1) profile.json (필수)
    p = config.PROFILE_PATH
    if not p.exists():
        add("❌", "profile.json", "없습니다 — templates/profile.template.json 을 복사해 채우세요")
    else:
        text = p.read_text(encoding="utf-8")
        try:
            prof = UserProfile.model_validate_json(text)
            if "★" not in text:
                add("✅", "profile.json", f"{prof.target_role} / 자격증 {len(prof.certifications)}개")
        except Exception as e:
            add("❌", "profile.json", f"형식 오류: {str(e).splitlines()[0]} … {str(e).splitlines()[-2][:90]}")
        if "★" in text:
            add("❌", "profile.json", "★ 표시가 남아 있습니다 — 내용으로 바꾸세요")
        pii_scan("profile.json", text)

    # 2) docs/*.md (필수)
    files = sorted(config.DOCS_DIR.glob("*.md")) if config.DOCS_DIR.exists() else []
    if not files:
        add("❌", "docs/*.md", "내 경험 문서가 없습니다 — templates/experience.template.md 를 docs/ 에 복사해 채우세요")
    else:
        total, heads = 0, 0
        for f in files:
            t = f.read_text(encoding="utf-8")
            total += len(t)
            heads += len(re.findall(r"^# ", t, re.M))
            if "★" in t:
                add("❌", f"docs/{f.name}", "★ 표시가 남아 있습니다 — 내용으로 바꾸세요")
            pii_scan(f"docs/{f.name}", t)
        digits = sum(len(re.findall(r"\d", f.read_text(encoding="utf-8"))) for f in files)
        add("✅" if total >= 1000 else "⚠️", "docs/*.md",
            f"{len(files)}개 파일, 활동·문항 {heads}개, {total:,}자"
            + ("" if total >= 1000 else " — 너무 짧습니다. 활동당 500자 이상 구체적으로 쓰면 결과가 좋아집니다"))
        if digits < 10:
            add("⚠️", "docs 수치", "숫자가 거의 없습니다 — Agent는 여기 적힌 수치만 영어 표현에 씁니다")
        if heads == 0:
            add("❌", "docs 제목", "`# 제목` 이 없습니다 — 제목 단위로 검색하므로 활동마다 `# ` 제목을 붙이세요")

    # 3) job_posting.md (필수; 사용자 폴더에 없으면 데이터 폴더의 mock 공고가 쓰임)
    jp = config.JOB_POSTING_PATH
    where = "내 폴더" if jp.parent == config.USER_DIR else "기본 mock 공고(내 공고가 아님)"
    if not jp.exists():
        add("❌", "job_posting.md", "없습니다 — templates/job_posting.template.md 를 채우거나 ingest_posting.py 로 변환하세요")
    else:
        t = jp.read_text(encoding="utf-8")
        missing = [s for s in REQUIRED_SECTIONS if not re.search(rf"^## {s}\s*$", t, re.M)]
        absent = [s for s in OPTIONAL_SECTIONS if not re.search(rf"^## {s}\s*$", t, re.M)]
        if "★" in t:
            add("❌", "job_posting.md", "★ 표시가 남아 있습니다")
        if missing:
            add("❌", "job_posting.md", f"필수 섹션 없음: {', '.join(missing)} (`## 주요 업무` 형식)")
        else:
            add("✅" if where == "내 폴더" else "⚠️", "job_posting.md", f"{where} · 없는 선택 섹션: {', '.join(absent) or '없음'}")
        if "영어 면접 안내" in absent:
            add("ℹ️", "영어 면접 안내", "섹션이 없으면 Agent는 일반적인 면접 상황을 가정합니다")

    # 4) 선택 입력
    pr = config.USER_DIR / "persona_rules.md"
    add("✅" if pr.exists() else "ℹ️", "persona_rules.md", "내 규칙 사용" if pr.exists() else "(선택) 없어서 templates/persona_rules.default.md 기본 규칙을 씁니다")
    add("✅" if config.BANK_PATH.exists() else "ℹ️", "expression_bank.json", "사용" if config.BANK_PATH.exists() else "(선택) 없음 — 표현집 없이 동작합니다")

    # 5) API 키
    keys = {"GOOGLE_API_KEY": "Gemini(생성)", "OPENAI_API_KEY": "OpenAI(임베딩)"}
    for k, use in keys.items():
        add("✅" if os.getenv(k) else "❌", k, use + (" 설정됨" if os.getenv(k) else " — .env 에 키를 넣으세요"))

    width = max(len(r[1]) for r in rows)
    for ok, item, msg in rows:
        print(f"{ok}  {item:<{width}}  {msg}")
    errors = sum(r[0] == "❌" for r in rows)
    print(f"\n{'준비 완료 🎉' if not errors else f'오류 {errors}개를 고친 뒤 다시 실행하세요.'}"
          "  (입력 내용은 LLM API로 전송됩니다. 민감한 정보는 빼 주세요)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
