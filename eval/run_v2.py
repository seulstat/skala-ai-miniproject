"""After(v2): 새 서버의 HTTP API로 측정한다 (자동 승인, ADR-0009). 지표 정의는 eval/common.py로 v1과 같다.

서버를 sample_user 복사본·지정 모델로 직접 띄우고(:8120), 테스트가 끝나면 끈다. v1과 같게 FAST·QUALITY 모두 같은 모델.
    .venv/bin/python eval/run_v2.py <테스트셋.json> [반복 번호] [모델]
"""

import asyncio
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agent.prompts import banned_hits  # noqa: E402
from agent.reviewer_agent import card_text  # noqa: E402
from eval.common import applicant_text, judge, load_cases, save, summarize  # noqa: E402

PORT = int(os.getenv("EVAL_PORT", "8120"))
BASE = f"http://127.0.0.1:{PORT}"
WARMUP = "그 프로젝트에서 무엇을 배웠는지 말하고 싶어요"


def start_server(data_dir: Path, model: str) -> subprocess.Popen:
    env = {**os.environ, "COACH_DATA_DIR": str(data_dir), "FAST_MODEL": model, "QUALITY_MODEL": model,
           "EMBEDDING_MODEL": os.getenv("EVAL_EMBEDDING", "openai:text-embedding-3-small")}
    log = open(data_dir.parent / "server.log", "w")
    proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "server:app", "--port", str(PORT)],
                            cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
    for _ in range(60):
        try:
            if httpx.get(f"{BASE}/api/readiness", timeout=2).status_code == 200:
                return proc
        except httpx.HTTPError:
            time.sleep(1)
    proc.terminate()
    raise RuntimeError("서버가 뜨지 않음 — server.log 확인")


async def stream(client: httpx.AsyncClient, message: str, thread_id: str) -> list[dict]:
    events = []
    async with client.stream("GET", f"{BASE}/chat/stream", params={"message": message, "thread_id": thread_id}) as r:
        async for line in r.aiter_lines():
            if line.startswith("data: ") and line != "data: [DONE]":
                events.append(json.loads(line[6:]))
    return events


async def run_case(client: httpx.AsyncClient, c: dict, tid: str) -> dict:
    row = {"id": c["id"], "input": c["input"], "expected": c["intent"]}
    t0 = time.time()
    ev = await stream(client, c["input"], tid)
    by_type = lambda t: [e for e in ev if e["type"] == t]  # noqa: E731
    route, approval, error = by_type("RouteDecided"), by_type("ApprovalRequired"), by_type("ErrorRaised")
    row.update(intent=route[0]["intent"] if route else None,
               tools=[e["tool"] for e in by_type("EvidenceSearched")],
               rewrites=max([e["attempt"] for e in by_type("CardDrafted")], default=1) - 1,
               notices=[n["code"] for e in approval for n in e.get("notices", [])])
    if error:
        row["error"] = error[0]["error"]["code"]
    if approval:
        card = approval[0]["card"]
        row.update(card=card, structured_ok=True, warning=approval[0].get("warning"),
                   banned=banned_hits(card_text(card)))
        await client.post(f"{BASE}/chat/resume", json={"thread_id": tid, "approve": True})
    row["seconds"] = round(time.time() - t0, 1)
    return row


async def main(cases_file: str, rep: str, model: str) -> None:
    load_dotenv(ROOT / ".env")   # 심판(OpenAI) 키. 서버 subprocess도 이 환경을 물려받는다
    work = Path(tempfile.mkdtemp(prefix="eval_v2_"))
    data = work / "data"
    shutil.copytree(ROOT / "examples" / "sample_user", data)
    applicant = applicant_text(data)
    proc = start_server(data, model)
    rows = []
    try:
        async with httpx.AsyncClient(timeout=600) as client:
            await stream(client, WARMUP, f"v2-{rep}-warmup")   # 첫 요청의 색인 준비 시간은 지표에서 뺀다 (v1과 동일)
            for c in load_cases(cases_file):
                row = await run_case(client, c, f"v2-{rep}-{c['id']}")
                if row.get("card"):
                    row["judge"] = await judge(row["card"], applicant)
                print(f"{c['id']} {row.get('intent')} {row['seconds']}s err={row.get('error', '')}", flush=True)
                rows.append(row)
    finally:
        proc.terminate()
        proc.wait(timeout=30)
    summary = summarize(rows)
    safe = model.replace(":", "_").replace("/", "_")
    print(save(f"v2_{Path(cases_file).stem}_{safe}_r{rep}.json",
               {"version": "v2", "model": model, "summary": summary, "rows": rows}))
    print(summary)


if __name__ == "__main__":
    a = sys.argv[1:]
    asyncio.run(main(a[0], a[1] if len(a) > 1 else "1", a[2] if len(a) > 2 else "openai:gpt-4o-mini"))
