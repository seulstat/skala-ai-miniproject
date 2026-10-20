# ref/ — 재사용 원본 참고용 복사본 (읽기 전용)

work-plan §3 표에서 "참고"로 표시된 파일을 원본 그대로 둔 곳이다. **수정하지 않는다** (Lead 소유, ruff 제외).
구현은 담당 경로에 새로 작성하고, 이 파일들은 로직을 옮겨 올 때 비교용으로만 읽는다.

| 파일 | 원본 | 참고하는 역할 · 대상 |
|---|---|---|
| v1/graph.py | practice/dapdap/graph.py | A1 · agent/coach_agent.py, reviewer_agent.py, graph.py |
| v1/tools.py | practice/dapdap/tools.py | A2 · mcp_server.py (검색 3종) / A1 · agent/store.py (save_card, get_due_cards) |
| v1/config.py | practice/dapdap/config.py | A1 · agent/llm.py (init_chat_model, text_of) / A2 · 경로 상수 |
| v1/check_inputs.py | practice/scripts/check_inputs.py | A3 · services/readiness.py |
| v1/ingest_posting.py | practice/scripts/ingest_posting.py | A3 · services/posting.py |
| base/server.py | all_total_vue_student/server.py | A3 · server.py (lifespan 싱글턴, LangSmith flush) |
| base/web_chat.html | all_total_vue_student/web_chat.html | A4 · web/ (SSE 파싱, STEP_LABELS, CSS) |
| base/web_demo_server.py | all_total_vue_student/web_demo_server.py | A4 · web_server.py (프록시) |

담당 경로에 직접 복사한 파일(contracts/schemas.py, agent/prompts.py, agent/retry.py, agent/mcp_client.py, rag.py, templates/, examples/sample_user/, eval/v1/)은 각 파일 첫 줄 또는 SOURCES.md에 출처가 있다.
