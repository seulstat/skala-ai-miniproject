# 출처: skala-ai-agent/practice/dapdap/config.py (Phase 0 복사, 로직 미변경)
"""경로, 모델 설정, 공용 헬퍼."""

import os
from functools import lru_cache
from pathlib import Path

from dotenv import find_dotenv, load_dotenv
from langchain.chat_models import init_chat_model

load_dotenv(find_dotenv(usecwd=True), override=True)

ROOT = Path(__file__).resolve().parents[1]          # practice/
DATA = ROOT / "data"
PRIVATE = DATA / "private"
TEMPLATES = ROOT / "templates"

# 사용자 데이터 폴더. 다른 사람의 정보로 쓰려면 DAPDAP_USER_DIR=/내/폴더 (구조는 README.md 참고)
USER_DIR = Path(os.getenv("DAPDAP_USER_DIR", PRIVATE)).expanduser().resolve()
DOCS_DIR = USER_DIR / "docs"                         # 내 경험 문서 (.md, 필수)
PROFILE_PATH = USER_DIR / "profile.json"             # 프로필 (필수)
BANK_PATH = USER_DIR / "expression_bank.json"        # 표현집 (선택)
CARDS_PATH = USER_DIR / "cards.json"                 # 저장한 복습 카드 (자동 생성)
EMBED_CACHE_PATH = USER_DIR / "embedding_cache.json"  # 임베딩 캐시 (자동 생성)

# 공고·페르소나 규칙은 사용자 폴더에 있으면 그것을, 없으면 기본값을 쓴다
PERSONA_RULES_PATH = (USER_DIR / "persona_rules.md") if (USER_DIR / "persona_rules.md").exists() \
    else TEMPLATES / "persona_rules.default.md"
JOB_POSTING_PATH = (USER_DIR / "job_posting.md") if (USER_DIR / "job_posting.md").exists() \
    else DATA / "job_posting.md"

# 모델 교체: DAPDAP_MODEL=openai:gpt-4o-mini
DEFAULT_MODEL = "google_genai:gemini-3.5-flash-lite"
# Gemini 임베딩 무료 등급은 분당 100건 한도라 평가 중 429가 나서 OpenAI를 기본으로 둔다.
# Gemini로 바꾸려면 DAPDAP_EMBEDDING=google_genai:models/gemini-embedding-001
DEFAULT_EMBEDDING = "openai:text-embedding-3-small"

MAX_RETRY = 2   # Reviewer 재시도 상한


def model_name() -> str:
    return os.getenv("DAPDAP_MODEL", DEFAULT_MODEL)


def embedding_name() -> str:
    return os.getenv("DAPDAP_EMBEDDING", DEFAULT_EMBEDDING)


def get_model(name: str | None = None):
    # 캐시 키를 실제 모델 이름으로 잡아야 DAPDAP_MODEL을 바꿨을 때 새 모델이 쓰인다
    return _cached_model(name or model_name())


@lru_cache(maxsize=4)
def _cached_model(name: str):
    # 무료 등급 분당 한도(429)에 대비해 재시도 횟수를 늘린다
    return init_chat_model(name, temperature=0.3, max_retries=6)


def text_of(message) -> str:
    """Gemini는 content를 list[dict]로, OpenAI는 str로 준다 — 둘 다 문자열로."""
    content = getattr(message, "content", message)
    if isinstance(content, str):
        return content
    return "".join(part.get("text", "") for part in content if isinstance(part, dict))
