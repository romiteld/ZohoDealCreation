// Microsoft Graph OAuth (PKCE) in a Chrome extension service worker
const CONFIG = {
  clientId: 'c2435c27-41f3-4a3a-b400-7406518bb415',
  authority: 'https://login.microsoftonline.com/common',
  scopes: ['openid', 'profile', 'offline_access', 'User.Read', 'Mail.Read']
};

chrome.runtime.onInstalled.addListener(() => {});

// Utility: PKCE code verifier/challenge
async function sha256(base) {
  const encoder = new TextEncoder();
  const data = encoder.encode(base);
  const digest = await crypto.subtle.digest('SHA-256', data);
  return btoa(String.fromCharCode(...new Uint8Array(digest)))
    .replace(/\+/g, '-')
    .replace(/\//g, '_')
    .replace(/=+$/, '');
}

function randomString(len = 64) {
  const charset = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~';
  let result = '';
  const values = crypto.getRandomValues(new Uint8Array(len));
  for (let i = 0; i < len; i++) result += charset[values[i] % charset.length];
  return result;
}

async function buildPkce() {
  const verifier = randomString(64);
  const challenge = await sha256(verifier);
  return { verifier, challenge };
}

function getRedirectUri() {
  // Chrome Identity uses this fixed pattern for extensions
  return `https://${chrome.runtime.id}.chromiumapp.org/`; 
}

async function exchangeCodeForToken(code, codeVerifier) {
  const tokenUrl = `${CONFIG.authority}/oauth2/v2.0/token`;
  const body = new URLSearchParams({
    client_id: CONFIG.clientId,
    grant_type: 'authorization_code',
    code,
    redirect_uri: getRedirectUri(),
    code_verifier: codeVerifier,
    scope: CONFIG.scopes.join(' ')
  });
  const res = await fetch(tokenUrl, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: body.toString()
  });
  if (!res.ok) throw new Error(`Token exchange failed: ${res.status}`);
  return res.json();
}

async function refreshAccessToken(refreshToken) {
  const tokenUrl = `${CONFIG.authority}/oauth2/v2.0/token`;
  const body = new URLSearchParams({
    client_id: CONFIG.clientId,
    grant_type: 'refresh_token',
    refresh_token: refreshToken,
    scope: CONFIG.scopes.join(' ')
  });
  const res = await fetch(tokenUrl, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: body.toString()
  });
  if (!res.ok) throw new Error(`Token refresh failed: ${res.status}`);
  return res.json();
}

async function getValidGraphToken() {
  // Try cached token
  const { access_token, refresh_token, expires_at } = (await chrome.storage.local.get([
    'access_token', 'refresh_token', 'expires_at'
  ])) || {};
  const now = Math.floor(Date.now() / 1000);
  if (access_token && expires_at && now < (expires_at - 60)) {
    return access_token;
  }
  if (refresh_token) {
    try {
      const refreshed = await refreshAccessToken(refresh_token);
      const exp = now + (refreshed.expires_in || 3600);
      await chrome.storage.local.set({
        access_token: refreshed.access_token,
        refresh_token: refreshed.refresh_token || refresh_token,
        expires_at: exp
      });
      return refreshed.access_token;
    } catch (e) {
      // Fall through to full auth
      console.warn('Refresh failed, starting full auth:', e?.message || e);
    }
  }

  // Full interactive auth using Auth Code + PKCE
  const { verifier, challenge } = await buildPkce();
  const authUrl = new URL(`${CONFIG.authority}/oauth2/v2.0/authorize`);
  authUrl.search = new URLSearchParams({
    client_id: CONFIG.clientId,
    response_type: 'code',
    redirect_uri: getRedirectUri(),
    // Prefer query; we still parse fragment as a fallback
    response_mode: 'query',
    scope: CONFIG.scopes.join(' '),
    code_challenge: challenge,
    code_challenge_method: 'S256',
    // Use a single supported prompt value to avoid AADSTS90023
    prompt: 'select_account'
  }).toString();

  const responseUrl = await new Promise((resolve, reject) => {
    chrome.identity.launchWebAuthFlow({ url: authUrl.toString(), interactive: true }, (url) => {
      if (chrome.runtime.lastError) return reject(chrome.runtime.lastError);
      if (!url) return reject(new Error('No response URL'));
      try {
        const u = new URL(url);
        const err = u.searchParams.get('error') || (url.split('#')[1] && new URLSearchParams(url.split('#')[1]).get('error'));
        const errDesc = u.searchParams.get('error_description') || (url.split('#')[1] && new URLSearchParams(url.split('#')[1]).get('error_description'));
        if (err) return reject(new Error(`${err}: ${decodeURIComponent(errDesc || '')}`));
      } catch (_) {}
      console.log('[Send to Zoho] Auth redirect:', url);
      resolve(url);
    });
  });

  const parsed = new URL(responseUrl);
  let code = parsed.searchParams.get('code');
  if (!code) {
    const frag = responseUrl.split('#')[1] || '';
    const fp = new URLSearchParams(frag);
    code = fp.get('code');
  }
  if (!code) throw new Error('Authorization code not returned');

  const tokenSet = await exchangeCodeForToken(code, verifier);
  const exp = Math.floor(Date.now() / 1000) + (tokenSet.expires_in || 3600);
  await chrome.storage.local.set({
    access_token: tokenSet.access_token,
    refresh_token: tokenSet.refresh_token,
    expires_at: exp
  });
  return tokenSet.access_token;
}

