"""design §7 나머지 지표: 재시작 후 승인 대기 복원, 동시 2요청, MCP stdio 오버헤드, 체크포인트 DB 크기 (ADR-0009).

    .venv/bin/python eval/measure_extras.py          # OpenAI(gpt-4o-mini) 서버로 측정, 결과는 eval/results/extras.json
v1(10/13)은 InMemorySaver·동기 CLI라 재시작 복원은 구조상 0/N, 동시 처리는 순차뿐이다 (실측 대상 아님, 표에 근거와 함께 기록).
"""

import asyncio
import os
import shutil
import statistics
import sys
import tempfile
import time
from pathlib import Path

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from eval.common import load_cases, save  # noqa: E402
from eval.run_v2 import BASE, start_server, stream  # noqa: E402

MODEL = "openai:gpt-4o-mini"


async def restart_and_concurrency(work: Path) -> dict:
    data = work / "data"
    shutil.copytree(ROOT / "examples" / "sample_user", data)
    cases = [c for c in load_cases("test_cases_sample.json") if c["intent"] == "express"]
    proc = start_server(data, MODEL)
    out: dict = {}
    try:
        async with httpx.AsyncClient(timeout=600) as client:
            await stream(client, cases[0]["input"], "warmup")
            # 동시 2요청 vs 순차 2요청 (같은 입력 2개)
            pair = cases[1:3]
            t0 = time.time()
            for i, c in enumerate(pair):
                await stream(client, c["input"], f"seq-{i}")
            out["sequential_2_seconds"] = round(time.time() - t0, 1)
            t0 = time.time()
            await asyncio.gather(*(stream(client, c["input"], f"par-{i}") for i, c in enumerate(pair)))
            out["concurrent_2_seconds"] = round(time.time() - t0, 1)
            # 승인 대기 N개를 만든 뒤 서버 재시작
            pending_ids = [f"pend-{i}" for i in range(3)]
            for tid, c in zip(pending_ids, cases):
                await stream(client, c["input"], tid)
    finally:
        proc.terminate()
        proc.wait(timeout=30)
    db = data / "checkpoints.db"
    out["checkpoint_db_bytes"] = db.stat().st_size
    out["conversations"] = 1 + 2 + 2 + 3
    out["checkpoint_bytes_per_conversation"] = out["checkpoint_db_bytes"] // out["conversations"]
    proc = start_server(data, MODEL)
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            restored = [(await client.get(f"{BASE}/chat/pending", params={"thread_id": t})).json()["pending"]
                        for t in pending_ids]
    finally:
        proc.terminate()
        proc.wait(timeout=30)
    out["restart_restored"] = f"{sum(p is not None for p in restored)}/{len(pending_ids)}"
    return out


async def mcp_overhead(work: Path, n: int = 20) -> dict:
    """fake 임베딩으로 네트워크를 빼고, 같은 검색을 프로세스 안(rag.Retriever)과 MCP stdio 경유로 비교."""
    from agent.mcp_client import MCPClient
    from contracts import mcp_spec
    from contracts.deps import DataPaths
    from rag import Retriever

    data = work / "mcp_data"
    shutil.copytree(ROOT / "examples" / "sample_user", data)
    os.environ.update(COACH_DATA_DIR=str(data), EMBEDDING_MODEL="fake")
    retriever = Retriever(DataPaths(data))
    retriever.search_experience("워밍업")
    t0 = time.perf_counter()
    for i in range(n):
        retriever.search_experience(f"배송 지연 원인 {i}")
    direct_ms = (time.perf_counter() - t0) / n * 1000
    client = MCPClient(server_scripts={mcp_spec.SERVER_NAME: ROOT / "mcp_server.py"})
    await client.start()
    try:
        await client.call_tool(mcp_spec.TOOL_SEARCH_MY_EXPERIENCE, {"query": "워밍업"})
        samples = []
        for i in range(n):
            t0 = time.perf_counter()
            await client.call_tool(mcp_spec.TOOL_SEARCH_MY_EXPERIENCE, {"query": f"배송 지연 원인 {i}"})
            samples.append((time.perf_counter() - t0) * 1000)
    finally:
        await client.stop()
    return {"direct_ms": round(direct_ms, 2), "mcp_ms_median": round(statistics.median(samples), 2),
            "mcp_overhead_ms": round(statistics.median(samples) - direct_ms, 2), "calls": n}


async def main() -> None:
    load_dotenv(ROOT / ".env")
    work = Path(tempfile.mkdtemp(prefix="eval_extras_"))
    result = {"model": MODEL, **await restart_and_concurrency(work), **{"mcp": await mcp_overhead(work)}}
    print(save("extras.json", result))
    print(result)


if __name__ == "__main__":
    asyncio.run(main())
