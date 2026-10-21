# Lead 진행 기록 — Phase 0

## 사용률 기록 (사용자가 알려 준 값만 기록)

| 시각 | 시점 | 5시간 창 사용률 | 비고 |
|---|---|---|---|
| 16:37 | Phase 0 시작 (기준선) | 16% | 현재 창 재설정 19:50 (사용자 확인) |
| ~17:05 | M1 완료 | 19% | M1 구간 +3%p → Phase 0 전체 예상 3 ÷ 0.20 = 15%p (종료 예상 약 31%, 예산 40%p 이내) |
| ~17:25 | M2 완료 | 23% | M2 +4%p (비중 25% 대비 예상 3.75%p, 정상) |
| ~17:35 | M3 완료 | 24% | M3 +1%p |
| ~17:50 | M4 완료 | 25% | M4 +1%p (누적 +9%p) |
| ~18:05 | M5 완료 | 27% | M5 +2%p (누적 +11%p) |
| ~18:25 | M6 완료 (CP0 보고) | 29% | M6 +2%p, Phase 0 합계 +13%p (예산 40%p의 약 1/3) |
| — | CP0 리뷰 반영 (ADR-0012 등) | 측정 불가 | 같은 구간에 사용자의 강의자료 PDF→MD 변환 작업이 섞여 증가분을 분리할 수 없음 |
| 19:50 이후 | 5시간 창 재설정 | 0% | 새 창 기준선. 병렬 단계 예산은 이 값부터 계산 |
| 10/21 A1 2차 검증 후 | A1 구현·재작업 + Lead 검증 | 19% | 새 창 기준 누적. A1 세션(Sonnet) 사용량 포함 |
| 10/21 A1 최종 수정 후 | A1 3차 수정 + CP1 1단계 병합 | 22% | |
| 10/21 A2 완료 후 | A2 구현(세션 다운·재개 포함) + A4 진행 중 | 47% | 세션 2개 병행으로 증가폭 큼 |
| 10/21 10:28 | A4 완료, CP1 리뷰 게이트 | 51% | 창 재설정 14:00 (사용자 확인) |
| 10/21 11:24 | A3 완료 | 68% | **소프트 한도 근접 → A3 1차 검증 후 정지**, 14:00 재설정 뒤 재개 |

## 마일스톤 상태

| M | 내용 | 상태 | 커밋 |
|---|---|---|---|
| M1 | 환경·복사·design 수정 | 완료 | `[lead] Phase 0 M1 ...` |
| M2 | contracts/ | 완료 | `[lead] Phase 0 M2 ...` |
| M3 | agent.md | 완료 | `[lead] Phase 0 M3 ...` |
| M4 | check.sh | 완료 | `[lead] Phase 0 M4 ...` |
| M5 | ADR 0001~0011 | 완료 | `[lead] Phase 0 M5 ...` |
| M6 | worktree·검증·인수인계 | 완료 | `[lead] Phase 0 M6 ...` |

## 사용자 지시 (상시)
- GitHub private 레포 `seulstat/skala-ai-miniproject`(이 폴더만) 생성·remote `origin` 연결 완료. **분기점(CP0~CP4)마다 main을 push** (첫 push는 CP0 승인 시점)
- 커밋 메시지에 Claude·AI 이름을 넣지 않는다 (`Co-Authored-By` trailer 금지). M1 커밋에서 제거함(amend). work-plan §3·§4에 반영, agent.md·check.sh에도 반영 예정

## 한도 판단 기준
- 소프트 한도: 사용률 70% 또는 경과 3시간(16:37 시작 → 19:37)
- 19:50에 창이 재설정되므로, 19:37 이후 작업은 새 창 기준으로 다시 사용률을 받아 판단