async function graphGetMeMessage(token, messageId) {
  const res = await fetch(`https://graph.microsoft.com/v1.0/me/messages/${encodeURIComponent(messageId)}?$select=subject,from,bodyPreview,body,webLink,conversationId`, {
    headers: { Authorization: `Bearer ${token}` }
  });
  if (!res.ok) throw new Error(`Graph ${res.status}`);
  return res.json();
}

async function graphListMessages(token) {
  const url = 'https://graph.microsoft.com/v1.0/me/messages?$top=50&$select=id,subject,from,bodyPreview,webLink,conversationId,receivedDateTime&$orderby=receivedDateTime%20desc';
  const res = await fetch(url, { headers: { Authorization: `Bearer ${token}` } });
  if (!res.ok) throw new Error(`Graph ${res.status}`);
  const data = await res.json();
  return data.value || [];
}

function extractItemIdFromOutlookUrl(rawUrl) {
  try {
    const u = new URL(rawUrl);
    const itemIdParam = u.searchParams.get('itemid');
    if (itemIdParam) return decodeURIComponent(itemIdParam);
    const m = u.pathname.match(/\/mail\/.+\/id\/([^/?]+)(?:[/?]|$)/);
    if (m && m[1]) return decodeURIComponent(m[1]);
  } catch (_) {}
  return null;
}

async function getActiveOutlookTab() {
  const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
  const tab = tabs && tabs[0];
  if (!tab || !tab.url) return null;
  const isOutlook = /https:\/\/(outlook\.office\.com|outlook\.office365\.com)\//.test(tab.url);
  return isOutlook ? tab : null;
}

async function findMessageByActiveTabUrl(token) {
  const tab = await getActiveOutlookTab();
  if (!tab) return null;
  const itemId = extractItemIdFromOutlookUrl(tab.url);
  if (!itemId) return null;
  const list = await graphListMessages(token);
  const target = (list || []).find(m => {
    const wl = decodeURIComponent(m.webLink || '');
    return wl.includes(itemId);
  });
  return target || null;
}

async function findMessageByHint(token) {
  try {
    const tab = await getActiveOutlookTab();
    if (!tab) return null;
    const hint = await chrome.tabs.sendMessage(tab.id, { type: 'getOutlookMessageHint' });
    if (!hint?.ok) return null;
    const subject = (hint.hint?.subject || '').toLowerCase();
    const fromEmail = (hint.hint?.fromEmail || '').toLowerCase();
    const bodySnippet = (hint.hint?.bodySnippet || '').toLowerCase();
    if (!subject && !fromEmail && !bodySnippet) return null;
    const list = await graphListMessages(token);
    let best = null;
    let bestScore = -1;
    for (const m of (list || [])) {
      const s = (m.subject || '').toLowerCase();
      const f = (m.from?.emailAddress?.address || '').toLowerCase();
      const b = (m.bodyPreview || '').toLowerCase();
      let score = 0;
      if (subject && s && s.includes(subject.substring(0, Math.min(25, subject.length)))) score += 2;
      if (fromEmail && f && f === fromEmail) score += 2;
      if (bodySnippet && b) {
        const snippet = bodySnippet.substring(0, Math.min(50, bodySnippet.length));
        if (b.includes(snippet)) score += 1;
      }
      if (score > bestScore) { bestScore = score; best = m; }
    }
    return best;
  } catch (_) {
    return null;
  }
}

