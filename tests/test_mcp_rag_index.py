"""A2 — rag.py 색인: 파일 mtime이 바뀌면 재색인, 안 바뀌면 재사용, (모델, 텍스트) 단위 디스크 임베딩 캐시.

임베딩 호출을 세는 fake 임베딩과 tmp_path(examples/sample_user 복사본)만 쓴다 (네트워크 없음).
"""

import json
import os
import shutil
from pathlib import Path

import pytest

from contracts.deps import DataPaths
from rag import FakeEmbeddings, Retriever

SAMPLE_USER = Path(__file__).resolve().parents[1] / "examples" / "sample_user"


class CountingEmbeddings(FakeEmbeddings):
    """embed_documents에 들어온 텍스트를 기록해 재색인 여부를 관찰한다."""

    def __init__(self):
        self.embedded: list[str] = []

    def embed_documents(self, texts):
        self.embedded.extend(texts)
        return super().embed_documents(texts)


@pytest.fixture
def paths(tmp_path) -> DataPaths:
    root = tmp_path / "user"
    shutil.copytree(SAMPLE_USER, root)
    return DataPaths(root)


def _bump_mtime(path: Path, seconds: int = 5) -> None:
    st = path.stat()
    os.utime(path, ns=(st.st_atime_ns, st.st_mtime_ns + seconds * 1_000_000_000))


# ---------- mtime 재색인 ----------

def test_index_is_reused_while_files_are_unchanged(paths):
    emb = CountingEmbeddings()
    r = Retriever(paths, embedder=emb, model="fake")
    r.search_experience("배송 지연")
    built = len(emb.embedded)
    assert built == 3                      # 샘플 섹션 3개를 한 번 임베딩
    r.search_experience("고객 이탈")
    r.search_experience("지원동기")
    assert len(emb.embedded) == built      # 파일이 그대로면 다시 임베딩하지 않는다


def test_reindexes_when_file_mtime_changes(paths):
    emb = CountingEmbeddings()
    r = Retriever(paths, embedder=emb, model="fake")
    r.search_experience("배송 지연")
    built = len(emb.embedded)

    _bump_mtime(paths.docs_dir / "experience.md")          # 내용은 그대로, mtime만 바뀜
    r.search_experience("배송 지연")
    assert len(emb.embedded) == 2 * built


def test_new_content_becomes_searchable_after_edit_and_removed_after_delete(paths):
    r = Retriever(paths, model="fake")
    assert "해커톤" not in r.search_experience("해커톤 우승 경험", k=5)

    doc = paths.docs_dir / "experience.md"
    doc.write_text(doc.read_text(encoding="utf-8") + "\n# 사내 해커톤\n## 활동내용\n해커톤에서 추천 알고리즘을 만들어 우승했습니다.\n",
                   encoding="utf-8")
    _bump_mtime(doc)
    result = r.search_experience("해커톤 우승 경험", k=1)
    assert result.startswith("[experience.md > 사내 해커톤]") and "우승" in result

    extra = paths.docs_dir / "portfolio.md"                # 파일 추가도 반영된다
    extra.write_text("# 대시보드 포트폴리오\n운영팀용 대시보드를 만들었습니다.\n", encoding="utf-8")
    assert "[portfolio.md > 대시보드 포트폴리오]" in r.search_experience("운영팀 대시보드", k=5)

    extra.unlink()                                          # 삭제도 반영된다
    assert "portfolio.md" not in r.search_experience("운영팀 대시보드", k=5)


def test_embedding_cache_skips_unchanged_chunks_after_restart(paths):
    """실제 임베딩 모델 이름이면 (모델, 텍스트) 단위로 디스크 캐시한다. 서버를 다시 띄워도 바뀐 문단만 임베딩한다."""
    first = CountingEmbeddings()
    Retriever(paths, embedder=first, model="ollama:test").search_experience("배송 지연")
    assert len(first.embedded) == 3 and paths.embed_cache.exists()

    second = CountingEmbeddings()
    Retriever(paths, embedder=second, model="ollama:test").search_experience("배송 지연")
    assert second.embedded == []                            # 전부 캐시 적중

    doc = paths.docs_dir / "experience.md"
    doc.write_text(doc.read_text(encoding="utf-8") + "\n# 새 활동\n새 활동 내용입니다.\n", encoding="utf-8")
    third = CountingEmbeddings()
    Retriever(paths, embedder=third, model="ollama:test").search_experience("새 활동")
    assert third.embedded == ["새 활동 내용입니다."]         # 새 문단만

    other_model = CountingEmbeddings()                       # 모델이 다르면 캐시를 공유하지 않는다
    Retriever(paths, embedder=other_model, model="ollama:other").search_experience("배송 지연")
    assert len(other_model.embedded) == 4


def test_corrupted_embedding_cache_is_rebuilt(paths):
    paths.embed_cache.write_text("{깨진 json", encoding="utf-8")
    emb = CountingEmbeddings()
    assert Retriever(paths, embedder=emb, model="ollama:test").search_experience("배송 지연")
    assert len(emb.embedded) == 3
    json.loads(paths.embed_cache.read_text(encoding="utf-8"))   # 다시 올바른 JSON으로 써졌다