## M1 완료 항목
- `git init`(main), `.gitignore`, `requirements.txt`(버전 고정, 10/13·Base venv에서 검증된 버전 + `aiosqlite` 명시), `.env.example`, `pyproject.toml`(ruff·pytest 설정)
- `sh/setup_venv.sh`(uv 우선, 없으면 venv+pip), `sh/seed_sample.sh`(examples → COACH_DATA_DIR, 덮어쓰기 안 함)
- 재사용 코드 `cp` 복사 + 출처 주석: `contracts/schemas.py`, `agent/prompts.py`, `agent/retry.py`, `agent/mcp_client.py`, `rag.py`, `templates/`, `examples/sample_user/`, `eval/v1/`
- 참고용 원본은 `ref/v1/`, `ref/base/`에 원본 그대로 (ruff 제외, 읽기 전용, `ref/README.md`)
- import 경로 조정: `agent/prompts.py`의 schemas → `contracts.schemas`. `.config` 의존은 TODO(A1)/TODO(A2) 주석만 달고 그대로 둠 (config는 각 역할이 대체)
- 역할 담당 파일은 docstring만 있는 skeleton
- design.md 수정 2건: Deps 정의 위치(§2 구조도·핵심 결정 표·§3 DI 행), 테스트 7을 CP1(Day2 오전)로(§9). 상단에 변경 이력
- work-plan.md 동기화: ADR 0011 추가, Lead 소유 경로에 `pyproject.toml`·`ref/`·`examples/` 명시, `sh/smoke_*.sh`는 A3

## M2 완료 항목
- `contracts/schemas.py`: 10/13 모델 유지 + Intent·PostingSection·REVIEW_INTERVALS_DAYS·ReviewOutcome·SavedCard·ApprovalRequest·PostingDraft. evidence 예시를 sample_user 라벨로 교체(실제 경력 노출 방지)
- `contracts/state.py`: AgentState(JSON 직렬화 가능한 기본형), ResumeValue, MAX_REWRITES=2, 노드 이름·INTENT_TO_NODE
- `contracts/deps.py`: Deps(fast_llm, quality_llm, mcp, store, checkpointer, **paths**), MCPPort·CardStore Protocol(async), DataPaths(COACH_DATA_DIR 배치)
- `contracts/events.py`: SSE 이벤트 6종 + `[DONE]`, to_sse/parse_event/is_valid_sequence. 오류는 FinalAnswer(error=True)
- `contracts/api.py`: ROUTES 표, 요청·응답 모델
- `contracts/mcp.py`: Tool 2·Resource 1·Prompt 1 이름·인자, 출처 라벨 형식, Agent 래퍼 Tool 이름 3개
- `contracts/fixtures/` 20개 + loader, `tests/conftest.py`, `tests/test_contracts.py` (34 passed)
- design §3 DI 행에 `paths` 추가

## 남은 항목
- M3~M6 (위 표)

## M3 완료 항목
- `agent.md`: 요약·문서 위치 / 소유권표 / 계약 안내 / 코딩 규칙 / 실행·환경변수 / 금지 8개 / 작업 전·후 체크리스트 / 인수인계 양식("요청" 칸 추가) / ADR 규칙·템플릿 / 커밋 규칙(AI 이름 금지) / CP 표·push 절차
- work-plan §6 공통 절차에 CP 통과 후 push 추가

## M4 완료 항목
- `check.sh` 8개 항목: ① ruff ② pytest(계약 제외, 수집 0개=통과) ③ 계약 테스트 ④ 금지 파일(.env·data/·*.db·private/)·PII 정규식·`.forbidden_patterns.local` 고유명사 ⑤ 소유권(브랜치→역할, main...HEAD + 작업 트리 + 새 파일, 새 ADR 파일은 전원 허용) ⑥ 200줄 경고 ⑦ 커밋 메시지 형식·AI 표기 금지 ⑧ ADR(필수 제목·색인·계약 변경 커밋의 ADR 번호, 현재 비활성)
- 임시 브랜치 feat/core로 소유권 위반 검출 확인 (contracts 수정 FAIL, agent/ 수정·새 ADR 허용) 후 브랜치 삭제
- `.forbidden_patterns.local`은 사용자가 로컬에 직접 작성 필요 (Lead는 private 서류를 읽지 않음)

