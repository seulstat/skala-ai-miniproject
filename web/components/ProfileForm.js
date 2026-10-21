// 프로필 폼: GET/PUT /api/profile (contracts.schemas.UserProfile). 목록 필드는 입력 편의상 문자열로 받아 나눈다
(function () {
  const { api, store } = window.IC;
  const blank = () => ({ goal: '', target_role: '', speaking_with: '', tone_preference: '중립/상관없음', english_variety: '상관없음',
    certifications: [], background: '', persona_summary: '', known_chunks: '' });
  const toForm = (p) => ({ ...blank(), ...p, speaking_with: (p.speaking_with || []).join(', '),
    known_chunks: (p.known_chunks || []).join('\n'), certifications: (p.certifications || []).map((c) => ({ ...c })) });
  const split = (s, sep) => s.split(sep).map((x) => x.trim()).filter(Boolean);
  const toProfile = (f) => ({ ...f, speaking_with: split(f.speaking_with, ','), known_chunks: split(f.known_chunks, '\n'),
    certifications: f.certifications.filter((c) => c.name.trim() && c.score_or_level.trim()) });

  window.IC.components.ProfileForm = {
    data() {
      return { form: blank(), saving: false, savedAt: null, hint: '', error: null,
        tones: ['직설적인느낌', '부드럽고 정중한 느낌', '중립/상관없음'], varieties: ['미국식', '영국식', '호주식', '상관없음'] };
    },
    mounted() { this.load(); },
    methods: {
      async load() {
        try { this.form = toForm(await api.getProfile()); this.error = null; } catch (e) {
          const info = api.toErrorInfo(e);
          this.error = info.code === 'NOT_FOUND' ? null : info;   // NOT_FOUND = 아직 프로필 없음 → 빈 폼
        }
      },
      async save() {
        this.hint = '';
        if (!this.form.goal.trim() || !this.form.target_role.trim()) { this.hint = '목표와 지원 직무는 꼭 입력해 주세요.'; return; }
        this.saving = true;
        try {
          await api.putProfile(toProfile(this.form));
          this.error = null;
          this.savedAt = new Date().toLocaleTimeString('ko-KR');
          store.refreshReadiness();
        } catch (e) { this.error = api.toErrorInfo(e); } finally { this.saving = false; }
      },
      addCert() { this.form.certifications.push({ name: '', score_or_level: '' }); },
    },
    template: `
      <section class="panel">
        <h2>2. 프로필</h2>
        <form class="form" @submit.prevent="save">
          <label>목표 <input v-model="form.goal" placeholder="예: 취업 면접(영어 면접 포함)" required></label>
          <label>지원 직무 <input v-model="form.target_role" placeholder="예: 이커머스 데이터 분석가 (신입)" required></label>
          <label>대화 상대 <small>쉼표로 구분</small><input v-model="form.speaking_with" placeholder="면접관, 해외 파트너"></label>
          <div class="grid2">
            <label>선호 말투 <select v-model="form.tone_preference"><option v-for="t in tones" :key="t">{{ t }}</option></select></label>
            <label>영어 억양 <select v-model="form.english_variety"><option v-for="v in varieties" :key="v">{{ v }}</option></select></label>
          </div>
          <fieldset>
            <legend>영어 자격 <small>이름 · 점수/등급</small></legend>
            <div v-for="(c, i) in form.certifications" :key="i" class="cert">
              <input v-model="c.name" placeholder="OPIc" aria-label="자격 이름">
              <input v-model="c.score_or_level" placeholder="IM2" aria-label="점수 또는 등급">
              <button type="button" class="btn ghost" @click="form.certifications.splice(i, 1)">삭제</button>
            </div>
            <button type="button" class="btn ghost" @click="addCert">+ 자격 추가</button>
          </fieldset>
          <label>배경 <textarea v-model="form.background" rows="3" placeholder="전공, 프로젝트, 인턴 경험 등"></textarea></label>
          <label>면접에서 보이고 싶은 모습 <small>선택</small><input v-model="form.persona_summary"></label>
          <label>이미 익숙한 표현 <small>한 줄에 하나, 선택</small><textarea v-model="form.known_chunks" rows="2"></textarea></label>
          <p v-if="hint" class="hint" role="alert">{{ hint }}</p>
          <error-box v-if="error" :error="error" retryable dismissable @retry="save" @dismiss="error = null"></error-box>
          <div class="actions">
            <button class="btn primary" type="submit" :disabled="saving">저장</button>
            <span v-if="savedAt" class="muted" aria-live="polite">{{ savedAt }}에 저장했어요</span>
          </div>
        </form>
      </section>`,
  };
})();
