# agent.md — 역할 agent 공용 규칙

> 모든 역할 agent(A1~A4)는 착수 전에 **이 파일과 [doc/design.md](doc/design.md)**를 읽는다. 이 두 문서만으로 착수할 수 있어야 한다.
> 이 파일은 Lead만 수정한다. 작업 방식의 전체 배경은 [doc/work-plan.md](doc/work-plan.md)에 있다.

## 1. 프로젝트 요약

**Interview Coach Agent** — 내 경험 서류와 지원 공고를 근거로 영어 면접 표현·답변 카드를 만들고, 규칙 검수 후 **사용자가 웹에서 승인한 것만** 복습 카드로 저장하는 웹 서비스. SKALA AI 미니프로젝트, 마감 Day3(2026-10-22) 13:00.

10/13 CLI 버전("dapdap")을 Base 골격(FastAPI·SSE·Vue·MCP·DI·LangSmith) 위로 옮긴다.

```
브라우저(Vue) → web_server.py(:8600, 프록시) → server.py(:8100, FastAPI, lifespan에서 Deps 1회 조립)
  → LangGraph Supervisor: router → coach(서브그래프) → reviewer(서브그래프) ⟲최대 2회 재작성
                         → approve(interrupt) → save | rejected,   review_cards, out_of_scope
  → MCP 서버 "coach"(stdio): search_my_experience(RAG) · search_expression_bank · posting://{section} · persona_review_prompt
  → SQLite: checkpoints.db(AsyncSqliteSaver), coach.db(카드·복습 단계)
```

### 문서 위치

| 문서 | 내용 |
|---|---|
| [doc/design.md](doc/design.md) | **단일 기준**: 목표 G1~G7, 구조, 기술요소 대응, 화면, API·SSE, 테스트 11개, 범위, 일정 |
| [doc/work-plan.md](doc/work-plan.md) | 역할·소유권, 역할별 작업 지시서(§5), 분기점 CP0~CP4(§6), ADR 운영(§8) |
| [doc/adr/README.md](doc/adr/README.md) | ADR 색인 — **기각된 대안** 확인용 |
| `contracts/` | 역할 사이 계약 코드 (State·Deps·스키마·SSE 이벤트·API·MCP 이름·fixture) |
| `ref/` | 재사용 원본의 참고용 복사본 (읽기 전용, [ref/README.md](ref/README.md)) |
| `doc/handoff/<role>.md` | 역할별 인수인계 노트 |

## 2. 소유권 (수정 가능 경로)

| 역할 | 수정 가능 | 브랜치 / worktree |
|---|---|---|
| **Lead** | `contracts/`, `agent.md`, `check.sh`, `requirements.txt`, `pyproject.toml`, `.env.example`, `.gitignore`, `sh/`(단 `sh/smoke_*.sh` 제외), `ref/`, `examples/`, `tests/conftest.py`, `tests/test_contracts.py`, `doc/` 전체, `eval/`, `README.md` | `main` |
| **A1** 에이전트 코어 | `agent/`(단 `agent/mcp_client.py` 제외), `tests/test_core_*.py` | `feat/core` · `.worktrees/core` |
| **A2** MCP·RAG | `mcp_server.py`, `rag.py`, `agent/mcp_client.py`, `templates/`, `tests/test_mcp_*.py` | `feat/mcp` · `.worktrees/mcp` |
| **A3** API | `server.py`, `routers/`, `services/`, `tests/test_api_*.py`, `sh/smoke_*.sh` | `feat/api` · `.worktrees/api` |
| **A4** 프론트 | `web/`, `web_server.py` | `feat/web` · `.worktrees/web` |

- 모든 역할은 `doc/adr/NNNN-*.md` **새 파일**(Proposed)과 `doc/handoff/<role>.md`를 추가할 수 있다. 기존 ADR 수정·확정·색인 갱신은 Lead만 한다.
- `check.sh`가 브랜치 이름으로 역할을 판별해 `main` 대비 변경 경로를 검사한다. 허용 경로 밖을 고치면 실패한다.
- 남의 경로에 고칠 것이 보이면 직접 고치지 말고 인수인계 노트의 "요청" 칸이나 Lead 보고에 적는다.