## M5 완료 항목
- ADR 0001~0011 전부 전체 틀(배경·결정·대안 비교·결과, 기각 대안 포함)로 작성, 상태 Accepted
- `doc/adr/README.md` 색인 + design.md ↔ ADR 대응표
- check.sh `ADR_CHECK_ENABLED=1`, 통과(FAIL 0·WARN 0). 필수 제목 누락 ADR로 FAIL 검출 확인

## M6 완료 항목
- fake 스모크: `tests/test_contracts.py::test_stub_graph_streams_contract_events_and_resumes` (GenericFakeChatModel router → 계약 이벤트 → AsyncSqliteSaver → interrupt payload 조회 → resume 승인)
- worktree 4개 `.worktrees/{core,mcp,api,web}` (`feat/*`), 각각 setup_venv + check.sh FAIL 0 · WARN 0
- check.sh: worktree에서는 main 작업 트리의 `.forbidden_patterns.local`을 사용
- `doc/handoff/lead.md`(부록 A 양식), `doc/handoff/kickoff-prompts.md`(A1·A2·A4)

## 마일스톤별 사용률 요약 (병렬 단계 예산 계획용)
| 구간 | 증가 | 비고 |
|---|---|---|
| M1 환경·복사·design | +3%p | 원본 탐색 포함 |
| M2 contracts | +4%p | 가장 큼 (설계 판단 + fixture 생성) |
| M3 agent.md | +1%p | |
| M4 check.sh | +1%p | |
| M5 ADR 11개 | +2%p | 전부 전체 틀 |
| M6 worktree·검증·인수인계 | +2%p | |
| Phase 0 합계 | +13%p (16% → 29%) | M1 외삽 15%p와 거의 일치 |

## CP0 리뷰 반영 (사용자 승인 3건)
- 강의자료(AI캠퍼스_AI_Capstone_20261016.md) 대조 → 오류 처리 4계층(`contracts/errors.py`, `ErrorRaised`, `EvidenceSearched.error`, `notices`, `ErrorResponse`), ADR-0012(0006 일부 대체)
- `contracts/mcp.py` → `contracts/mcp_spec.py` (강의 p.222 라이브러리 이름 가림 방지)
- SSE_HEADERS(p.114), Resource 캐시 금지·docstring 품질(p.47·p.45), ADR-0002(MultiServerMCPClient 기각 근거)·0006(PostgreSQL 대안, HITL 위치)·0009(LangSmith 혼합 평가) 보강
- design §2·§5·§6(테스트 11개)·§7·§9, work-plan §5·§6, agent.md, kickoff-prompts, lead.md 갱신. fixture 24개, 계약 테스트 43개

## A1 1차 검증 (2026-10-21, feat/core `70ff199`)
- Lead가 core worktree에서 check.sh 재실행: FAIL 0 · WARN 1(색인 미등록 ADR, 예상됨). 테스트 core 17 + 계약 43 통과, 소유권 위반 없음, 계약 미변경
- **check.sh ⑥ 버그 수정**(A1 발견): `$n줄`이 set -u에서 unbound로 죽고 pipefail로 조용히 PASS → `${n}줄`. agent/graph.py 206줄 경고가 이제 나온다
- Proposed ADR 판정 (CP1 병합 때 상태·색인 확정):
  - 0013 fake 모델 bind_tools → **Accept**
  - 0014 중첩 서브그래프 writer 명시 전달 → **Accept**
  - 0015 Reviewer가 MCP Prompt 대신 paths → **Reject**. 원인은 Lead 지시서 문구("deps.paths 기반")와 ADR-0004의 충돌 — 지시서를 고침. Reviewer는 `deps.mcp.get_prompt(persona_review_prompt)`로 규칙을 받고, A2 서버는 `agent.prompts.reviewer_prompt(rules)`로 렌더링