async function findMessageBySearch(token) {
  try {
    const tab = await getActiveOutlookTab();
    if (!tab) return null;
    const hint = await chrome.tabs.sendMessage(tab.id, { type: 'getOutlookMessageHint' });
    if (!hint?.ok) return null;
    const subject = (hint.hint?.subject || '').replace(/\"/g, '').trim();
    const fromEmail = (hint.hint?.fromEmail || '').trim();
    // Need at least one term to search
    if (!subject && !fromEmail) return null;
    const subjectSnippet = subject ? subject.slice(0, 32) : '';
    let searchQuery = '';
    if (subjectSnippet) searchQuery += `subject:\"${subjectSnippet}\"`;
    if (fromEmail) searchQuery += (searchQuery ? ' ' : '') + `from:${fromEmail}`;
    const url = `https://graph.microsoft.com/v1.0/me/messages?$search=${encodeURIComponent(searchQuery)}&$top=25&$select=id,subject,from,bodyPreview,webLink,conversationId,receivedDateTime&$orderby=receivedDateTime%20desc`;
    const res = await fetch(url, {
      headers: {
        Authorization: `Bearer ${token}`,
        'ConsistencyLevel': 'eventual',
        'Prefer': 'outlook.body-content-type="text"'
      }
    });
    if (!res.ok) return null;
    const data = await res.json();
    const list = data.value || [];
    // If multiple, choose best by simple scoring vs hints
    let best = null;
    let bestScore = -1;
    const subjLower = (subjectSnippet || '').toLowerCase();
    const fromLower = (fromEmail || '').toLowerCase();
    for (const m of list) {
      let score = 0;
      const s = (m.subject || '').toLowerCase();
      const f = (m.from?.emailAddress?.address || '').toLowerCase();
      if (subjLower && s.includes(subjLower)) score += 2;
      if (fromLower && f === fromLower) score += 2;
      if (score > bestScore) { bestScore = score; best = m; }
    }
    return best;
  } catch (_) {
    return null;
  }
}

async function graphGetConversation(token, conversationId) {
  const url = `https://graph.microsoft.com/v1.0/me/messages?$filter=conversationId eq '${conversationId}'&$top=5&$select=id,subject,from,receivedDateTime,bodyPreview`;
  const res = await fetch(url, { headers: { Authorization: `Bearer ${token}` } });
  if (!res.ok) throw new Error(`Graph ${res.status}`);
  const data = await res.json();
  return data.value || [];
}

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  (async () => {
    if (msg?.type === 'edge.sendCurrentEmailGraph') {
      const token = await getValidGraphToken();
      let message;
      let conversation = [];
      if (msg.messageId) {
        message = await graphGetMeMessage(token, msg.messageId);
        if (message?.conversationId) {
          conversation = await graphGetConversation(token, message.conversationId);
        }
      } else {
        // Try to match the currently viewed Outlook message via the active tab URL
        let matched = await findMessageByActiveTabUrl(token);
        if (!matched) {
          // Fallback: use subject/from/body hints scraped by content script
          // First, Graph $search (subject/from) for a precise match
          matched = await findMessageBySearch(token) || await findMessageByHint(token);
        }
        if (matched) {
          message = await graphGetMeMessage(token, matched.id);
          if (matched?.conversationId) {
            conversation = await graphGetConversation(token, matched.conversationId);
          }
        } else {
          // No match; return a clear error instead of using the latest message
          throw new Error('No current message detected. Open the email, then click Preview again.');
        }
      }
      sendResponse({ ok: true, token, message, conversation });
    } else if (msg?.type === 'edge.openPopup') {
      try {
        await chrome.action.openPopup();
        sendResponse({ ok: true });
      } catch (e) {
        sendResponse({ ok: false, error: e?.message || String(e) });
      }
    }
  })().catch(e => sendResponse({ ok: false, error: e?.message || String(e) }));
  return true;
});



// Pre-auth and badge when on Outlook Web
async function handleTab(tabId) {
  try {
    const tab = await chrome.tabs.get(tabId);
    if (!tab?.url) return;
    const isOutlook = /https:\/\/(outlook\.office\.com|outlook\.office365\.com)\//.test(tab.url);
    if (isOutlook) {
      chrome.action.setBadgeText({ tabId, text: '•' });
      chrome.action.setBadgeBackgroundColor({ tabId, color: '#2563eb' });
      // Pre-warm Graph auth silently
      try { await getValidGraphToken(); } catch (_) {}
    } else {
      chrome.action.setBadgeText({ tabId, text: '' });
    }
  } catch (_) {}
}

chrome.tabs.onActivated.addListener(({ tabId }) => handleTab(tabId));
chrome.tabs.onUpdated.addListener((tabId, changeInfo) => {
  if (changeInfo.status === 'complete' || changeInfo.url) handleTab(tabId);
});

