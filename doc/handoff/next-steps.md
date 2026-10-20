# 다음 할 일 — Day2(10/21) 오전부터

> CP0 통과·push 완료 (2026-10-20, main `0b29d58`). 원래 계획은 Day1 저녁에 역할 agent를 착수하는 것이었지만, 실제로는 Day2 오전에 시작하므로 아래 일정은 **압축 조정안**이다.
> 마감: Day3(10/22) 13:00 — Git 주소 + 결과 보고서 링크 등록.

## 0. 시작 전 5분 체크

- [ ] 5시간 창 사용률 확인 (Lead 세션에 알려 줄 값)
- [ ] ollama 실행 중인지 확인. 임베딩 모델이 없으므로 미리 받는다: `ollama pull nomic-embed-text` (qwen3:0.6b·qwen3:8b는 있음)
- [ ] `.env`는 CP2(실제 모델 연결) 전까지 없어도 된다. A1·A2·A4는 모두 fake 모델·MOCK으로 개발한다

## 1. 오전 착수 — 역할 agent 3개 동시 시작 (09:00)

각 역할마다 **새 창·새 세션**을 연다. 이 대화(Lead)와 섞지 않는다.

| 역할 | 열 폴더 | 붙여 넣을 프롬프트 |
|---|---|---|
| A1 코어 | `skala-ai-miniproject/.worktrees/core` | [kickoff-prompts.md](kickoff-prompts.md) "A1" 블록 |
| A2 MCP·RAG | `skala-ai-miniproject/.worktrees/mcp` | "A2" 블록 |
| A4 프론트 | `skala-ai-miniproject/.worktrees/web` | "A4" 블록 |

여는 방법 (둘 중 하나):
- **터미널**: `cd .../skala-ai-miniproject/.worktrees/core && claude --model sonnet` → 프롬프트 붙여 넣기
- **VS Code**: 파일 > 새 창 → 폴더 열기(`.worktrees/core`) → Claude Code 패널에서 붙여 넣기

A3(API)는 지금 시작하지 않는다. CP1이 끝나면 Lead가 A3 프롬프트를 만든다.

## 2. 진행 중 사용자가 할 일

| 상황 | 할 일 |
|---|---|
| 역할 agent가 "계약 변경 필요"·Proposed ADR을 보고 | 그 내용을 Lead 세션에 그대로 전달 → Lead가 계약·ADR 수정 후 알려 줌 → 역할 세션에 "main을 merge하고 계속" 전달 |
| 역할 agent가 완료 보고 | 보고문(check.sh 결과 포함)을 Lead 세션에 붙여 넣기 → Lead가 해당 worktree에서 check.sh 재실행·노트 대조 |
| 역할 agent가 다른 역할 파일을 고치려 함 | 멈추게 하고 Lead에 요청하도록 지시 (check.sh ⑤가 막는다) |
| 사용률이 70%에 가까움 | Lead 세션에 알리기 → 우선순위 조정 |

Lead 세션을 새로 열 때는 [lead-progress.md](lead-progress.md) 맨 아래 "새 세션이 이어받을 때" 문장을 첫 메시지로 쓴다.

## 3. 분기점 일정 (압축 조정안)

| 시점 | 분기점 | 무엇을 확인하나 | 사용자 몫 |
|---|---|---|---|
| Day2 09:00 | 착수 | A1·A2·A4 동시 시작 | 세션 3개 열기 |
| Day2 ~13:00 | **CP1** | A1+A2 병합: 실제 MCP 서버 + fake LLM 그래프 E2E, 테스트 1~7·10 + MCP 테스트 | 인수인계 노트(core.md·mcp.md) 읽고 리뷰 질문 답하기 → 승인 → push |
| Day2 ~13:00 | A3 착수 | Lead가 A3 프롬프트 작성 | `.worktrees/api`에서 세션 열기 |
| Day2 ~17:00 | **CP2** | +A3: `sh/smoke_chat.sh` fake → ollama, 테스트 8·9·11, 서버 재시작 후 승인 대기 복원 | `.env` 만들기(`.env.example` 복사), 승인 → push |
| Day2 ~21:00 | **CP3** | +A4 실제 백엔드: 브라우저 E2E(ollama), 새로고침 복원, 오류 화면 | 브라우저로 직접 시연해 보기 → 승인 → push |
| Day2 21:00 | 컷 판단 | E2E가 안 되면 P1(복습 퀴즈 등) 전부 포기 | 결정 |
| Day3 09:00~11:30 | **CP4** | OpenAI E2E, Before/After·demo 노트북, README 캡처 | OpenAI 키 준비, 승인 → push |
| Day3 11:30~13:00 | 제출 | PPT 완성, Git·보고서 링크 등록 | 등록 |

원래 계획(work-plan §7)보다 CP1~CP3가 각각 3~4시간씩 늦다. **CP3가 Day2 안에 끝나지 않으면 컷 규칙을 바로 적용한다.**
이 조정안을 확정하면 Lead가 ADR-0010과 work-plan §7을 갱신한다.

## 4. 각 CP에서 사용자 리뷰 게이트

CP마다 Lead가 질문 3개를 낸다. 인수인계 노트(`doc/handoff/<role>.md`)를 읽고 답할 수 있어야 다음으로 넘어간다. 모르는 용어가 나오면 그 자리에서 물어본다 — 발표 질의응답 대비이기도 하다.

## 5. 아직 남은 결정·준비물

| 항목 | 언제까지 | 비고 |
|---|---|---|
| 일정 조정안 확정 (위 §3) | Day2 착수 전 | Lead 세션에 "조정안 확정"이라고 알리기 |
| `nomic-embed-text` 받기 | CP2 전 | RAG 실제 임베딩용 |
| `.env` 작성 (FAST/QUALITY/EMBEDDING_MODEL, OPENAI_API_KEY, LANGSMITH_*) | CP2 전 | `.env.example` 참고, 커밋 금지 |
| OpenAI 키·크레딧 확인 | CP4 전 | Before/After 측정은 gpt-4o-mini 고정 |
| Google Slides 준비 | Day3 오전 | ADR·오류 표·Before/After 표를 그대로 사용 |
