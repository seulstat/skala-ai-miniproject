// ① 준비 탭: 점검 → 프로필 → 경험 문서 → 공고 (design §4)
window.IC.components.PrepareTab = {
  mounted() { window.IC.store.refreshReadiness(); },
  template: `
    <div class="prepare">
      <readiness-list></readiness-list>
      <profile-form></profile-form>
      <doc-manager></doc-manager>
      <posting-editor></posting-editor>
    </div>`,
};