- A1 재작업 요청: Reviewer MCP Prompt 전환 + 테스트, graph.py 200줄 이하 분리, main merge

## CP1 1단계 (2026-10-21)
- A1 3차 검증 통과(`64245b2`: Reviewer가 get_prompt 반환값을 그대로 system으로, 테스트 `==` 검증). feat/core → main 선병합(`8e56130`), check.sh FAIL 0 · WARN 0, 테스트 core 20 + 계약 43
- ADR 0013·0014 Accepted, 0015 Rejected(Lead 판정 절 추가), 색인 등록
- A2 지시서에 `_build_mcp` 호출 형태 호환 조건 추가

## CP1 2단계 (2026-10-21)
- A2 검증: feat/mcp check.sh FAIL 0 · WARN 0, mcp 테스트 52(+core 20), 계약 미변경, Proposed ADR 없음. Lock 제거(동시 호출 허용)·ToolError(tool_name) 인자 판단 수용
- feat/mcp → main 병합(`a4fa27e`). `tests/test_integration_cp1.py`(Lead): 실제 MCP 서버 subprocess + fake LLM 그래프 E2E 통과 — Tool·Resource·Prompt 응답 형식, 이벤트 순서, 승인 대기, resume → 저장
- 통합 수정(Lead): agent/tools.py `k`를 1~5로 보정(A2 요청 2, 10/13과 동일), pyproject의 rag.py E702 예외 제거(A2 요청 1), Lead 소유 경로에 `tests/test_integration_*.py` 추가
- A3 착수 프롬프트 작성 (kickoff-prompts.md)
- 남은 A2 요청: 실제 임베딩(nomic-embed-text) 검색 스모크는 CP2에서

## A4 검증 (2026-10-21, feat/web `6f7aff1`)
- check.sh FAIL 0 · WARN 1(ADR-0016 색인 미등록), MOCK 화면 캡처 10장, 계약 미변경
- ADR-0016 4건 수용 → main 계약 반영: api.py 성공 응답 본문·프로필 404 명시, `BACKEND_UNAVAILABLE` 오류 코드 추가, sse fixture의 `FinalAnswer.error` 잔재 제거. A4 테스트 경로 `tests/test_web_*.py` 허용(check.sh·agent.md)
- feat/web 병합은 CP3(병합 순서 core→mcp→api→web). CP3 때 A4 후속: 프록시 연결 불가를 `BACKEND_UNAVAILABLE`로 전환, 0016 Accepted·색인
- 리뷰 게이트 1차 답변: 1번 부분(비치명 검색 실패 흐름 보충 설명), 2번 설명 제공, 3번 통과 → 사용자 확인 대기

## CP1 통과 (2026-10-21)
- 사용자 리뷰 게이트 통과(보충 설명 후 승인), main `4383825` push
- :8100·:8600 Base 데모 프로세스 확인 → 이미 종료돼 있음

## A3 1차 검증 (2026-10-21 11:24, feat/api `625b96f`) — 여기서 정지
- check.sh FAIL 0 · WARN 1(0017·0018 색인 미등록), 테스트 131 통과(api 58), 계약 미변경
- 미검토: Proposed ADR-0017(API가 새 턴 입력 초기화 `FRESH_TURN`·스레드 락·저장 재시도), ADR-0018(빈 구조화 출력 → LLM_OUTPUT_INVALID). 두 건 모두 A1(agent/) 수정 요청을 포함
- **CP2 위험**: A3 측정 qwen3:8b Coach 구조화 출력 성공률 1/6 → "ollama 승인 → 저장" 기준 미달 가능. 대응 후보: (a) CP2 정상 경로는 OpenAI(gpt-4o-mini)로 확인하고 ollama는 오류 경로·실패율 측정(한계 3)으로, (b) QUALITY_MODEL 조정(qwen3.5:4b 등)·프롬프트 조정
- A3 메모: api worktree에서 `.env.example`이 작업 트리에서만 삭제돼 있었음(복원함, 원인 불명 — 다른 세션의 stash/checkout 의심, 재발 시 확인)

