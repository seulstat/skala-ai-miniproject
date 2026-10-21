"""A2 — rag.py: 제목 단위 분할, 출처 라벨, 코사인 검색, 표현집. fake 임베딩·tmp_path만 쓴다 (네트워크 없음). 재색인·캐시는 test_mcp_rag_index.py."""

import json
import os
import re
import shutil
from pathlib import Path

import pytest

from contracts import mcp_spec
from contracts.deps import DataPaths
from rag import FakeEmbeddings, Retriever, make_embeddings, split_by_heading, split_fixed

SAMPLE_USER = Path(__file__).resolve().parents[1] / "examples" / "sample_user"
LABEL_RE = re.compile(r"^\[experience\.md > (?P<heading>[^\]]+)\]$")


@pytest.fixture
def paths(tmp_path) -> DataPaths:
    """examples/sample_user를 tmp_path에 복사한 COACH_DATA_DIR (실제 data/는 건드리지 않는다)."""
    root = tmp_path / "user"
    shutil.copytree(SAMPLE_USER, root)
    return DataPaths(root)


def _bump_mtime(path: Path, seconds: int = 5) -> None:
    st = path.stat()
    os.utime(path, ns=(st.st_atime_ns, st.st_mtime_ns + seconds * 1_000_000_000))


def _blocks(result: str) -> list[str]:
    """검색 결과를 출처 라벨로 시작하는 블록으로 나눈다 (본문 안에도 빈 줄이 있어 `\\n\\n`만으로는 못 나눈다)."""
    return re.split(r"\n\n(?=\[)", result)


# ---------- 분할 ----------

def test_split_by_heading_uses_h1_as_label_and_splits_on_h2():
    text = "# 프로젝트 A\n## 활동내용\n내용 A\n## 결과\n결과 A\n# 프로젝트 B\n본문 B"
    assert split_by_heading(text) == [("프로젝트 A", "내용 A"), ("프로젝트 A", "결과 A"), ("프로젝트 B", "본문 B")]


def test_split_by_heading_falls_back_to_h2_without_h1_and_skips_empty_sections():
    assert split_by_heading("## 지원동기\n내용\n## 빈 섹션\n\n") == [("지원동기", "내용")]
    assert split_by_heading("제목 없는 메모") == [("", "제목 없는 메모")]


def test_split_fixed_keeps_short_text_and_overlaps_long_text():
    assert split_fixed("짧은 글") == ["짧은 글"]
    long = ". ".join(f"문장 {i} 입니다" for i in range(120))
    chunks = split_fixed(long, size=100, overlap=20)
    assert len(chunks) > 1 and all(len(c) <= 100 for c in chunks)


# ---------- 검색 결과·출처 라벨 ----------

def test_experience_search_results_start_with_source_label(paths):
    result = Retriever(paths, model="fake").search_experience("배송 지연 민원", k=2)
    blocks = _blocks(result)
    assert len(blocks) == 2
    for block in blocks:
        label, _, body = block.partition("\n")
        assert LABEL_RE.match(label) and body.strip()
    # 라벨은 계약 형식 LABEL_EXPERIENCE 그대로다
    assert blocks[0].startswith(mcp_spec.LABEL_EXPERIENCE.format(file="experience.md", heading="물류 스타트업 데이터 분석 인턴 (2개월)"))


@pytest.mark.parametrize("query, heading", [
    ("배송 지연 민원 택배사 집하", "물류 스타트업 데이터 분석 인턴 (2개월)"),
    ("고객 이탈 예측 모델 재현율 쿠폰", "고객 이탈 예측 졸업 프로젝트"),
    ("지원동기 해외 물류 파트너", "자기소개서"),
])
def test_experience_search_ranks_relevant_section_first(paths, query, heading):
    first = _blocks(Retriever(paths, model="fake").search_experience(query, k=3))[0]
    assert LABEL_RE.match(first.partition("\n")[0]).group("heading") == heading


def test_experience_search_respects_k(paths):
    r = Retriever(paths, model="fake")
    assert len(_blocks(r.search_experience("경험", k=1))) == 1
    assert len(_blocks(r.search_experience("경험", k=5))) == 3     # 샘플 문서의 섹션은 3개뿐


def test_experience_search_without_docs_returns_guidance(paths):
    for f in paths.docs_dir.glob("*.md"):
        f.unlink()
    assert Retriever(paths, model="fake").search_experience("아무거나").startswith("경험 문서가 비어 있습니다")


# ---------- 표현집 ----------

def test_bank_falls_back_to_template_and_uses_bank_label_format(paths):
    assert not (paths.root / "expression_bank.json").exists()
    result = Retriever(paths, model="fake").search_bank("의견이 다를 때", k=2)
    lines = result.splitlines()
    assert len(lines) == 2
    pattern = re.escape(mcp_spec.LABEL_BANK.format(id="@@", verified="@@")).replace("@@", r"[^,\]]+")
    assert all(re.match(rf"^{pattern} .+ — .+", line) for line in lines)
    assert lines[0].startswith("[E02, verified=false]")


def test_bank_puts_verified_expressions_first_and_reindexes_on_edit(paths):
    bank = paths.root / "expression_bank.json"
    entries = [
        {"id": "E01", "situation": "의견이 다를 때 협업", "phrase": "Let's compare our views.", "verified": False},
        {"id": "E02", "situation": "의견이 다를 때", "phrase": "I'd check their side first.", "verified": True},
        {"id": "E03", "situation": "전혀 다른 상황", "phrase": "Unrelated phrase.", "verified": False},
    ]
    bank.write_text(json.dumps({"expressions": entries}), encoding="utf-8")
    r = Retriever(paths, model="fake")
    assert r.search_bank("의견이 다를 때 협업", k=1).startswith("[E02, verified=true]")

    entries[1]["verified"] = False                          # 표현집을 고치면 다음 검색에 반영된다
    bank.write_text(json.dumps({"expressions": entries}), encoding="utf-8")
    _bump_mtime(bank)
    assert r.search_bank("의견이 다를 때 협업", k=1).startswith("[E01, verified=false]")


def test_empty_bank_returns_guidance(paths):
    (paths.root / "expression_bank.json").write_text('{"expressions": []}', encoding="utf-8")
    assert Retriever(paths, model="fake").search_bank("아무거나").startswith("표현집이 비어 있습니다")


# ---------- 임베딩 선택 ----------

def test_fake_embeddings_are_deterministic_and_overlap_based():
    fake = FakeEmbeddings()
    assert fake.embed_query("배송 지연") == fake.embed_query("배송 지연")
    assert make_embeddings("fake").embed_documents(["a"]) == fake.embed_documents(["a"])
    assert len(fake.embed_query("x")) == 256


def test_make_embeddings_accepts_provider_model_names_without_network():
    from langchain_core.embeddings import Embeddings
    assert isinstance(make_embeddings("ollama:nomic-embed-text"), Embeddings)   # 생성만 하고 호출은 안 한다
