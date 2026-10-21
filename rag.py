# 출처: skala-ai-agent/practice/dapdap/rag.py (Phase 0 복사 후 .config 의존을 DataPaths·EMBEDDING_MODEL로 교체, ADR-0003)
"""내 서류·표현집을 벡터 검색한다. MCP 서버 프로세스 안에서만 쓴다 (ADR-0003).

제목 단위 분할 → 임베딩 → 순수 Python 코사인 검색(문서 수십 개 규모, numpy 불필요). 검색할 때 파일 mtime이 바뀌었으면 다시 색인한다.
EMBEDDING_MODEL=fake면 네트워크 없는 해시 임베딩을 쓴다 (테스트·MOCK 개발용).
"""

import contextlib
import json
import math
import os
import threading
import zlib
from pathlib import Path
from typing import Callable, Optional

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

from contracts import mcp_spec
from contracts.deps import DataPaths

CHUNK_SIZE = 500
CHUNK_OVERLAP = 50
FAKE_DIM = 256
NO_EXPERIENCE = "경험 문서가 비어 있습니다. get_job_posting과 search_expression_bank의 근거로 작성하세요."
NO_BANK = "표현집이 비어 있습니다. search_my_experience와 get_job_posting의 근거로 작성하세요."


def split_by_heading(text: str) -> list[tuple[str, str]]:
    """'#'/'##' 제목 단위로 (제목, 본문) 묶음을 만든다. 활동별 맥락이 섞이지 않게 하기 위함.
    출처 라벨에 쓰는 제목은 '#' 제목(활동 이름)이고, '#'가 없는 문서만 '##' 제목을 쓴다 (계약 fixture의 라벨 형식)."""
    sections, h1, h2, buf = [], "", "", []

    def flush():
        if "".join(buf).strip():
            sections.append(((h1 or h2)[:40], "\n".join(buf).strip()))

    for line in text.splitlines():
        if line.startswith("# "):
            flush()
            h1, h2, buf = line[2:].strip(), "", []
        elif line.startswith("## "):
            flush()
            h2, buf = line[3:].strip(), []
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


def load_documents(docs_dir: Path) -> list[Document]:
    docs = []
    for path in sorted(docs_dir.glob("*.md")):
        for title, body in split_by_heading(path.read_text(encoding="utf-8")):
            for piece in split_fixed(body):
                docs.append(Document(page_content=piece, metadata={"file": path.name, "heading": title}))
    return docs


