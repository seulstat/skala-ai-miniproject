// 진행 타임라인: 분류 → 근거 검색 → 초안 → 검수 위반 → 재작성 (SSE 이벤트 순서, design §5)
window.IC.components.Timeline = {
  props: { steps: { type: Array, required: true }, running: Boolean },
  data() { return { MARK: { done: '✓', error: '✕', fail: '!', warn: '△', wait: '⏸' } }; },
  template: `
    <ol class="timeline">
      <li v-for="(s, i) in steps" :key="i" class="step" :class="s.state">
        <span class="mark">{{ MARK[s.state] }}</span>
        <div class="body">
          <div class="title">{{ s.text }}<span v-if="s.detail" class="detail">“{{ s.detail }}”</span></div>
          <div v-if="s.error" class="step-note">{{ s.error.user_message }}</div>
          <ul v-if="s.violations && s.violations.length" class="violations">
            <li v-for="(v, j) in s.violations" :key="j">
              <b class="rule">{{ v.rule_id }}</b> <code>{{ v.quote }}</code>
              <div class="fix">→ {{ v.fix }}</div>
            </li>
          </ul>
        </div>
      </li>
      <li v-if="running" class="step active"><span class="mark spinner"></span><div class="body">진행 중…</div></li>
    </ol>`,
};
