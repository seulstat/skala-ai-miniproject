# ADR-0005: 모든 그래프 노드를 async로

- 상태: Accepted
- 날짜: 2026-10-20
- 작성: Lead
- 관련: design.md §2 "비동기", contracts/deps.py (MCPPort·CardStore가 async)

## 배경
Base 골격에서 동기 LLM 호출이 FastAPI 이벤트 루프를 막아, 한 요청이 처리되는 동안 SSE·다른 요청이 멈추는 문제가 있었다.
이번에는 SSE 스트림, MCP stdio 호출, SQLite 체크포인터가 한 프로세스 안에서 동시에 돈다.

## 결정
그래프 노드·MCP 호출·카드 store 메서드는 모두 `async`로 만들고 `ainvoke`/`astream`/`await`로 호출한다.
체크포인터는 `AsyncSqliteSaver`를 쓴다. 동기 라이브러리를 써야 하면 `asyncio.to_thread`로 감싼다.

## 대안 비교
| 대안 | 장점 | 단점 | 기각 이유 |
|---|---|---|---|
| 동기 노드 + FastAPI 스레드풀(`def` 엔드포인트) | 10/13 코드 그대로 | 스트리밍·MCP 비동기 세션과 섞기 어려움, 스레드 수만큼만 병행 | Base에서 겪은 블로킹 재발 위험 |
| 동기 노드 + `run_in_executor` 래핑 | 부분 적용 가능 | 노드마다 래핑, 누락 시 블로킹 | 규칙으로 강제하기 어려움 |

## 결과
- 긍정: 동시 요청이 병행 처리된다(design §7 "동시 2요청" 지표). MCP·SQLite I/O 대기 중에도 SSE가 흐른다.
- 부정(트레이드오프): 10/13 동기 코드를 옮길 때 수정이 필요하다. 테스트가 `pytest-asyncio`에 의존한다.
- 후속 조치: `ruff`의 ASYNC 규칙을 켠다(pyproject.toml). 코드 리뷰에서 동기 `invoke` 사용을 막는다(agent.md §6).
- 검증 방법: ruff ASYNC 통과, design §7 동시 2요청 총 처리 시간 측정.
