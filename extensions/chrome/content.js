// Inject a small floating button on Outlook Web
(function () {
  const BTN_ID = 'well-sendtozoho-btn';
  if (document.getElementById(BTN_ID)) return;
  const btn = document.createElement('button');
  btn.id = BTN_ID;
  btn.textContent = 'Send to Zoho';
  Object.assign(btn.style, {
    position: 'fixed', right: '16px', bottom: '16px', zIndex: '2147483647',
    background: '#2563eb', color: '#fff', border: 'none', borderRadius: '8px',
    padding: '10px 12px', boxShadow: '0 4px 12px rgba(0,0,0,0.2)', cursor: 'pointer', fontFamily: 'system-ui, Arial'
  });
  btn.addEventListener('click', async () => {
    try {
      // Ask background to open popup (user gesture already present by this click)
      await chrome.runtime.sendMessage({ type: 'edge.openPopup' });
    } catch (_) {}
  });
  document.body.appendChild(btn);
})();


// Provide lightweight hints (subject/from) from the currently viewed message
chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  (async () => {
    if (msg && msg.type === 'getOutlookMessageHint') {
      try {
        const hint = { subject: '', fromEmail: '', bodySnippet: '' };
        // Subject heuristics
        const subjectEl = document.querySelector('[data-test-id="message-subject"], [data-automationid="messageSubject"], h1[role="heading"], h2[role="heading"]');
        if (subjectEl && subjectEl.textContent) hint.subject = subjectEl.textContent.trim();
        if (!hint.subject && document.title) hint.subject = document.title.replace(/ - Outlook( Web)?/i, '').trim();
        // From email heuristics: pick first mailto in reading pane/content area
        const mailtoEl = document.querySelector('a[href^="mailto:"]');
        if (mailtoEl) {
          try { hint.fromEmail = new URL(mailtoEl.href).pathname.replace(/^\//, '').trim(); } catch(_) {}
        }
        // Body snippet heuristics: visible reading pane text
        let bodyRoot = document.querySelector('[role="document"], div[aria-label="Message body"], .ReadingPane, .content');
        if (!bodyRoot) bodyRoot = document.body;
        const text = (bodyRoot?.innerText || '').replace(/\s+/g, ' ').trim();
        if (text) hint.bodySnippet = text.slice(0, 300);
        sendResponse({ ok: true, hint });
      } catch (e) {
        sendResponse({ ok: false, error: e?.message || String(e) });
      }
    }
  })();
  return true;
});

