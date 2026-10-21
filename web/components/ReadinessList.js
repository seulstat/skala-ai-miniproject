// 준비 체크리스트: GET /api/readiness 항목(프로필·경험 문서·공고 필수 + 개인정보 경고) + 개인정보 안내
window.IC.components.ReadinessList = {
  data() { return { store: window.IC.store, MARK: { ok: '✓', warn: '⚠', error: '✕' }, busy: false }; },
  computed: {
    items() { return this.store.readiness ? this.store.readiness.items : []; },
    ready() { return !!(this.store.readiness && this.store.readiness.ready); },
  },
  methods: {
    async recheck() { this.busy = true; await this.store.refreshReadiness(); this.busy = false; },
  },
  template: `
    <section class="panel">
      <h2>1. 준비 점검
        <span v-if="store.readiness" class="badge" :class="ready ? 'ok' : 'err'">{{ ready ? '준비 완료' : '준비 필요' }}</span>
      </h2>
      <ul class="checklist">
        <li v-for="it in items" :key="it.item" :class="it.status">
          <span class="mark">{{ MARK[it.status] }}</span><b>{{ it.item }}</b><span>{{ it.message }}</span>
        </li>
      </ul>
      <error-box v-if="store.readinessError" :error="store.readinessError" retryable @retry="recheck"></error-box>
      <div class="banner warn privacy">
        ⚠ 개인정보: 실제 이력서·연락처는 올리지 마세요. 시연에는 examples/sample_user의 가상 서류만 쓰세요.
        OpenAI 같은 외부 LLM을 쓰면 업로드한 서류 내용이 외부로 전송돼요 (ollama는 내 컴퓨터 안에서만 처리).
      </div>
      <div class="actions"><button class="btn" :disabled="busy" @click="recheck">다시 점검</button></div>
    </section>`,
};
