// 탭 사이에 공유하는 화면 상태. 서버 데이터는 각 탭이 직접 불러오고, 여기에는 여러 탭이 같이 보는 것만 둔다
(function () {
  const IC = window.IC;
  const TAB_KEY = 'ic.tab';
  const TABS = ['prepare', 'coach', 'cards'];

  let savedTab = null;
  try { savedTab = localStorage.getItem(TAB_KEY); } catch { /* 저장 불가 환경 */ }

  const store = Vue.reactive({
    tab: TABS.includes(savedTab) ? savedTab : 'prepare',
    readiness: null,       // GET /api/readiness 응답
    readinessError: null,  // 불러오기 실패 시 ErrorInfo
    mock: false,           // web_server.py가 MOCK=1이면 true (GET /mock-info)
    mockChips: [],
    cardsVersion: 0,       // 카드를 저장·복습할 때마다 올려서 카드 탭이 다시 불러오게 한다
  });

  Vue.watch(() => store.tab, (tab) => {
    try { localStorage.setItem(TAB_KEY, tab); } catch { /* 저장 불가 환경 */ }
  });

  store.refreshReadiness = async () => {
    try {
      store.readiness = await IC.api.readiness();
      store.readinessError = null;
    } catch (e) { store.readinessError = IC.api.toErrorInfo(e); }
  };

  // MOCK 서버에만 있는 경로. 실제 백엔드 모드에서는 404이므로 조용히 넘어간다
  store.detectMock = async () => {
    try {
      const res = await fetch('/mock-info');
      const info = res.ok ? await res.json() : null;
      store.mock = !!(info && info.mock);
      store.mockChips = store.mock ? info.chips : [];
    } catch { /* 실제 백엔드 모드 */ }
  };

  store.goPrepare = () => { store.tab = 'prepare'; };
  IC.store = store;
})();
