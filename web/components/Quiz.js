// 오늘 복습 플립 퀴즈 (P1): GET /api/cards/due → 한국어를 보고 말해 본 뒤 정답 확인 → 안다/다시 (POST /api/cards/{id}/review)
window.IC.components.Quiz = {
  emits: ['close'],
  data() { return { queue: [], i: 0, flipped: false, loaded: false, busy: false, error: null, tried: null, known: 0, again: 0, last: null }; },
  computed: {
    card() { return this.queue[this.i]; },
    finished() { return this.loaded && !this.error && this.queue.length > 0 && this.i >= this.queue.length; },
  },
  mounted() { this.load(); },
  methods: {
    async load() {
      const { api } = window.IC;
      try { this.queue = await api.dueCards(); this.error = null; } catch (e) { this.error = api.toErrorInfo(e); }
      this.loaded = true;
    },
    async answer(result) {
      const { api, store } = window.IC;
      this.busy = true;
      this.tried = result;   // 실패하면 같은 답으로 다시 시도한다
      try {
        this.last = await api.reviewCard(this.card.id, result);
        if (result === 'known') this.known++; else this.again++;
        this.i++;
        this.flipped = false;
        this.error = null;
        store.cardsVersion++;
      } catch (e) { this.error = api.toErrorInfo(e); } finally { this.busy = false; }
    },
  },
  template: `
    <section class="panel quiz">
      <div class="quiz-head">
        <h3>오늘 복습 <span v-if="card" class="muted">{{ i + 1 }} / {{ queue.length }}</span></h3>
        <button class="btn ghost" @click="$emit('close')">{{ finished ? '닫기' : '그만하기' }}</button>
      </div>
      <error-box v-if="error" :error="error" :retryable="true" @retry="card ? answer(tried) : load()"></error-box>
      <p v-if="loaded && !queue.length && !error" class="empty-line">오늘 복습할 카드가 없어요.</p>
      <div v-else-if="card" class="flip">
        <template v-if="!flipped">
          <p class="q">{{ card.korean_prompt }}</p>
          <p class="muted">영어로 먼저 말해 본 뒤 정답을 확인하세요.</p>
          <button class="btn primary" @click="flipped = true">정답 보기</button>
        </template>
        <template v-else>
          <expression-card :card="card"></expression-card>
          <div class="actions">
            <button class="btn primary" :disabled="busy" @click="answer('known')">안다</button>
            <button class="btn" :disabled="busy" @click="answer('again')">다시</button>
          </div>
        </template>
      </div>
      <div v-else-if="finished" class="result ok">복습 끝 — 안다 {{ known }}장 · 다시 {{ again }}장</div>
      <p v-if="last" class="muted" aria-live="polite">{{ last.id }} 다음 복습 {{ last.next_review }}</p>
    </section>`,
};
