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

## 남은 항목
- 없음. CP0 사용자 승인 대기

## 다음 시작점
- CP0 승인 → `git push -u origin main` → 각 worktree에서 kickoff-prompts.md로 A1·A2·A4 착수
- 새 세션이 이어받을 때: "skala-ai-miniproject의 Lead다. agent.md, doc/handoff/lead.md, doc/handoff/lead-progress.md를 읽고 CP0 승인 여부를 사용자에게 확인한 뒤, 승인되면 main을 origin에 push하고 역할 agent 착수를 안내하라. 커밋에 AI 이름을 넣지 말 것."
