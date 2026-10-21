// 경험 문서: .md를 FileReader로 읽어 JSON으로 업로드 (ADR-0007), 목록·삭제 (GET/POST/DELETE /api/docs)
window.IC.components.DocManager = {
  data() { return { docs: [], busy: false, error: null, notes: [] }; },
  mounted() { this.load(); },
  methods: {
    async load() {
      try { this.docs = await window.IC.api.listDocs(); this.error = null; } catch (e) { this.error = window.IC.api.toErrorInfo(e); }
    },
    async onFiles(event) {
      const { api, store } = window.IC;
      const files = Array.from(event.target.files);
      event.target.value = '';   // 같은 파일을 다시 고를 수 있게 비운다
      this.busy = true;
      this.notes = [];
      for (const file of files) {
        if (!file.name.endsWith('.md')) { this.notes.push(file.name + ': .md 파일만 올릴 수 있어요'); continue; }
        try {
          const content = await api.readFile(file);
          if (!content.trim()) { this.notes.push(file.name + ': 내용이 비어 있어요'); continue; }
          await api.addDoc(file.name, content);
          this.error = null;
        } catch (e) { this.error = api.toErrorInfo(e); break; }
      }
      await this.load();
      store.refreshReadiness();
      this.busy = false;
    },
    async remove(doc) {
      if (!confirm(doc.name + ' 문서를 삭제할까요?')) return;
      try {
        await window.IC.api.deleteDoc(doc.name);
        await this.load();
        window.IC.store.refreshReadiness();
      } catch (e) { this.error = window.IC.api.toErrorInfo(e); }
    },
  },
  template: `
    <section class="panel">
      <h2>3. 경험 문서 <small>.md</small></h2>
      <ul v-if="docs.length" class="docs">
        <li v-for="d in docs" :key="d.name">
          <b>{{ d.name }}</b><span class="muted">{{ d.chars }}자 · {{ d.updated.slice(0, 16).replace('T', ' ') }}</span>
          <button class="btn ghost" @click="remove(d)">삭제</button>
        </li>
      </ul>
      <p v-else class="empty-line">올린 문서가 없어요. 경험·프로젝트를 적은 .md 파일을 올려 주세요.</p>
      <p v-for="n in notes" :key="n" class="hint" role="alert">{{ n }}</p>
      <error-box v-if="error" :error="error" retryable dismissable @retry="load" @dismiss="error = null"></error-box>
      <label class="upload" :class="{ disabled: busy }">
        <input type="file" accept=".md" multiple :disabled="busy" @change="onFiles"> {{ busy ? '업로드 중…' : '.md 파일 선택 (여러 개 가능)' }}
      </label>
    </section>`,
};
