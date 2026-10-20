# 출처: skala-ai-agent/practice/dapdap/rag.py (Phase 0 복사, 로직 미변경)
"""내 서류·표현집을 벡터 검색할 수 있게 만든다.

InMemoryVectorStore는 numpy를 요구해서, 문서 수십 개 규모에 맞춘 순수 Python 코사인 검색으로 대신한다.
"""

import json
import math
from functools import lru_cache

from langchain_core.documents import Document

from .config import (  # TODO(A2): COACH_DATA_DIR·EMBEDDING_MODEL 기반으로 교체
    BANK_PATH,
    DOCS_DIR,
    EMBED_CACHE_PATH,
    embedding_name,
)

CHUNK_SIZE = 500
CHUNK_OVERLAP = 50


def split_by_heading(text: str) -> list[tuple[str, str]]:
    """'#'/'##' 제목 단위로 (제목 경로, 본문) 묶음을 만든다. 활동별 맥락이 섞이지 않게 하기 위함."""
    sections, h1, h2, buf = [], "", "", []

    def flush():
        if "".join(buf).strip():
            title = " > ".join(x[:40] for x in (h1, h2) if x)
            sections.append((title, "\n".join(buf).strip()))

    for line in text.splitlines():
        if line.startswith("# "):
            flush(); h1, h2, buf = line[2:].strip(), "", []
        elif line.startswith("## "):
            flush(); h2, buf = line[3:].strip(), []
        else:
            buf.append(line)
    flush()
    return sections


def split_fixed(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """고정 길이 + overlap 분할 (RecursiveCharacterTextSplitter의 단순판)."""
    if len(text) <= size:
        return [text]
    chunks, start = [], 0
    while start < len(text):
        end = min(start + size, len(text))
        # 문장 중간에서 끊기지 않도록 마지막 줄바꿈/마침표로 당긴다
        cut = max(text.rfind("\n", start, end), text.rfind(". ", start, end), text.rfind("다. ", start, end))
        if end < len(text) and cut > start + size // 2:
            end = cut + 1
        chunks.append(text[start:end].strip())
        if end >= len(text):
            break
        start = end - overlap
    return chunks


def load_documents() -> list[Document]:
    docs = []
    for path in sorted(DOCS_DIR.glob("*.md")):
        for title, body in split_by_heading(path.read_text(encoding="utf-8")):
            for i, piece in enumerate(split_fixed(body)):
                source = f"{path.name} > {title}" if title else path.name
                docs.append(Document(page_content=piece, metadata={"source": source, "part": i}))
    return docs


@lru_cache(maxsize=1)
def embeddings():
    provider, model = embedding_name().split(":", 1)
    if provider == "openai":
        from langchain_openai import OpenAIEmbeddings
        return OpenAIEmbeddings(model=model)
    from langchain_google_genai import GoogleGenerativeAIEmbeddings
    return GoogleGenerativeAIEmbeddings(model=model)


def _load_cache() -> dict:
    if EMBED_CACHE_PATH.exists():
        return json.loads(EMBED_CACHE_PATH.read_text(encoding="utf-8"))
    return {}


def embed_texts(texts: list[str]) -> list[list[float]]:
    """문서 임베딩은 (모델, 텍스트) 단위로 디스크에 캐시해 실행할 때마다 다시 호출하지 않는다."""
    cache, prefix = _load_cache(), embedding_name() + "::"
    missing = [t for t in texts if prefix + t not in cache]
    if missing:
        for t, v in zip(missing, embeddings().embed_documents(missing)):
            cache[prefix + t] = v
        EMBED_CACHE_PATH.write_text(json.dumps(cache), encoding="utf-8")
    return [cache[prefix + t] for t in texts]


class SimpleVectorStore:
    """임베딩 + 코사인 유사도 검색 (similarity_search 인터페이스만 맞춤)."""

    def __init__(self, docs: list[Document]):
        self.docs = docs
        self.vectors = [self._norm(v) for v in embed_texts([d.page_content for d in docs])]

    @staticmethod
    def _norm(v: list[float]) -> list[float]:
        n = math.sqrt(sum(x * x for x in v)) or 1.0
        return [x / n for x in v]

    def similarity_search(self, query: str, k: int = 3) -> list[Document]:
        q = self._norm(embeddings().embed_query(query))
        scored = sorted(zip(self.docs, self.vectors), key=lambda dv: -sum(a * b for a, b in zip(q, dv[1])))
        return [d for d, _ in scored[:k]]


@lru_cache(maxsize=1)
def experience_store() -> SimpleVectorStore:
    return SimpleVectorStore(load_documents())


def load_bank() -> list[dict]:
    if not BANK_PATH.exists():          # 표현집은 선택 입력
        return []
    return json.loads(BANK_PATH.read_text(encoding="utf-8"))["expressions"]


@lru_cache(maxsize=1)
def bank_store() -> SimpleVectorStore:
    return SimpleVectorStore([
        Document(page_content=f"{e['situation']} — {e['phrase']}", metadata=e)
        for e in load_bank()
    ])
