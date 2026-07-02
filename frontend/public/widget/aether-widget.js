/**
 * Aether Chat Widget — Embeddable Web Chat
 * Insert on any website:
 *   <script src="https://YOUR_HOST/widget/aether-widget.js" data-aether-host="https://YOUR_HOST"></script>
 */
(function () {
  'use strict';

  const script = document.currentScript;
  const host = script.getAttribute('data-aether-host') || 'http://localhost:5173';
  const tenantId = script.getAttribute('data-aether-tenant') || 'demo';
  const primaryColor = script.getAttribute('data-color') || '#1a73e8';
  const position = script.getAttribute('data-position') || 'bottom-right';
  const greeting = script.getAttribute('data-greeting') || 'Hi! How can we help?';

  // ── State ─────────────────────────────────────────────────
  let isOpen = false;
  let isConnected = false;
  let messages = [];
  let ws = null;
  let reconnectTimer = null;
  let token = null;

  // ── Styles ────────────────────────────────────────────────
  const css = `
    .aether-widget * { box-sizing: border-box; margin: 0; padding: 0; }
    .aether-widget { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; font-size: 14px; line-height: 1.5; position: fixed; z-index: 999999; ${position.includes('bottom') ? 'bottom: 20px' : 'top: 20px'}; ${position.includes('right') ? 'right: 20px' : 'left: 20px'}; }
    .aether-widget .aether-button { width: 56px; height: 56px; border-radius: 28px; background: ${primaryColor}; border: none; cursor: pointer; box-shadow: 0 4px 12px rgba(0,0,0,0.15); display: flex; align-items: center; justify-content: center; transition: transform 0.2s, box-shadow 0.2s; }
    .aether-widget .aether-button:hover { transform: scale(1.05); box-shadow: 0 6px 16px rgba(0,0,0,0.2); }
    .aether-widget .aether-button svg { width: 24px; height: 24px; fill: white; }
    .aether-widget .aether-badge { position: absolute; top: -2px; right: -2px; width: 10px; height: 10px; border-radius: 50%; background: #ea4335; border: 2px solid white; }
    .aether-widget .aether-panel { position: absolute; bottom: 72px; right: 0; width: 370px; height: 560px; max-height: calc(100vh - 100px); background: white; border-radius: 12px; box-shadow: 0 8px 32px rgba(0,0,0,0.12); display: none; flex-direction: column; overflow: hidden; }
    .aether-widget .aether-panel.open { display: flex; }
    .aether-widget .aether-header { background: ${primaryColor}; color: white; padding: 16px 20px; display: flex; align-items: center; gap: 10px; }
    .aether-widget .aether-header h3 { font-size: 16px; font-weight: 600; flex: 1; }
    .aether-widget .aether-header .aether-close { background: none; border: none; color: white; cursor: pointer; font-size: 20px; opacity: 0.8; }
    .aether-widget .aether-header .aether-close:hover { opacity: 1; }
    .aether-widget .aether-body { flex: 1; overflow-y: auto; padding: 12px; display: flex; flex-direction: column; gap: 10px; background: #f8f9fa; }
    .aether-widget .aether-msg { max-width: 85%; padding: 8px 14px; border-radius: 12px; font-size: 13px; line-height: 1.45; }
    .aether-widget .aether-msg.user { align-self: flex-end; background: ${primaryColor}; color: white; border-bottom-right-radius: 4px; }
    .aether-widget .aether-msg.bot { align-self: flex-start; background: white; color: #202124; border-bottom-left-radius: 4px; box-shadow: 0 1px 2px rgba(0,0,0,0.06); }
    .aether-widget .aether-typing { align-self: flex-start; padding: 8px 14px; display: flex; gap: 4px; }
    .aether-widget .aether-typing span { width: 7px; height: 7px; border-radius: 50%; background: #9aa0a6; animation: aether-bounce 1.4s infinite ease-in-out both; }
    .aether-widget .aether-typing span:nth-child(1) { animation-delay: -0.32s; }
    .aether-widget .aether-typing span:nth-child(2) { animation-delay: -0.16s; }
    @keyframes aether-bounce { 0%,80%,100% { transform: scale(0); } 40% { transform: scale(1); } }
    .aether-widget .aether-composer { padding: 12px; background: white; border-top: 1px solid #e0e0e0; display: flex; gap: 8px; }
    .aether-widget .aether-composer input { flex: 1; padding: 10px 14px; border: 1px solid #dadce0; border-radius: 20px; font-size: 13px; outline: none; }
    .aether-widget .aether-composer input:focus { border-color: ${primaryColor}; }
    .aether-widget .aether-composer button { width: 36px; height: 36px; border-radius: 50%; border: none; background: ${primaryColor}; color: white; cursor: pointer; display: flex; align-items: center; justify-content: center; }
    .aether-widget .aether-composer button:disabled { opacity: 0.5; cursor: not-allowed; }
    @media (max-width: 480px) { .aether-widget .aether-panel { width: calc(100vw - 40px); right: -4px; height: calc(100vh - 100px); } }
  `;

  // ── DOM ───────────────────────────────────────────────────
  const styleEl = document.createElement('style');
  styleEl.textContent = css;
  document.head.appendChild(styleEl);

  const container = document.createElement('div');
  container.className = 'aether-widget';
  container.innerHTML = `
    <button class="aether-button" id="aether-btn">
      <svg viewBox="0 0 24 24"><path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm0 14H5.2L4 17.2V4h16v12z"/><path d="M7 9h10M7 12h7"/></svg>
    </button>
    <div class="aether-panel" id="aether-panel">
      <div class="aether-header">
        <h3>Chat with us</h3>
        <span style="font-size:11px;opacity:0.8" id="aether-status">${isConnected ? '● Online' : '○ Offline'}</span>
        <button class="aether-close" id="aether-close">✕</button>
      </div>
      <div class="aether-body" id="aether-body">
        <div class="aether-msg bot">${greeting}</div>
      </div>
      <div class="aether-composer">
        <input type="text" id="aether-input" placeholder="Type a message..." />
        <button id="aether-send" disabled>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="white"><path d="M2 21l21-9L2 3v7l15 2-15 2v7z"/></svg>
        </button>
      </div>
    </div>
  `;
  document.body.appendChild(container);

  // ── Elements ──────────────────────────────────────────────
  const btn = document.getElementById('aether-btn');
  const panel = document.getElementById('aether-panel');
  const closeBtn = document.getElementById('aether-close');
  const body = document.getElementById('aether-body');
  const input = document.getElementById('aether-input');
  const sendBtn = document.getElementById('aether-send');
  const statusEl = document.getElementById('aether-status');

  // ── WebSocket ─────────────────────────────────────────────
  function connect() {
    const wsUrl = host.replace(/^http/, 'ws') + '/ws/widget/' + tenantId + (token ? '?token=' + token : '');
    try {
      ws = new WebSocket(wsUrl);
      ws.onopen = () => { isConnected = true; statusEl.textContent = '● Online'; statusEl.style.opacity = '1'; sendBtn.disabled = false; };
      ws.onmessage = (e) => {
        try {
          const msg = JSON.parse(e.data);
          if (msg.type === 'message') appendMessage(msg.content, 'bot');
          else if (msg.type === 'quick_replies') showQuickReplies(msg.content, msg.buttons);
          else if (msg.type === 'typing') showTyping();
        } catch (e) {}
      };
      ws.onclose = () => { isConnected = false; statusEl.textContent = '○ Offline'; statusEl.style.opacity = '0.8'; sendBtn.disabled = true; scheduleReconnect(); };
      ws.onerror = () => ws.close();
    } catch (e) {}
  }

  function scheduleReconnect() {
    if (reconnectTimer) clearTimeout(reconnectTimer);
    reconnectTimer = setTimeout(connect, 3000);
  }

  // ── UI ────────────────────────────────────────────────────
  btn.addEventListener('click', () => {
    isOpen = true;
    panel.classList.add('open');
    btn.style.display = 'none';
    if (!ws) connect();
  });

  closeBtn.addEventListener('click', () => {
    isOpen = false;
    panel.classList.remove('open');
    btn.style.display = 'flex';
  });

  function appendMessage(text, role) {
    const div = document.createElement('div');
    div.className = 'aether-msg ' + role;
    div.textContent = text;
    body.appendChild(div);
    body.scrollTop = body.scrollHeight;
    messages.push({ role, content: text });
  }

  function showTyping() {
    const div = document.createElement('div');
    div.className = 'aether-typing';
    div.innerHTML = '<span></span><span></span><span></span>';
    div.id = 'aether-typing';
    body.appendChild(div);
    body.scrollTop = body.scrollHeight;
    setTimeout(() => { const el = document.getElementById('aether-typing'); if (el) el.remove(); }, 2000);
  }

  function showQuickReplies(content, buttons) {
    appendMessage(content, 'bot');
    const row = document.createElement('div');
    row.style.cssText = 'display:flex;flex-wrap:wrap;gap:6px;padding:4px 0';
    buttons.forEach(btn => {
      const b = document.createElement('button');
      b.textContent = btn;
      b.style.cssText = 'padding:6px 14px;border-radius:16px;border:1px solid ${primaryColor};background:white;color:${primaryColor};font-size:12px;cursor:pointer';
      b.addEventListener('click', () => { sendMessage(btn); b.remove(); });
      row.appendChild(b);
    });
    body.appendChild(row);
    body.scrollTop = body.scrollHeight;
  }

  // ── Send ──────────────────────────────────────────────────
  function sendMessage(text) {
    if (!text.trim() || !isConnected) return;
    appendMessage(text, 'user');
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'chat.message', content: text }));
    }
  }

  sendBtn.addEventListener('click', () => { sendMessage(input.value); input.value = ''; });
  input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') { sendMessage(input.value); input.value = ''; }
  });

  // ── Public API ────────────────────────────────────────────
  window.AetherWidget = {
    open: () => { isOpen = true; panel.classList.add('open'); btn.style.display = 'none'; if (!ws) connect(); },
    close: () => { isOpen = false; panel.classList.remove('open'); btn.style.display = 'flex'; },
    send: (text) => sendMessage(text),
    setToken: (t) => { token = t; if (ws) { ws.close(); connect(); } },
    isOpen: () => isOpen,
    isConnected: () => isConnected,
  };

  // ── Auto-connect ──────────────────────────────────────────
  if (script.getAttribute('data-auto-open') === 'true') {
    setTimeout(() => { window.AetherWidget.open(); }, 1000);
  }
})();
