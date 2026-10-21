// 코치 탭 상태 로직: SSE 이벤트 → 타임라인·카드, 승인·거절, 승인 대기 복원, 오류 처리 (design §4·§5, ADR-0006·0012)
(function () {
  const IC = window.IC;
  const INTENT_LABEL = { express: '문장 표현 만들기', answer: '면접 답변 만들기', review: '카드 복습', out_of_scope: '범위 밖' };
  const TOOL_LABEL = { search_my_experience: '내 경험 검색', search_expression_bank: '표현집 검색', get_job_posting: '공고 조회' };
  const TERMINAL = ['ApprovalRequired', 'FinalAnswer', 'ErrorRaised'];   // 이 중 하나 없이 끝난 스트림은 끊긴 것으로 본다

  // 이벤트 하나를 turn(요청 한 건의 화면 상태)에 반영한다. 계약 밖 이벤트는 무시한다
  function applyEvent(turn, e) {
    switch (e.type) {
      case 'RouteDecided':
        turn.intent = e.intent;
        turn.steps.push({ state: 'done', text: '요청 분류 · ' + (INTENT_LABEL[e.intent] || e.intent) });
        break;
      case 'EvidenceSearched':   // error가 있으면 이 검색만 실패한 것 (치명 아님, 진행은 계속된다)
        turn.steps.push({ state: e.error ? 'error' : 'done', text: '근거 검색 · ' + (TOOL_LABEL[e.tool] || e.tool),
          detail: e.query, error: e.error });
        break;
      case 'CardDrafted':
        turn.steps.push({ state: 'done', text: e.attempt > 1 ? '재작성 · ' + e.attempt + '번째 초안' : '카드 초안 작성' });
        break;
      case 'ReviewDone':         // error가 있으면 REVIEWER_DEGRADED: 규칙 검사만 적용됨
        turn.lastReview = e;
        turn.steps.push({ state: e.error ? 'warn' : e.passed ? 'done' : 'fail',
          text: '규칙 검수 ' + e.round + '회차 · ' + (e.passed ? '통과' : '위반 ' + e.violations.length + '건'),
          violations: e.violations, error: e.error });
        break;
      case 'ApprovalRequired':
        Object.assign(turn, { card: e.card, warning: e.warning, notices: e.notices || [], status: 'awaiting' });
        turn.steps.push({ state: 'wait', text: '승인 대기' });
        break;
      case 'FinalAnswer': turn.reply = e.reply; turn.status = 'done'; break;
      case 'ErrorRaised': turn.error = e.error; turn.status = 'error'; break;
    }
  }

  IC.useCoach = function () {
    const { api, store } = IC;
    const entries = Vue.ref([]);          // 말풍선: { id, text } 또는 요청 한 건: { id, turn }
    const startupError = Vue.ref(null);
    const tick = Vue.ref(0);              // 화면이 맨 아래로 스크롤할 신호
    let seq = 0;
    const busy = Vue.computed(() => entries.value.some((x) => x.turn && ['running', 'awaiting'].includes(x.turn.status)));

    const blankTurn = () => ({ status: 'running', intent: null, steps: [], card: null, warning: null, notices: [],
      lastReview: null, reply: null, error: null, retryFn: null });
    const addTurn = (message) => {
      const turn = Vue.reactive({ ...blankTurn(), message, result: null, restored: false, question: null, resolving: false });
      entries.value.push({ id: ++seq, text: message }, { id: ++seq, turn });
      return turn;
    };

    function run(turn) {
      Object.assign(turn, blankTurn());
      let terminal = false;
      api.streamChat(turn.message, {
        onEvent(e) {
          terminal = terminal || TERMINAL.includes(e.type);
          applyEvent(turn, e);
          if (e.type === 'ErrorRaised') turn.retryFn = () => run(turn);
          tick.value++;
        },
        onDone() { if (!terminal) lost(turn); },
        onDisconnect() { lost(turn); },
      });
    }

    // 승인 대기 payload(ApprovalRequest)를 화면에 올린다. 새로고침 복원과 스트림 끊김 복구가 같이 쓴다
    function showPending(turn, p) {
      const fresh = turn.steps.length === 0;
      Object.assign(turn, { status: 'awaiting', card: p.card, warning: p.warning, notices: p.notices || [],
        question: p.question, restored: true, error: null, retryFn: null });
      if (p.review) {
        turn.lastReview = p.review;
        if (fresh && !p.review.passed) turn.steps.push({ state: 'fail', text: '마지막 규칙 검수 결과', violations: p.review.violations });
      }
      turn.steps.push({ state: 'wait', text: '승인 대기 (복원됨)' });
    }

    // SSE가 끊기면 /chat/pending으로 승인 대기가 있는지 확인하고, 없으면 다시 시도를 안내한다 (STREAM_DISCONNECTED)
    async function lost(turn) {
      Object.assign(turn, { status: 'error', error: api.streamLost(), retryFn: () => run(turn) });
      try {
        const res = await api.pending();
        if (res.pending) showPending(turn, res.pending);
      } catch (e) { turn.error = api.toErrorInfo(e); }
      tick.value++;
    }

    async function restore() {
      startupError.value = null;
      try {
        const res = await api.pending();
        if (!res.pending) return;
        showPending(addTurn(res.pending.card.korean_prompt), res.pending);
        store.tab = 'coach';   // 승인 대기 카드가 다른 탭에 가려지지 않게 한다
        tick.value++;
      } catch (e) { startupError.value = api.toErrorInfo(e); }
    }

    async function resolve(turn, approve) {
      Object.assign(turn, { resolving: true, error: null, retryFn: null });
      try {
        turn.result = await api.resume(approve);
        turn.status = turn.result.saved ? 'saved' : 'rejected';
        if (turn.result.saved) store.cardsVersion++;
      } catch (e) {
        turn.error = api.toErrorInfo(e);
        if (turn.error.code === 'NO_PENDING') turn.status = 'stale';   // 이미 처리됨: 버튼을 거둔다
        else turn.retryFn = () => resolve(turn, approve);
      } finally { turn.resolving = false; tick.value++; }
    }

    function send(message) {
      const text = message.trim();
      if (!text || busy.value) return;
      run(addTurn(text));
    }

    function reset() { api.newThread(); entries.value = []; startupError.value = null; }

    return { entries, busy, tick, startupError, send, resolve, restore, reset };
  };
  IC.applyEvent = applyEvent;   // 단독 검증용
})();
