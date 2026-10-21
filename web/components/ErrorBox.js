// 오류 표시 (ADR-0012 Presentation): user_message를 보여 주고, recoverable이면 다시 시도, NOT_READY면 준비 탭 이동
window.IC.components.ErrorBox = {
  props: { error: { type: Object, required: true }, retryable: Boolean, dismissable: Boolean },
  emits: ['retry', 'dismiss'],
  computed: {
    showRetry() { return this.error.recoverable && this.retryable; },
    notReady() { return this.error.code === 'NOT_READY'; },
  },
  methods: { goPrepare() { window.IC.store.goPrepare(); } },
  template: `
    <div class="errbox" :class="error.fatal ? 'fatal' : 'soft'" role="alert">
      <div class="errmsg">{{ error.user_message }}</div>
      <div class="errmeta">{{ error.code }}<span v-if="error.trace_id"> · trace id {{ error.trace_id }}</span></div>
      <div v-if="showRetry || notReady || dismissable" class="actions">
        <button v-if="showRetry" class="btn" @click="$emit('retry')">다시 시도</button>
        <button v-if="notReady" class="btn primary" @click="goPrepare">준비 탭으로 이동</button>
        <button v-if="dismissable" class="btn ghost" @click="$emit('dismiss')">닫기</button>
      </div>
    </div>`,
};
