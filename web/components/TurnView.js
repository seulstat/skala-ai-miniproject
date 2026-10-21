// 요청 한 건의 화면: 타임라인 → 경고 배너 → 카드 → 승인·거절 → 결과 / 최종 답변 / 오류
window.IC.components.TurnView = {
  props: { turn: { type: Object, required: true } },
  emits: ['resolve'],
  computed: {
    // 검수를 끝내 통과하지 못한 채 승인 단계로 온 경우 남은 위반
    remaining() { const r = this.turn.lastReview; return r && !r.passed ? r.violations : []; },
    canResolve() { return this.turn.status === 'awaiting'; },
  },
  template: `
    <div class="turn">
      <timeline :steps="turn.steps" :running="turn.status === 'running'"></timeline>
      <div v-if="turn.reply" class="bubble agent">{{ turn.reply }}</div>
      <template v-if="turn.card">
        <div v-if="turn.restored" class="banner info">새로고침·재연결 전에 승인 대기 중이던 카드를 불러왔어요.</div>
        <div v-if="turn.warning || remaining.length" class="banner warn" role="alert">
          <div v-if="turn.warning">⚠ {{ turn.warning }}</div>
          <ul v-if="remaining.length">
            <li v-for="(v, i) in remaining" :key="i"><b>{{ v.rule_id }}</b> <code>{{ v.quote }}</code> → {{ v.fix }}</li>
          </ul>
        </div>
        <div v-for="(n, i) in turn.notices" :key="'n' + i" class="banner notice" role="alert">ⓘ {{ n.user_message }}</div>
        <expression-card :card="turn.card"></expression-card>
        <div v-if="canResolve" class="approve">
          <span>{{ turn.question || '이 카드를 복습 카드로 저장할까요?' }}</span>
          <button class="btn primary" :disabled="turn.resolving" @click="$emit('resolve', true)">승인하고 저장</button>
          <button class="btn" :disabled="turn.resolving" @click="$emit('resolve', false)">거절</button>
        </div>
        <div v-if="turn.status === 'saved'" class="result ok">저장했어요 · 카드 {{ turn.result.card_id }} · 다음 복습 {{ turn.result.next_review }}</div>
        <div v-if="turn.status === 'rejected'" class="result">거절했어요. 카드는 저장되지 않았어요.</div>
      </template>
      <error-box v-if="turn.error" :error="turn.error" :retryable="!!turn.retryFn" @retry="turn.retryFn()"></error-box>
    </div>`,
};