## CP2 (2026-10-21 13:30~13:50)
- `.env.example`이 64ca3bb에서 삭제 커밋됨(사용자가 .env로 이름 변경 → Lead `git add -A`) → 복원 `4b0a5a6`. 원격(4383825)에는 영향 없음. **교훈: main에서 `git add -A` 전에 `git status` 확인**
- feat/api 병합 `3baf454`. 통합 수정: router·coach 빈 구조화 출력 → LLM_OUTPUT_INVALID(0018), router가 새 턴 필드 초기화(0017 1번 보강), A1 테스트 기대값 None 허용. ADR 0016(색인만)·0017·0018 Accepted
- 스모크: fake OK / ollama qwen3:8b 0/3(LLM_OUTPUT_INVALID) / **ollama qwen3.5:4b OK(첫 시도, 승인 → 저장)** → ADR-0019로 기본값 변경
- 테스트 8·9·11·재시작 후 pending 복원은 A3 테스트(132 passed)로 확인

## 운영 변경 (2026-10-21, 사용자 요청)
- 리뷰 게이트 전에 Lead가 `doc/handoff/flow-guide.md`(사용자용 흐름 설명서)를 갱신하고, 질문은 그 문서로 답할 수 있게 낸다. 모르는 부분은 대화로 채우고 §7 Q&A에 누적

## CP3 (2026-10-21 14:20~)
- CP2 승인·push(`a5afe0a`). 사용률 5%(14:00 재설정 후)
- feat/web 병합 `f0d6cc5`, 프록시 `BACKEND_UNAVAILABLE` 전환·ADR-0016 Accepted `e99ffde`
- 통합 수정 `8791c81`: build_deps가 데이터 폴더 생성(없으면 서버 기동 실패했음), seed_sample.sh가 .env보다 명령의 COACH_DATA_DIR 우선(이전엔 .env가 덮어씀 → 샘플이 data/로 감, data/는 새로 생긴 폴더라 사용자 데이터와 섞이지 않음)
- 실제 스택 E2E(프록시 :8600 경유, ollama qwen3:0.6b·qwen3.5:4b·nomic-embed-text): stream 7이벤트 → pending 복원 → resume 저장(C0001) → 재승인 409 → 카드함 1장. 첫 시도 성공
- 사용자 브라우저 E2E 대기 (서버·프록시를 scratchpad e2e_data로 띄워 둠)

## 재개 순서 (14:00 이후)
1. 사용률 확인
2. ADR-0017·0018 판정 → 필요한 A1 수정 지시(라우터 None 처리, 새 턴 초기화) 또는 수용
3. feat/api 병합 → check.sh → CP2 스모크: `nomic-embed-text` 준비, `.env`, `bash sh/smoke_chat.sh fake` → ollama(또는 OpenAI) → 서버 재시작 후 pending 복원
4. CP2 리뷰 게이트 → push → CP3(feat/web 병합 + A4 후속 BACKEND_UNAVAILABLE, 브라우저 E2E)

## 남은 항목
- 위 재개 순서

## 다음 시작점
- CP0 승인·push 완료(2026-10-20, `0b29d58`). Day2 오전 각 worktree에서 kickoff-prompts.md로 A1·A2·A4 착수. 일정 압축 조정안은 [next-steps.md](next-steps.md) — 확정 시 ADR-0010·work-plan §7 갱신
- 새 세션이 이어받을 때: "skala-ai-miniproject의 Lead다. agent.md, doc/handoff/lead-progress.md(특히 'A3 1차 검증'과 '재개 순서'), doc/handoff/api.md를 읽어라. CP1까지 통과·push됐고(main 4383825 이후), A1·A2는 main에 병합, A3(feat/api)·A4(feat/web)는 완료 후 미병합이다. 먼저 사용자에게 현재 사용률을 묻고 '재개 순서'대로 진행하라. 커밋에 AI 이름을 넣지 말 것."
