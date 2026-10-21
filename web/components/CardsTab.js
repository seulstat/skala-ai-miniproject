// ③ 카드·복습 탭: 저장된 카드 목록(다음 복습일). 오늘 복습 퀴즈(P1)는 Quiz 컴포넌트
(function () {
  const pad = (n) => String(n).padStart(2, '0');
  const today = () => { const d = new Date(); return d.getFullYear() + '-' + pad(d.getMonth() + 1) + '-' + pad(d.getDate()); };
  const daysUntil = (date) => Math.round((Date.parse(date + 'T00:00:00') - Date.parse(today() + 'T00:00:00')) / 86400000);

  window.IC.components.CardsTab = {
    data() { return { store: window.IC.store, cards: [], dueCount: null, open: null, quiz: false, error: null }; },
    computed: {
      sorted() { return [...this.cards].sort((a, b) => a.next_review.localeCompare(b.next_review) || a.id.localeCompare(b.id)); },
      active() { return this.store.tab === 'cards'; },
      version() { return this.store.cardsVersion; },
    },
    watch: {
      active(on) { if (on) this.load(); },   // 탭을 열 때마다 최신 상태로
      version() { this.load(); },
    },
    mounted() { this.load(); },
    methods: {
      async load() {
        const { api } = window.IC;
        try { this.cards = await api.listCards(); this.error = null; } catch (e) { this.error = api.toErrorInfo(e); return; }
        try { this.dueCount = (await api.dueCards()).length; } catch { this.dueCount = null; }
      },
      dueLabel(card) {
        const d = daysUntil(card.next_review);
        return d < 0 ? (-d) + '일 지남' : d === 0 ? '오늘' : d === 1 ? '내일' : d + '일 후';
      },
      isDue(card) { return daysUntil(card.next_review) <= 0; },
      toggle(id) { this.open = this.open === id ? null : id; },
      closeQuiz() { this.quiz = false; this.load(); },
    },
    template: `
      <div class="cards-tab">
        <div class="cards-bar">
          <h2>저장한 카드 <span class="muted">{{ cards.length }}장</span></h2>
          <button class="btn primary" :disabled="quiz || !cards.length" @click="quiz = true">
            오늘 복습 시작<span v-if="dueCount !== null"> ({{ dueCount }}장)</span></button>
        </div>
        <quiz v-if="quiz" @close="closeQuiz"></quiz>
        <error-box v-if="error" :error="error" retryable @retry="load"></error-box>
        <p v-else-if="!cards.length" class="empty">아직 저장된 카드가 없어요.<br>코치 탭에서 카드를 만들고 승인하면 여기에 쌓여요.</p>
        <ul class="cardlist">
          <li v-for="c in sorted" :key="c.id">
            <button class="cardrow" :aria-expanded="open === c.id" @click="toggle(c.id)">
              <span class="id">{{ c.id }}</span>
              <span class="pill" :class="c.mode">{{ c.mode === 'answer' ? '면접 답변' : '문장 표현' }}</span>
              <span class="text" lang="en">{{ c.formal_expression }}</span>
              <span class="due" :class="{ now: isDue(c) }">다음 복습 {{ c.next_review }} · {{ dueLabel(c) }}</span>
              <span class="stage">단계 {{ c.stage + 1 }}/3</span>
            </button>
            <expression-card v-if="open === c.id" :card="c"></expression-card>
          </li>
        </ul>
      </div>`,
  };
})();