## 3. 계약 (`contracts/`) — 읽기만 한다

| 파일 | 내용 | 주로 쓰는 역할 |
|---|---|---|
| `schemas.py` | UserProfile·ExpressionCard·Route·ReviewResult·Violation(10/13 그대로, 필드 설명이 곧 LLM 프롬프트) + Intent·PostingSection·SavedCard·ApprovalRequest·PostingDraft·REVIEW_INTERVALS_DAYS | 전원 |
| `state.py` | AgentState(JSON 직렬화 가능한 값만), ResumeValue, MAX_REWRITES=2, 노드 이름, INTENT_TO_NODE | A1 |
| `deps.py` | `Deps(fast_llm, quality_llm, mcp, store, checkpointer, paths)`, MCPPort·CardStore Protocol(async), DataPaths | A1·A2·A3 |
| `events.py` | SSE 이벤트 7종(`ErrorRaised` 포함), `to_sse`, `SSE_DONE`, `SSE_HEADERS`, `parse_event`, `is_valid_sequence` | A1·A3·A4 |
| `errors.py` | 오류 코드·계층·재시도 가능 여부·사용자 메시지(`ERROR_CATALOG`), `ErrorInfo`, `CoachError`·`ToolError`, 재시도 정책 `RETRY_*`, 로그 필드 `LOG_FIELDS` | 전원 |
| `api.py` | ROUTES 표, REST 요청·응답 모델 | A3·A4 |
| `mcp_spec.py` | MCP Tool·Resource·Prompt 이름·인자, 출처 라벨 형식, Agent 래퍼 Tool 이름 | A1·A2 |
| `fixtures/` | fake 카드·검수 결과·SSE 시퀀스·API 응답 JSON, `load()`·`load_model()` | A1(fake MCP)·A4(MOCK) |

- 계약이 부족하거나 틀렸으면 **고치지 말고** Lead에 요청하고 Proposed ADR을 쓴다. Lead가 계약·ADR을 고친 뒤 영향받는 역할에 알린다.
- 계약에 없는 필드·이벤트·경로를 만들어 쓰지 않는다.

## 4. 코딩 규칙

- **async**: 그래프 노드·라우터·MCP 호출·store 메서드는 모두 `async`이고, 호출은 `ainvoke`/`await`를 쓴다. 동기 `invoke`·블로킹 I/O를 이벤트 루프에서 호출하지 않는다. 동기 SQLite는 `asyncio.to_thread`로 감싼다 (ADR-0005).
- **DI**: 의존성은 `contracts.deps.Deps`로 받는다. 노드는 `functools.partial(node, deps=deps)`로 주입한다. 모듈 전역 싱글턴이나 import 시점의 모델·DB 생성은 금지한다. 조립은 `agent/deps.py`의 `build_deps()` 한 곳에서만 한다 (ADR-0011).
- **LLM**: LangChain `BaseChatModel`만 쓴다. `init_chat_model`로 만들고, 테스트에서는 `GenericFakeChatModel`을 쓴다. Base의 httpx LLM 클래스는 쓰지 않는다 (ADR-0001).
- **경로**: 데이터 경로는 `deps.paths`(DataPaths, `COACH_DATA_DIR`)만 쓴다. 하드코딩하지 않는다.
- **오류 처리** (ADR-0012): 오류는 `contracts.errors`의 코드로만 분류한다. `except Exception: pass`나 오류를 삼키는 기본 문구 금지. Tool 호출은 `asyncio.TimeoutError`만 `RETRY_*` 정책으로 재시도하고, 나머지는 `ToolError`/`CoachError`로 바꾼다. 치명 아닌 오류는 이벤트의 `error`·`notices`로 알리고 계속 진행한다. 화면에는 `user_message`만, 내부 원인은 로그(`LOG_FIELDS`)에만 남긴다.
- **파일 크기**: 파일당 약 200줄 이하. 넘으면 `check.sh`가 경고하니 모듈을 나눈다.
- **스타일**: 주변 코드의 주석 밀도·명명·관용구를 따른다. 주석·docstring·문서는 한국어로 쓴다. `ruff check` 통과(`pyproject.toml` 설정).
- **테스트**: fake 모델·fake MCP·`tmp_path`만 쓰고 네트워크를 쓰지 않는다. 파일 이름은 자기 역할 접두사(`test_core_*`, `test_mcp_*`, `test_api_*`)를 쓴다.
- **trace**: 노드·MCP 호출은 LangSmith `@traceable` 또는 LangGraph 기본 trace에 맡긴다. API 키가 없어도 동작해야 한다.
- **재사용 코드**: `ref/`의 원본 로직을 옮길 때는 파일 상단에 `# 출처: ...` 한 줄을 남긴다.

