// 지원 공고: 붙여넣기/업로드 → [6개 섹션 정리] → 수정 → 저장 (POST /api/posting/normalize, PUT /api/posting)
(function () {
  const SECTIONS = ['회사 소개', '주요 업무', '자격 요건', '우대 사항', '전형 절차', '영어 면접 안내'];
  const REQUIRED = ['주요 업무', '자격 요건'];   // contracts.schemas.REQUIRED_POSTING_SECTIONS

  window.IC.components.PostingEditor = {
    data() { return { raw: '', markdown: '', draft: false, busy: false, savedAt: null, error: null }; },
    computed: {
      // 사용자가 고친 markdown의 `## 섹션` 제목으로 섹션 상태를 바로 계산한다
      chips() {
        const found = new Set([...this.markdown.matchAll(/^##\s+(.+?)\s*$/gm)].map((m) => m[1]));
        return SECTIONS.map((name) => ({ name, found: found.has(name), required: REQUIRED.includes(name) }));
      },
      missingRequired() { return this.chips.filter((c) => c.required && !c.found).map((c) => c.name); },
    },
    methods: {
      async onFile(event) {
        const file = event.target.files[0];
        event.target.value = '';
        if (file) this.raw = await window.IC.api.readFile(file);
      },
      async normalize() {
        this.busy = true;
        try {
          const res = await window.IC.api.normalizePosting(this.raw);
          this.markdown = res.markdown;
          this.draft = true;
          this.savedAt = null;
          this.error = null;
        } catch (e) { this.error = window.IC.api.toErrorInfo(e); } finally { this.busy = false; }
      },
      async save() {
        this.busy = true;
        try {
          await window.IC.api.savePosting(this.markdown);
          this.savedAt = new Date().toLocaleTimeString('ko-KR');
          this.error = null;
          window.IC.store.refreshReadiness();
        } catch (e) { this.error = window.IC.api.toErrorInfo(e); } finally { this.busy = false; }
      },
    },
    template: `
      <section class="panel">
        <h2>4. 지원 공고</h2>
        <div v-if="!draft" class="form">
          <label>공고 원문 <small>붙여넣기 또는 파일 업로드</small>
            <textarea v-model="raw" rows="7" placeholder="채용 공고 텍스트를 붙여넣어 주세요"></textarea></label>
          <label class="upload"><input type="file" accept=".md,.txt,text/plain" @change="onFile"> 파일에서 불러오기 (.md/.txt)</label>
        </div>
        <div v-else class="form">
          <div class="sections">
            <span v-for="c in chips" :key="c.name" class="chip" :class="{ ok: c.found, miss: !c.found && c.required }">
              {{ c.found ? '✓' : (c.required ? '✕' : '–') }} {{ c.name }}</span>
          </div>
          <p v-if="missingRequired.length" class="hint" role="alert">필수 섹션이 없어요: {{ missingRequired.join(', ') }}. 아래에서 직접 추가해 주세요.</p>
          <label>정리된 공고 <small>섹션 제목은 “## 섹션 이름” 형식</small>
            <textarea v-model="markdown" rows="14" class="mono"></textarea></label>
        </div>
        <error-box v-if="error" :error="error" retryable dismissable @retry="draft ? save() : normalize()" @dismiss="error = null"></error-box>
        <div class="actions">
          <template v-if="!draft">
            <button class="btn primary" :disabled="busy || !raw.trim()" @click="normalize">{{ busy ? '정리 중…' : '6개 섹션으로 정리' }}</button>
          </template>
          <template v-else>
            <button class="btn primary" :disabled="busy || !markdown.trim()" @click="save">저장</button>
            <button class="btn ghost" :disabled="busy" @click="draft = false">원문 다시 입력</button>
            <span v-if="savedAt" class="muted" aria-live="polite">{{ savedAt }}에 저장했어요</span>
          </template>
        </div>
      </section>`,
  };
})();
