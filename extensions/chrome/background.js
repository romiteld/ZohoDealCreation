// Reuse the Edge Graph flow for Chrome via chrome.identity
const CONFIG = {
  clientId: 'c2435c27-41f3-4a3a-b400-7406518bb415',
  tenantId: '29ee1479-b5f7-48c5-b665-7de9a8a9033e',
  scopes: ['openid', 'profile', 'offline_access', 'User.Read', 'Mail.Read']
};

chrome.runtime.onInstalled.addListener(() => {});

async function getGraphTokenInteractive() {
  return new Promise((resolve, reject) => {
    const redirectUrl = 'https://login.microsoftonline.com/common/oauth2/nativeclient';
    const authBase = `https://login.microsoftonline.com/${encodeURIComponent(CONFIG.tenantId)}/oauth2/v2.0/authorize`;
    const params = new URLSearchParams({
      client_id: CONFIG.clientId,
      response_type: 'token',
      response_mode: 'fragment',
      redirect_uri: redirectUrl,
      scope: CONFIG.scopes.join(' '),
      prompt: 'select_account'
    });
    const authUrl = `${authBase}?${params.toString()}`;
    chrome.identity.launchWebAuthFlow({ url: authUrl, interactive: true }, (responseUrl) => {
      if (chrome.runtime.lastError) return reject(chrome.runtime.lastError);
      if (!responseUrl || responseUrl.includes('error=')) return reject(new Error('Auth failed'));
      const frag = responseUrl.split('#')[1] || '';
      const params = new URLSearchParams(frag);
      const accessToken = params.get('access_token');
      if (!accessToken) return reject(new Error('No access token'));
      resolve(accessToken);
    });
  });
}

async function graphGetMeMessage(token, messageId) {
  const res = await fetch(`https://graph.microsoft.com/v1.0/me/messages/${encodeURIComponent(messageId)}?$select=subject,from,bodyPreview,body`, {
    headers: { Authorization: `Bearer ${token}` }
  });
  if (!res.ok) throw new Error(`Graph ${res.status}`);
  return res.json();
}

async function graphListMessages(token) {
  const res = await fetch('https://graph.microsoft.com/v1.0/me/messages?$top=10&$select=id,subject,from,bodyPreview,conversationId', {
    headers: { Authorization: `Bearer ${token}` }
  });
  if (!res.ok) throw new Error(`Graph ${res.status}`);
  const data = await res.json();
  return data.value || [];
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
      const token = await getGraphTokenInteractive();
      let message;
      let conversation = [];
      if (msg.messageId) {
        message = await graphGetMeMessage(token, msg.messageId);
        if (message?.conversationId) {
          conversation = await graphGetConversation(token, message.conversationId);
        }
      } else {
        const list = await graphListMessages(token);
        const latest = list?.[0];
        message = latest ? await graphGetMeMessage(token, latest.id) : null;
        if (latest?.conversationId) {
          conversation = await graphGetConversation(token, latest.conversationId);
        }
      }
      sendResponse({ ok: true, token, message, conversation });
    }
  })().catch(e => sendResponse({ ok: false, error: e?.message || String(e) }));
  return true;
});


