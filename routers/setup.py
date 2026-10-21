"""/api/profile · /api/docs · /api/posting · /api/readiness (contracts.api, ADR-0007).

파일은 deps.paths(DataPaths)만 쓰고, 동기 파일 I/O는 asyncio.to_thread로 감싼다 (ADR-0005).
"""

import asyncio
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import ValidationError

from contracts.api import (
    DocInfo,
    DocUpload,
    OkResponse,
    PostingNormalizeRequest,
    PostingSaveRequest,
    ReadinessResponse,
)
from contracts.deps import DataPaths, Deps
from contracts.errors import CoachError
from contracts.schemas import PostingDraft, UserProfile
from routers.dependencies import get_deps
from services.posting import normalize_posting
from services.readiness import check_readiness

router = APIRouter(prefix="/api", tags=["setup"])


def _read_text(path: Path) -> Optional[str]:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None


def _write_text(path: Path, text: str) -> None:
    """임시 파일에 쓴 뒤 바꿔치기해서, 쓰는 도중 중단돼도 기존 파일이 깨지지 않게 한다."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def _doc_path(paths: DataPaths, name: str) -> Path:
    """문서 이름이 docs_dir 바깥을 가리키지 못하게 한다 (ADR-0007: 경로 구분자 불가, .md만)."""
    path = paths.docs_dir / name
    if (not re.fullmatch(r"[^/\\\x00]+\.md", name)
            or path.resolve().parent != paths.docs_dir.resolve()):
        raise CoachError("INPUT_INVALID", detail=f"허용되지 않는 문서 이름: {name!r}")
    return path


def _doc_info(path: Path) -> DocInfo:
    stat = path.stat()
    return DocInfo(name=path.name, chars=len(path.read_text(encoding="utf-8")),
                   updated=datetime.fromtimestamp(stat.st_mtime).astimezone().isoformat(timespec="seconds"))


def _list_docs(paths: DataPaths) -> list[DocInfo]:
    if not paths.docs_dir.exists():
        return []
    return [_doc_info(p) for p in sorted(paths.docs_dir.glob("*.md"))]


def _add_doc(paths: DataPaths, doc: DocUpload) -> DocInfo:
    path = _doc_path(paths, doc.name)
    _write_text(path, doc.content)
    return _doc_info(path)


def _delete_doc(paths: DataPaths, name: str) -> None:
    try:
        _doc_path(paths, name).unlink()
    except FileNotFoundError as e:
        raise CoachError("NOT_FOUND", detail=f"docs/{name} 없음") from e


@router.get("/profile", response_model=UserProfile)
async def get_profile(deps: Deps = Depends(get_deps)):
    text = await asyncio.to_thread(_read_text, deps.paths.profile)
    if text is None:
        raise CoachError("NOT_FOUND", detail="profile.json 없음")
    try:
        return UserProfile.model_validate_json(text)
    except ValidationError as e:
        raise CoachError("INPUT_INVALID", detail=f"profile.json 형식 오류: {e}") from e


@router.put("/profile", response_model=OkResponse)
async def put_profile(profile: UserProfile, deps: Deps = Depends(get_deps)):
    await asyncio.to_thread(_write_text, deps.paths.profile, profile.model_dump_json(indent=2) + "\n")
    return OkResponse()


@router.get("/docs", response_model=list[DocInfo])
async def list_docs(deps: Deps = Depends(get_deps)):
    return await asyncio.to_thread(_list_docs, deps.paths)


@router.post("/docs", response_model=DocInfo)
async def add_doc(doc: DocUpload, deps: Deps = Depends(get_deps)):
    return await asyncio.to_thread(_add_doc, deps.paths, doc)


@router.delete("/docs/{name}", response_model=OkResponse)
async def delete_doc(name: str, deps: Deps = Depends(get_deps)):
    await asyncio.to_thread(_delete_doc, deps.paths, name)
    return OkResponse()


@router.post("/posting/normalize", response_model=PostingDraft)
async def normalize(req: PostingNormalizeRequest, deps: Deps = Depends(get_deps)):
    return await normalize_posting(deps.quality_llm, req.text)


@router.put("/posting", response_model=OkResponse)
async def save_posting(req: PostingSaveRequest, deps: Deps = Depends(get_deps)):
    await asyncio.to_thread(_write_text, deps.paths.job_posting, req.markdown.rstrip() + "\n")
    return OkResponse()


@router.get("/readiness", response_model=ReadinessResponse)
async def readiness(deps: Deps = Depends(get_deps)):
    return await check_readiness(deps.paths)