## 5. 실행 명령·환경변수

```bash
bash sh/setup_venv.sh            # .venv 생성 + requirements.txt 설치 (worktree마다 1회)
bash check.sh                    # 모든 점검. 작업 전·후 반드시 실행
.venv/bin/python -m pytest tests/test_core_*.py   # 자기 테스트만
bash sh/seed_sample.sh           # examples/sample_user → COACH_DATA_DIR (시연 데이터)
```

| 변수 | 용도 | 예 |
|---|---|---|
| `FAST_MODEL` | router (빠른 모델) | `ollama:qwen3:0.6b`, `openai:gpt-4o-mini`, `fake` |
| `QUALITY_MODEL` | Coach·Reviewer | `ollama:qwen3:8b`, `openai:gpt-4o-mini`, `fake` |
| `EMBEDDING_MODEL` | RAG 임베딩 (MCP 서버) | `ollama:nomic-embed-text`, `fake` |
| `COACH_DATA_DIR` | 사용자 데이터 폴더 | `./data` |
| `LANGSMITH_*` | trace | `.env.example` 참고 |

`fake`는 네트워크 없는 fake 모델·임베딩을 뜻한다. `.env`는 `.env.example`을 복사해 각자 만들고 커밋하지 않는다.

## 6. 금지 사항

1. 자기 담당 경로 밖의 파일 수정 (특히 `contracts/`, 다른 역할 파일, `ref/`)
2. 계약 변경, 계약에 없는 필드·이벤트·경로 사용
3. `.env`, `data/`, `*.db`, 실제 개인 서류 커밋. 시연·테스트에는 `examples/sample_user`만 쓴다
4. 기각된 ADR 대안으로 임의 회귀 (되돌리려면 새 근거를 담은 supersede ADR 필요)
5. 동기 `invoke`, 이벤트 루프 블로킹, 전역 싱글턴
6. 커밋 메시지에 Claude·AI 이름 표기 (`Co-Authored-By` 등 trailer 금지)
7. `git push`, remote 변경, `main` 브랜치 직접 커밋 (push는 CP 통과 후 Lead만)
8. `requirements.txt` 직접 수정 (라이브러리가 필요하면 Lead에 요청 + Proposed ADR)

## 7. 작업 전·후 체크리스트

**작업 전**
- [ ] `agent.md`, design.md, work-plan §5의 내 작업 지시서를 읽었다
- [ ] `doc/adr/README.md`에서 관련 ADR과 **기각된 대안**을 확인했다
- [ ] `git branch --show-current`가 내 브랜치이고, 내 worktree에서 작업한다
- [ ] `bash check.sh` 기준선이 통과한다 (실패하면 착수하지 않고 Lead에 보고)

**작업 중**
- [ ] ADR 트리거(§9)가 생기면 바로 Proposed ADR을 쓴다
- [ ] 계약을 바꿔야 하면 수정하지 않고 Lead에 요청한다

**작업 후**
- [ ] `bash check.sh` 통과 (출력 원문을 보고에 붙인다). WARN은 허용, FAIL은 0개여야 한다
- [ ] 자기 테스트 통과
- [ ] `doc/handoff/<role>.md` 작성 (§8 양식)
- [ ] 커밋 메시지에 관련 ADR 번호, AI 이름 없음
- [ ] Lead에 보고 (한 일 / check.sh 결과 / 요청 사항)

## 8. 인수인계 노트 양식 (`doc/handoff/<role>.md`)

