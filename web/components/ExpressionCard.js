// 표현 카드: Formal/Casual, 핵심 표현, 근거 칩, 답변 초안 (contracts.schemas.ExpressionCard)
window.IC.components.ExpressionCard = {
  props: { card: { type: Object, required: true } },
  computed: {
    isAnswer() { return this.card.mode === 'answer'; },
  },
  template: `
    <article class="xcard">
      <header>
        <span class="pill" :class="card.mode">{{ isAnswer ? '면접 답변' : '문장 표현' }}</span>
        <span class="prompt">{{ card.korean_prompt }}</span>
      </header>
      <section class="pair">
        <div class="tone formal">
          <h4>Formal <small>{{ isAnswer ? '답변의 첫 문장' : '면접관에게' }}</small></h4>
          <p lang="en">{{ card.formal_expression }}</p>
        </div>
        <div class="tone casual">
          <h4>Casual <small>동료에게</small></h4>
          <p lang="en">{{ card.casual_expression }}</p>
        </div>
      </section>
      <section v-if="card.answer_draft" class="draft">
        <h4>답변 초안 <small>30~45초 분량</small></h4>
        <p lang="en">{{ card.answer_draft }}</p>
      </section>
      <section v-if="card.chunks.length">
        <h4>핵심 표현</h4>
        <ul class="chunks">
          <li v-for="c in card.chunks" :key="c.phrase"><b lang="en">{{ c.phrase }}</b><span>{{ c.note }}</span></li>
        </ul>
      </section>
      <section v-if="card.note" class="why">
        <h4>이 표현을 고른 이유</h4>
        <p>{{ card.note }}</p>
      </section>
      <footer v-if="card.evidence.length">
        <span class="label">근거</span>
        <span v-for="(e, i) in card.evidence" :key="i" class="chip">{{ e }}</span>
      </footer>
    </article>`,
};
