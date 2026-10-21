"""demo.ipynb 셀 정의 (eval/make_notebooks.py가 실행·저장). 실제 서버를 sample_user·gpt-4o-mini로 띄워 HTTP로 시연한다."""

INTRO = """# Interview Coach Agent — 실행 데모 (G1)

실제 서버(`server.py`)를 sample_user 데이터·`openai:gpt-4o-mini`로 띄우고, 브라우저가 쓰는 것과 같은 HTTP API로 E2E를 실행한 기록이다.
시나리오: ① 문장 표현 카드 → 새로고침 복원 → 승인·저장 ② 면접 질문 답변 ③ 복습 ④ 오류 처리(범위 밖·중복 승인·준비 미완료).
흐름 설명은 `doc/handoff/flow-guide.md`."""

START = """import json, os, shutil, sys, tempfile, httpx
from pathlib import Path
from dotenv import load_dotenv
os.environ["EVAL_PORT"] = "8140"
sys.path.insert(0, ".")
from eval.run_v2 import BASE, start_server
load_dotenv(".env")
work = Path(tempfile.mkdtemp(prefix="demo_")); data = work / "data"
shutil.copytree("examples/sample_user", data)
server = start_server(data, "openai:gpt-4o-mini")
c = httpx.Client(base_url=BASE, timeout=180)
print("서버:", BASE)
for item in c.get("/api/readiness").json()["items"]:
    print(f"  준비 점검 {item['item']}: {item['status']} — {item['message']}")"""

HELPERS = """LABEL = {"RouteDecided": "분류", "EvidenceSearched": "근거 검색", "CardDrafted": "초안", "ReviewDone": "검수",
         "ApprovalRequired": "승인 대기", "FinalAnswer": "답변", "ErrorRaised": "오류"}

def chat(message, thread_id):
    events = []
    with c.stream("GET", "/chat/stream", params={"message": message, "thread_id": thread_id}) as r:
        for line in r.iter_lines():
            if line.startswith("data: ") and line != "data: [DONE]":
                e = json.loads(line[6:]); events.append(e)
                detail = {"RouteDecided": e.get("intent"), "EvidenceSearched": f"{e.get('tool')} '{e.get('query')}'",
                          "CardDrafted": f"{e.get('attempt')}회차", "ReviewDone": f"{e.get('round')}라운드 통과={e.get('passed')} " + "; ".join(f"{v['rule_id']} '{v['quote'][:30]}'" for v in e.get("violations", [])),
                          "FinalAnswer": (e.get("reply") or "")[:120], "ErrorRaised": (e.get("error") or {}).get("code")}.get(e["type"], "")
                print(f"  [{LABEL[e['type']]}] {detail}")
    print("  [DONE]")
    return events

def show_card(ev):
    approval = next(e for e in ev if e["type"] == "ApprovalRequired"); card = approval["card"]
    if approval.get("warning"):
        print("  ⚠ 경고:", approval["warning"][:160])
    print(f"  Formal : {card['formal_expression']}\\n  Casual : {card['casual_expression']}")
    if card.get("answer_draft"):
        print(f"  답변 초안: {card['answer_draft']}")
    print("  핵심 표현:", ", ".join(ch["phrase"] for ch in card["chunks"]))
    print("  근거:", card["evidence"])"""

SCENARIO1 = """print("① 문장 표현"); ev = chat("배송 지연의 61%가 특정 택배사의 집하 구간에 몰려 있다는 걸 찾았어요", "demo-1")
show_card(ev)
print("\\n새로고침 → GET /chat/pending")
p = c.get("/chat/pending", params={"thread_id": "demo-1"}).json()
print("  승인 대기 복원:", p["pending"] is not None, "/", p["pending"]["card"]["formal_expression"][:70])
print("\\n승인 → POST /chat/resume:", c.post("/chat/resume", json={"thread_id": "demo-1", "approve": True}).json())"""

SCENARIO2 = """print("② 면접 질문 답변"); ev = chat("면접 질문: 분석 결과가 현업의 예상과 다를 때 어떻게 설득하겠습니까?", "demo-2")
show_card(ev)
print("\\n승인:", c.post("/chat/resume", json={"thread_id": "demo-2", "approve": True}).json())"""

SCENARIO3 = """print("③ 복습"); chat("오늘 복습할 카드 보여줘", "demo-3")
print("\\n카드함 GET /api/cards:")
for card in c.get("/api/cards").json():
    print(f"  {card['id']} 다음 복습 {card['next_review']} 단계 {card['stage']} — {card['korean_prompt'][:40]}")"""

ERRORS = """print("④-1 범위 밖 요청"); chat("오늘 점심 메뉴 추천해줘", "demo-4")
print("\\n④-2 이미 승인한 카드를 다시 승인 → 409")
r = c.post("/chat/resume", json={"thread_id": "demo-1", "approve": True}); print(" ", r.status_code, r.json()["error"]["code"], r.json()["error"]["user_message"])
print("\\n④-3 공고가 없을 때 질문 → SSE ErrorRaised(NOT_READY)")
(data / "job_posting.md").rename(work / "posting.bak")
chat("고객 이탈을 미리 예측하는 모델을 만들었어요", "demo-5")
(work / "posting.bak").rename(data / "job_posting.md")"""

STOP = """server.terminate(); server.wait(timeout=30); print("서버 종료")"""

CELLS = [("md", INTRO), ("code", START), ("code", HELPERS), ("code", SCENARIO1), ("code", SCENARIO2),
         ("code", SCENARIO3), ("code", ERRORS), ("code", STOP)]
