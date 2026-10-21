// fetch + EventSource 래퍼. 경로는 contracts/api.py ROUTES, 이벤트 형식은 contracts/events.py, 오류는 contracts/errors.py
(function () {
  const IC = (window.IC = window.IC || { components: {} });
  const THREAD_KEY = 'ic.thread_id';

  // 화면에 보여 줄 오류 정보. 모양은 contracts.errors.ErrorInfo와 같다
  class ApiError extends Error {
    constructor(info, status) { super(info.user_message); this.info = info; this.status = status; }
  }
  // 서버 응답이 아닌 오류(연결 불가·형식 불명)는 화면에서 만든다. 문구는 ERROR_CATALOG와 같은 어조로 맞춘다
  const clientError = (code, user_message, recoverable) =>
    ({ code, layer: 'presentation', recoverable, fatal: true, user_message, trace_id: null });
  const CONNECTION_LOST = clientError('STREAM_DISCONNECTED', '서버에 연결할 수 없어요. 잠시 후 다시 시도해 주세요.', true);
  const STREAM_LOST = clientError('STREAM_DISCONNECTED', '서버 연결이 끊겼어요. 승인 대기 중인 카드가 있는지 확인할게요.', true);
  const UNEXPECTED = clientError('UNEXPECTED_ERROR', '예상치 못한 오류가 발생했어요. 계속되면 trace id와 함께 알려 주세요.', false);

  async function request(method, path, body) {
    let res;
    try {
      res = await fetch(path, {
        method,
        headers: body === undefined ? {} : { 'Content-Type': 'application/json' },
        body: body === undefined ? undefined : JSON.stringify(body),
      });
    } catch { throw new ApiError(CONNECTION_LOST, 0); }
    const text = await res.text();
    let data = null;
    try { data = text ? JSON.parse(text) : null; } catch { /* JSON이 아닌 본문 */ }
    if (!res.ok) throw new ApiError(data && data.error ? data.error : UNEXPECTED, res.status);
    return data;
  }

  const toErrorInfo = (e) => (e instanceof ApiError ? e.info : UNEXPECTED);
  const enc = encodeURIComponent;

  // thread_id는 localStorage. ?thread_id=로 덮어쓸 수 있다(MOCK의 demo-thread-1 시연용)
  function threadId() {
    let id = null;
    try {
      id = new URLSearchParams(location.search).get('thread_id') || localStorage.getItem(THREAD_KEY);
      if (!id) { id = 't-' + Math.random().toString(36).slice(2, 10); }
      localStorage.setItem(THREAD_KEY, id);
    } catch { id = id || 't-fallback'; }
    return id;
  }
  function newThread() {
    const id = 't-' + Math.random().toString(36).slice(2, 10);
    try { localStorage.setItem(THREAD_KEY, id); } catch { /* 저장 불가 환경 */ }
    return id;
  }

  // GET /chat/stream → `data: <json>` 이벤트마다 onEvent, `data: [DONE]`이면 onDone, 연결 오류면 onDisconnect.
  // EventSource는 오류 시 자동 재연결하므로(= 같은 요청 재실행) 첫 오류에서 바로 닫는다
  function streamChat(message, { onEvent, onDone, onDisconnect }) {
    const es = new EventSource(`/chat/stream?message=${enc(message)}&thread_id=${enc(threadId())}`);
    let finished = false;
    const finish = () => { finished = true; es.close(); };
    es.onmessage = (ev) => {
      if (ev.data === '[DONE]') { finish(); onDone(); return; }
      let event;
      try { event = JSON.parse(ev.data); } catch { return; }
      onEvent(event);
    };
    es.onerror = () => { if (!finished) { finish(); onDisconnect(); } };
    return { close: finish };
  }

  // 파일을 UTF-8 텍스트로 읽는다 (업로드는 multipart 없이 JSON, ADR-0007)
  const readFile = (file) => new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.onerror = () => reject(reader.error);
    reader.readAsText(file, 'utf-8');
  });

  IC.api = {
    ApiError, toErrorInfo, streamChat, readFile, threadId, newThread,
    streamLost: () => STREAM_LOST,
    getProfile: () => request('GET', '/api/profile'),
    putProfile: (profile) => request('PUT', '/api/profile', profile),
    listDocs: () => request('GET', '/api/docs'),
    addDoc: (name, content) => request('POST', '/api/docs', { name, content }),
    deleteDoc: (name) => request('DELETE', `/api/docs/${enc(name)}`),
    normalizePosting: (text) => request('POST', '/api/posting/normalize', { text }),
    savePosting: (markdown) => request('PUT', '/api/posting', { markdown }),
    readiness: () => request('GET', '/api/readiness'),
    resume: (approve) => request('POST', '/chat/resume', { thread_id: threadId(), approve }),
    pending: () => request('GET', `/chat/pending?thread_id=${enc(threadId())}`),
    listCards: () => request('GET', '/api/cards'),
    dueCards: () => request('GET', '/api/cards/due'),
    reviewCard: (id, result) => request('POST', `/api/cards/${enc(id)}/review`, { result }),
  };
})();
