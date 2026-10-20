# 출처: skala-ai-agent/practice/scripts/ingest_posting.py (Phase 0 복사, 로직 미변경)
"""채용공고(URL / PDF / txt / md)를 Agent가 읽는 job_posting.md 형식으로 변환한다.

사용법: python scripts/ingest_posting.py <공고 URL 또는 파일> <내 폴더>
  - 이미 `## 주요 업무`·`## 자격 요건` 형식의 md 면 그대로 복사한다.
  - 그 외에는 LLM이 원문을 6개 섹션으로 재정리한다 (원문에 없는 내용은 지어내지 않도록 지시).
  - 로그인이 필요하거나 JavaScript로 그려지는 페이지는 본문을 못 읽을 수 있다 — 그때는 내용을 복사해 .txt 로 저장해 넘기면 된다.
결과를 열어 눈으로 한 번 확인하세요. LLM 재정리는 틀릴 수 있습니다.
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dapdap.config import get_model, text_of  # noqa: E402

MAX_CHARS = 15000
SECTIONS = ["회사 소개", "주요 업무", "자격 요건", "우대 사항", "전형 절차", "영어 면접 안내"]

PROMPT = """아래는 채용공고 원문입니다. 다음 형식의 마크다운으로 정리하세요.

# [채용공고] <회사명> — <직무명>

## 회사 소개
## 주요 업무
## 자격 요건
## 우대 사항
## 전형 절차
## 영어 면접 안내

규칙:
- 섹션 제목은 위 이름 그대로 `## ` 로 쓰세요.
- 원문에 있는 내용만 옮기세요. 없는 섹션은 "(공고에 명시 없음)" 한 줄만 쓰세요. 절대 지어내지 마세요.
- 영어 사용·해외 협업·어학 기준 관련 문장은 빠뜨리지 말고, 영어 면접이 언급되면 '영어 면접 안내'에 넣으세요.
- 마크다운 외 설명 문장은 출력하지 마세요.

[공고 원문]
"""


def read_source(src: str) -> str:
    if re.match(r"https?://", src):
        import requests
        from bs4 import BeautifulSoup
        resp = requests.get(src, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        return re.sub(r"\n{3,}", "\n\n", soup.get_text("\n")).strip()
    path = Path(src).expanduser()
    if path.suffix.lower() == ".pdf":
        from pypdf import PdfReader
        return "\n".join((page.extract_text() or "") for page in PdfReader(path).pages).strip()
    return path.read_text(encoding="utf-8")


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__)
        return 2
    src, out_dir = sys.argv[1], Path(sys.argv[2]).expanduser()
    try:
        raw = read_source(src)
    except ImportError as e:
        print(f"❌ 필요한 패키지가 없습니다: {e.name} — pip install {e.name}")
        return 1
    except Exception as e:     # 네트워크·파일 오류는 사용자가 바로 조치할 수 있게 한 줄로
        print(f"❌ 공고를 읽지 못했습니다: {type(e).__name__}: {str(e)[:150]}\n   링크가 열리지 않으면 내용을 복사해 .txt 로 저장한 뒤 그 파일을 넘기세요.")
        return 1
    if len(raw) < 200:
        print(f"❌ 본문을 거의 읽지 못했습니다({len(raw)}자). 로그인/JS 렌더링 페이지일 수 있습니다 — 내용을 복사해 .txt 로 저장한 뒤 다시 실행하세요.")
        return 1

    already = all(re.search(rf"^## {s}\s*$", raw, re.M) for s in ["주요 업무", "자격 요건"])
    if already:
        result, how = raw, "형식이 이미 맞아 그대로 복사"
    else:
        if len(raw) > MAX_CHARS:
            print(f"ℹ️ 원문이 길어 앞 {MAX_CHARS:,}자만 사용합니다 ({len(raw):,}자)")
        result, how = text_of(get_model().invoke(PROMPT + raw[:MAX_CHARS])).strip(), "LLM으로 재정리"
        result = re.sub(r"^```(?:markdown)?\n|\n```$", "", result)

    missing = [s for s in ["주요 업무", "자격 요건"] if not re.search(rf"^## {s}\s*$", result, re.M)]
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / "job_posting.md"
    out.write_text(result + "\n", encoding="utf-8")
    present = [s for s in SECTIONS if re.search(rf"^## {s}\s*$", result, re.M)]
    print(f"✅ {out}  ({how}, {len(result):,}자)\n   섹션: {', '.join(present)}")
    if missing:
        print(f"⚠️ 필수 섹션이 없습니다: {', '.join(missing)} — 파일을 열어 직접 보완하세요")
    print("👉 결과를 열어 원문과 다르지 않은지 확인하세요.")
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