class FakeEmbeddings(Embeddings):
    """글자 1·2-gram 해시를 누적한 벡터. 겹치는 글자가 많을수록 코사인이 커져 테스트에서도 순위가 의미 있다 (hash() 대신 crc32: 프로세스마다 같은 값)."""

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vector(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vector(text)

    @staticmethod
    def _vector(text: str) -> list[float]:
        s, v = "".join(text.split()), [0.0] * FAKE_DIM
        for gram in [*s, *(a + b for a, b in zip(s, s[1:]))]:
            v[zlib.crc32(gram.encode()) % FAKE_DIM] += 1.0
        return v


def make_embeddings(name: str) -> Embeddings:
    """EMBEDDING_MODEL 값("provider:model", 예: ollama:nomic-embed-text)으로 임베딩을 만든다. "fake"는 네트워크 없음."""
    if name == "fake":
        return FakeEmbeddings()
    from langchain.embeddings import init_embeddings
    return init_embeddings(name)


def _read_cache(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):      # 없거나 깨진 캐시는 비운 채로 시작해 곧바로 새로 쓴다
        return {}


class VectorIndex:
    """임베딩 + 코사인 유사도 검색. 문서 임베딩은 (모델, 텍스트) 단위로 디스크에 캐시해 재색인 때 바뀐 문단만 다시 부른다."""

    def __init__(self, docs: list[Document], embedder: Embeddings, model: str, cache_path: Optional[Path]):
        self.docs, self._embedder = docs, embedder
        self.vectors = [self._norm(v) for v in self._embed_docs([d.page_content for d in docs], model, cache_path)]

    def _embed_docs(self, texts: list[str], model: str, cache_path: Optional[Path]) -> list[list[float]]:
        if cache_path is None:                       # fake는 계산이 싸서 캐시하지 않는다
            return self._embedder.embed_documents(texts) if texts else []
        cache, prefix = _read_cache(cache_path), model + "::"
        missing = list(dict.fromkeys(t for t in texts if prefix + t not in cache))
        if missing:
            for t, v in zip(missing, self._embedder.embed_documents(missing)):
                cache[prefix + t] = v
            tmp = cache_path.with_suffix(".tmp")      # 쓰다 죽어도 캐시가 깨지지 않게 교체 방식으로 저장
            tmp.write_text(json.dumps(cache), encoding="utf-8")
            os.replace(tmp, cache_path)
        return [cache[prefix + t] for t in texts]

    @staticmethod
    def _norm(v: list[float]) -> list[float]:
        n = math.sqrt(sum(x * x for x in v)) or 1.0
        return [x / n for x in v]

    def similarity_search(self, query: str, k: int = 3) -> list[Document]:
        if not self.docs:
            return []
        q = self._norm(self._embedder.embed_query(query))
        scored = sorted(zip(self.docs, self.vectors), key=lambda dv: -sum(a * b for a, b in zip(q, dv[1])))
        return [d for d, _ in scored[:k]]


def _signature(files: list[Path]) -> tuple:
    """색인이 낡았는지 보는 지문: (경로, mtime, 크기). 파일이 추가·삭제돼도 달라진다."""
    sig = []
    for p in files:
        with contextlib.suppress(FileNotFoundError):       # glob과 stat 사이에 지워진 파일은 없는 셈 친다
            st = p.stat()
            sig.append((str(p), st.st_mtime_ns, st.st_size))
    return tuple(sig)


class Retriever:
    """경험 문서·표현집 검색기. 결과는 mcp_spec.LABEL_* 형식 `[출처 라벨]`로 시작한다. 동기 메서드라 서버가 to_thread로 부르고 (ADR-0005), 색인은 락으로 직렬화해 중복 임베딩을 막는다."""

    def __init__(self, paths: DataPaths, embedder: Optional[Embeddings] = None, model: Optional[str] = None):
        self._paths = paths
        self._model = model or os.getenv("EMBEDDING_MODEL", "fake")
        self._embedder = embedder
        self._lock = threading.Lock()
        self._built: dict[str, tuple[tuple, VectorIndex]] = {}

    def _index(self, kind: str, files: list[Path], load: Callable[[], list[Document]]) -> VectorIndex:
        sig = _signature(files)
        with self._lock:
            hit = self._built.get(kind)
            if hit and hit[0] == sig:
                return hit[1]
            if self._embedder is None:               # 첫 검색 때 만든다 (키·모델이 없어도 서버 기동은 되도록)
                self._embedder = make_embeddings(self._model)
            cache = None if self._model == "fake" else self._paths.embed_cache
            index = VectorIndex(load(), self._embedder, self._model, cache)
            self._built[kind] = (sig, index)
            return index

    def search_experience(self, query: str, k: int = 3) -> str:
        docs_dir = self._paths.docs_dir
        index = self._index("experience", sorted(docs_dir.glob("*.md")), lambda: load_documents(docs_dir))
        hits = index.similarity_search(query, k=k)
        if not hits:
            return NO_EXPERIENCE
        return "\n\n".join(
            f"{mcp_spec.LABEL_EXPERIENCE.format(file=d.metadata['file'], heading=d.metadata['heading'] or '본문')}\n"
            f"{d.page_content}" for d in hits)

    def search_bank(self, query: str, k: int = 3) -> str:
        bank_path = self._paths.expression_bank         # 사용자 표현집이 없으면 templates 예시
        index = self._index("bank", [bank_path], lambda: [
            Document(page_content=f"{e['situation']} — {e['phrase']}", metadata=e)
            for e in json.loads(bank_path.read_text(encoding="utf-8"))["expressions"]])
        if not index.docs:
            return NO_BANK
        hits = index.similarity_search(query, k=k + 2)
        hits.sort(key=lambda d: not d.metadata.get("verified", False))       # verified 먼저
        return "\n".join(
            f"{mcp_spec.LABEL_BANK.format(id=d.metadata['id'], verified=str(d.metadata.get('verified', False)).lower())} "
            f"{d.metadata['situation']} — {d.metadata['phrase']}" for d in hits[:k])
