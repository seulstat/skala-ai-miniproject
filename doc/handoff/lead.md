# Lead 인수인계 — 2026-10-20 (CP0)

## 한 일
Phase 0 — 역할 agent가 병렬로 착수할 수 있도록 공유 규칙·계약·환경·검사 도구·ADR을 만들었다. 구현 코드(그래프·MCP 서버·라우터·화면)는 만들지 않았고, 담당 파일은 docstring만 있는 skeleton이다.

1. 환경: git(main), 버전 고정 `requirements.txt`, `.env.example`, `pyproject.toml`(ruff·pytest), `sh/setup_venv.sh`·`sh/seed_sample.sh`
2. 재사용 코드: 1:1 대상은 담당 경로에 `cp`(출처 주석), "참고" 대상은 `ref/`에 원본 그대로
3. 계약: `contracts/` 6개 파일 + fixture 20개 + 계약 테스트 35개(스텁 그래프 스모크 포함)
4. 규칙: `agent.md`, 점검: `check.sh`(8개 항목)
5. ADR 0001~0011 + 색인, design.md 수정 2건
6. worktree 4개(`feat/core`·`feat/mcp`·`feat/api`·`feat/web`), 착수 프롬프트 초안

## 파일·함수 위치
| 파일 | 함수/클래스 | 역할 |
|---|---|---|
| `contracts/schemas.py` | `ExpressionCard`·`ReviewResult` 등(10/13) + `SavedCard`·`ApprovalRequest`·`PostingDraft`·`REVIEW_INTERVALS_DAYS` | 공용 데이터 모델. 10/13 모델의 필드 설명은 LLM 프롬프트 |
| `contracts/state.py` | `AgentState`, `ResumeValue`, `MAX_REWRITES`, `INTENT_TO_NODE` | 그래프 상태·노드 이름 |
| `contracts/deps.py` | `Deps`, `MCPPort`, `CardStore`, `DataPaths` | DI 컨테이너·포트·데이터 파일 배치 |
| `contracts/events.py` | 이벤트 6종, `to_sse`, `SSE_DONE`, `is_valid_sequence` | SSE 형식·순서 |
| `contracts/api.py` | `ROUTES`, 요청·응답 모델 | REST 경로·형식 |
| `contracts/mcp.py` | Tool·Resource·Prompt 상수, `SearchArgs`, 라벨 형식, `AGENT_TOOL_NAMES` | MCP 이름 고정 |
| `contracts/fixtures/__init__.py` | `load`, `load_model`, `FIXTURE_SCHEMAS` | fake 데이터 (A1 fake MCP, A4 MOCK) |
| `tests/test_contracts.py` | `test_stub_graph_streams_contract_events_and_resumes` | 계약만으로 만든 스텁 그래프: 이벤트 → interrupt → pending → resume |
| `check.sh` | ①~⑧ | ruff·pytest·계약·금지 패턴·소유권·길이·커밋 메시지·ADR |
| `agent.md` | §1~§11 | 역할 agent 공용 규칙 |
| `doc/handoff/kickoff-prompts.md` | A1·A2·A4 | 착수 프롬프트 |

## 관련 ADR
[0001](../adr/0001-langchain-llm-fast-quality.md) ~ [0011](../adr/0011-deps-in-contracts.md) 전부 ([색인](../adr/README.md)). Phase 0 고유 결정은 0010(역할·worktree·테스트 7 시점)과 0011(Deps 위치·`paths`).

## 사용한 계약 (contracts/)
계약을 만든 쪽이다. 핵심 흐름은 다음과 같다:
`/chat/stream` → 그래프 노드가 `get_stream_writer()`로 `contracts.events` 이벤트 전송 → approve에서 `interrupt(ApprovalRequest)` → `[DONE]` → 새로고침 시 `/chat/pending`이 `aget_state().interrupts[0].value` 반환 → `/chat/resume`이 `Command(resume=ResumeValue)`로 재개 → save가 `CardStore.save_card` → `ResumeResponse`

## 테스트 결과 (check.sh, 자기 테스트)
- main: `bash check.sh` FAIL 0 · WARN 0 (계약 테스트 35 passed)
- worktree 4개: 각각 `bash sh/setup_venv.sh && bash check.sh` 통과 (lead-progress.md에 기록)
- 위반 검출 확인: 임시 `feat/core`에서 `contracts/` 수정 → ⑤ FAIL, 필수 제목 없는 ADR → ⑧ FAIL

## 알려진 한계·미완료
- `agent/prompts.py`·`rag.py`는 10/13 `.config`를 import하는 복사본이라 아직 import 불가 (TODO 주석, A1·A2가 교체)
- `check.sh` ⑤는 `main...HEAD` 기준이라, main이 앞서 나가면 역할 브랜치는 CP 병합 전에 `git merge main`이 필요할 수 있다
- 이벤트 순서 검사(`is_valid_sequence`)는 오류 종료 `FinalAnswer`를 E·C·V 뒤에서도 허용한다. `error=True` 여부는 검사하지 않는다
- A3 착수 프롬프트는 CP1에서 작성한다

## Lead·다른 역할에 대한 요청
- 사용자: CP0 승인 후 각 worktree에서 착수 프롬프트로 A1·A2·A4 세션 시작, main을 `origin`에 첫 push 승인

## 발표 때 설명할 포인트 (3줄)
- 계약 우선: 역할 사이 접점을 `contracts/`에 코드로 고정하고, fixture로 백엔드 없이 프론트를 개발했다
- 점검은 스크립트로: 소유권·금지 패턴·커밋 규칙·ADR 형식을 `check.sh`가 기계적으로 판정한다
- 결정 기록: 설계 결정 11개를 기각한 대안과 함께 ADR로 남겨 회귀를 막았다