파일 이름은 브랜치 접미사를 쓴다: `core.md`·`mcp.md`·`api.md`·`web.md` (Lead는 `lead.md`). `check.sh`는 자기 역할의 노트만 허용한다.

노트는 **무엇을·어디에**(구현 안내)를 쓴다. **왜**는 ADR에 쓰고, 노트에는 링크만 건다.

```markdown
# <역할> 인수인계 — <날짜> (CP<n>)
## 한 일
## 파일·함수 위치
| 파일 | 함수/클래스 | 역할 |
|---|---|---|
## 관련 ADR
## 사용한 계약 (contracts/)
## 테스트 결과 (check.sh, 자기 테스트)
## 알려진 한계·미완료
## Lead·다른 역할에 대한 요청
## 발표 때 설명할 포인트 (3줄)
```

## 9. ADR 규칙

- **위치**: `doc/adr/NNNN-<kebab-제목>.md`. 번호는 색인의 마지막 번호 + 1. 브랜치끼리 번호가 겹치면 CP 병합 때 Lead가 다시 매긴다.
- **고정 틀**: 메타(상태·날짜·작성·관련) → `## 배경` → `## 결정` → `## 대안 비교`(표, **기각한 대안 포함**) → `## 결과`(긍정·부정·후속 조치·검증 방법). `check.sh`가 네 제목이 모두 있는지 검사한다.
- **상태**: 역할 agent는 `Proposed`로만 쓴다. Accepted·Rejected·Superseded 확정과 색인 등록은 Lead가 CP에서 한다.
- **작성 트리거**: ① 계약 변경 요청 ② 라이브러리 추가·버전 변경 ③ design.md와 다르게 구현 ④ 대안 2개 이상 비교 후 선택 ⑤ 성능·보안·개인정보 영향 ⑥ 기존 ADR 번복

```markdown
# ADR-NNNN: <결정 제목>

- 상태: Proposed
- 날짜: YYYY-MM-DD
- 작성: <역할>
- 관련: design.md §<절>, supersedes ADR-XXXX (있으면)

## 배경
## 결정
## 대안 비교
| 대안 | 장점 | 단점 | 기각 이유 |
|---|---|---|---|
## 결과
- 긍정:
- 부정(트레이드오프):
- 후속 조치:
- 검증 방법:
```

## 10. 커밋 메시지 규칙

```
[role] 요약 (ADR-NNNN)
```

- `role`은 `lead`·`core`·`mcp`·`api`·`web` 중 하나.
- 관련 ADR이 없으면 괄호를 생략한다. 단 `contracts/`·`requirements.txt`를 바꾼 커밋은 ADR 번호가 **필수**다 (`check.sh`가 검사).
- 요약은 한국어 한 줄. 본문은 필요할 때만 쓴다.
- **Claude·AI 이름을 넣지 않는다.** `Co-Authored-By` 같은 trailer도 붙이지 않는다 (`check.sh`가 검사).
- 예: `[core] approve interrupt와 체크포인트 복원 구현 (ADR-0006)`

## 11. 분기점(CP)과 보고

| CP | 시점 | 통과 기준 (요약) |
|---|---|---|
| CP0 | Day1 19:30 | 계약·환경·ADR 0001~0011, worktree 4개 |
| CP1 | Day2 10:00 | A1+A2: 실제 MCP + fake LLM 그래프 E2E, 테스트 1~7·10 + MCP 테스트 |
| CP2 | Day2 13:00 | +A3: `sh/smoke_chat.sh` fake→ollama, 테스트 8·9·11, 재시작 후 pending 복원 |
| CP3 | Day2 20:00 | +A4: 브라우저 E2E(ollama), 새로고침 후 승인 대기 복원 |
| CP4 | Day3 11:30 | OpenAI E2E, Before/After·demo 노트북, README 캡처 |

Lead는 보고를 그대로 믿지 않고 해당 worktree에서 `check.sh`를 다시 실행하고, 노트와 실제 diff를 대조한다. CP를 통과하면 Lead가 `main`에 병합(core → mcp → api → web 순)하고 private 레포 `origin`에 push한다.
