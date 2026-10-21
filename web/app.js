// Vue 앱 — 탭 ①준비 ②코치 ③카드 (design §4). 탭은 v-show로 바꿔서 코치 대화 상태가 탭 전환에 사라지지 않는다
(function () {
  const IC = window.IC;
  const app = Vue.createApp({
    data() {
      return {
        store: IC.store,
        tabs: [{ id: 'prepare', label: '① 준비' }, { id: 'coach', label: '② 코치' }, { id: 'cards', label: '③ 카드·복습' }],
      };
    },
    computed: {
      readyClass() { const r = this.store.readiness; return r ? (r.ready ? 'ok' : 'err') : ''; },
    },
    created() { this.store.detectMock(); },
  });
  for (const [name, definition] of Object.entries(IC.components)) app.component(name, definition);
  app.mount('#app');
})();
