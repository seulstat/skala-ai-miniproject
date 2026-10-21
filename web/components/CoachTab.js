// ② 코치 탭: 채팅 입력 + 예시 칩, 요청별 타임라인·카드·승인 (상태 로직은 web/coach.js)
const COACH_EXAMPLES = [   // contracts/fixtures의 시나리오와 같은 문장
  '배송 지연 원인을 데이터로 찾아서 민원을 줄였다고 말하고 싶어',
  'Tell me about a time you changed your approach based on feedback.',
  '오늘 복습할 카드 보여줘',
];

window.IC.components.CoachTab = {
  setup() {
    const coach = window.IC.useCoach();
    const input = Vue.ref('');
    const logEl = Vue.ref(null);
    const store = window.IC.store;
    const notReady = Vue.computed(() => store.readiness && !store.readiness.ready);

    function submit() {
      if (!input.value.trim() || coach.busy.value) return;
      coach.send(input.value);
      input.value = '';
    }
    function fill(text) { input.value = text; }
    Vue.watch(coach.tick, () => Vue.nextTick(() => { if (logEl.value) logEl.value.scrollTop = logEl.value.scrollHeight; }));
    Vue.onMounted(coach.restore);   // 새로고침 후 승인 대기 복원 (GET /chat/pending)

    return { ...coach, input, logEl, store, notReady, examples: COACH_EXAMPLES, submit, fill,
      threadId: () => window.IC.api.threadId() };
  },
  template: `
    <section class="coach">
      <div class="coach-bar">
        <span class="muted">대화 {{ threadId() }}</span>
        <button class="btn ghost" :disabled="busy" @click="reset">새 대화</button>
      </div>
      <div class="log" ref="logEl">
        <error-box v-if="startupError" :error="startupError" retryable @retry="restore"></error-box>
        <div v-if="notReady" class="banner warn">준비가 끝나지 않았어요. 준비 탭에서 프로필·경험 문서·공고를 먼저 입력해 주세요.</div>
        <p v-if="!entries.length" class="empty">면접에서 하고 싶은 말이나 받을 질문을 입력해 보세요.<br>근거를 찾아 카드를 만들고, 승인한 카드만 저장돼요.</p>
        <template v-for="item in entries" :key="item.id">
          <div v-if="!item.turn" class="bubble user">{{ item.text }}</div>
          <turn-view v-else :turn="item.turn" @resolve="(approve) => resolve(item.turn, approve)"></turn-view>
        </template>
      </div>
      <div class="composer">
        <div class="chips">
          <button v-for="ex in examples" :key="ex" type="button" class="chip action" @click="fill(ex)">{{ ex }}</button>
        </div>
        <div v-if="store.mock" class="chips mock">
          <span class="label">MOCK 시나리오</span>
          <button v-for="c in store.mockChips" :key="c.label" type="button" class="chip action" @click="fill(c.message)">{{ c.label }}</button>
        </div>
        <form @submit.prevent="submit">
          <input v-model="input" autocomplete="off" aria-label="메시지" :disabled="busy"
                 :placeholder="busy ? '승인 또는 거절(또는 진행 완료)을 기다리는 중이에요' : '예: 배송 지연 원인을 데이터로 찾았다고 말하고 싶어'" />
          <button class="btn primary" type="submit" :disabled="busy || !input.trim()">보내기</button>
        </form>
      </div>
    </section>`,
};
