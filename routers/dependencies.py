"""라우터에 Deps·graph를 주입하는 FastAPI 의존성 (ADR-0011). 전역 변수 대신 lifespan이 채운 app.state에서 꺼낸다."""

import asyncio
from collections import defaultdict

from fastapi import Request
from langgraph.graph.state import CompiledStateGraph

from contracts.deps import Deps


def get_deps(request: Request) -> Deps:
    return request.app.state.deps


def get_graph(request: Request) -> CompiledStateGraph:
    return request.app.state.graph


def get_thread_locks(request: Request) -> defaultdict[str, asyncio.Lock]:
    """thread_id별 락. 같은 승인 요청이 겹쳐 들어와도 한 번만 처리하게 한다 (단일 프로세스 전제, ADR-0008)."""
    return request.app.state.thread_locks
