(() => {
  const statusEl = document.getElementById('status');
  const sendBtn = document.getElementById('sendBtn');
  const previewBtn = document.getElementById('previewBtn');
  const formEl = document.getElementById('form');

  function setStatus(message, kind = 'info') {
    statusEl.textContent = message;
    statusEl.className = `status ${kind === 'error' ? 'err' : 'ok'}`;
  }

  function fillForm(data) {
    const set = (id, v) => { const el = document.getElementById(id); if (el) el.value = v || ''; };
    set('candidateName', data.candidateName || data.candidate_name);
    set('candidateEmail', data.candidateEmail || data.email || data.candidate_email);
    set('candidatePhone', data.candidatePhone || data.phone);
    set('linkedinUrl', data.linkedinUrl || data.linkedin_url);
    set('jobTitle', data.jobTitle || data.job_title);
    set('location', data.location);
    set('companyName', data.companyName || data.company_name);
    set('notes', data.notes);
  }

  function readForm() {
    const get = (id) => document.getElementById(id)?.value?.trim() || '';
    return {
      candidate_name: get('candidateName'),
      candidate_email: get('candidateEmail'),
      phone: get('candidatePhone'),
      linkedin_url: get('linkedinUrl'),
      job_title: get('jobTitle'),
      location: get('location'),
      company_name: get('companyName'),
      notes: get('notes')
    };
  }

  const API_BASE_URL = 'https://well-intake-api.wittyocean-dfae0f9b.eastus.azurecontainerapps.io';
  const API_KEY = 'e49d2dbcfa4547f5bdc371c5c06aae2afd06914e16e680a7f31c5fc5384ba384';

  async function previewCurrentEmail() {
    try {
      previewBtn.disabled = true;
      setStatus('Signing in to Microsoft Graph...');
      const graph = await new Promise((resolve, reject) => {
        chrome.runtime.sendMessage({ type: 'edge.sendCurrentEmailGraph' }, (resp) => {
          if (!resp?.ok) return reject(new Error(resp?.error || 'Graph failed'));
          resolve(resp);
        });
      });

      const emailData = (function mapGraph(m) {
        if (!m) return null;
        const from = {
          displayName: m.from?.emailAddress?.name || '',
          emailAddress: m.from?.emailAddress?.address || ''
        };
        const subject = m.subject || '';
        const body = (m.body?.content || m.bodyPreview || '').toString().slice(0, 15000);
        return { subject, from, body };
      })(graph.message);

      if (!emailData) throw new Error('No current message found.');

      setStatus('Requesting AI extraction (preview)...');
      const headers = { 'Content-Type': 'application/json', 'X-API-Key': API_KEY };
      const resp = await fetch(`${API_BASE_URL}/intake/email`, {
        method: 'POST',
        headers,
        body: JSON.stringify({
          sender_email: emailData.from?.emailAddress || '',
          sender_name: emailData.from?.displayName || '',
          subject: emailData.subject || '',
          body: emailData.body || '',
          dry_run: true,
          graph_access_token: graph?.token || undefined,
          graph_message_id: graph?.message?.id || undefined,
          graph_conversation_id: graph?.message?.conversationId || undefined
        })
      });
      if (!resp.ok) throw new Error(`API ${resp.status}`);
      const result = await resp.json();
      if (result?.extracted) {
        fillForm(result.extracted);
        formEl.style.display = 'block';
        setStatus('Review and edit, then click Send');
      } else {
        setStatus('No extraction returned', 'error');
      }
    } catch (e) {
      setStatus(e.message || 'Failed', 'error');
    } finally {
      previewBtn.disabled = false;
    }
  }

  async function sendCurrentEmail() {
    try {
      sendBtn.disabled = true;
      setStatus('Signing in to Microsoft Graph...');
      const graph = await new Promise((resolve, reject) => {
        chrome.runtime.sendMessage({ type: 'edge.sendCurrentEmailGraph' }, (resp) => {
          if (!resp?.ok) return reject(new Error(resp?.error || 'Graph failed'));
          resolve(resp);
        });
      });

      const emailData = (function mapGraph(m) {
        if (!m) return null;
        const from = {
          displayName: m.from?.emailAddress?.name || '',
          emailAddress: m.from?.emailAddress?.address || ''
        };
        const subject = m.subject || '';
        const body = (m.body?.content || m.bodyPreview || '').toString().slice(0, 15000);
        return { subject, from, body };
      })(graph.message);

      if (!emailData) throw new Error('No current message found.');

      setStatus('Sending to The Well API...');
      const headers = { 'Content-Type': 'application/json', 'X-API-Key': API_KEY };
      const resp = await fetch(`${API_BASE_URL}/intake/email`, {
        method: 'POST',
        headers,
        body: JSON.stringify({
          sender_email: emailData.from?.emailAddress || '',
          sender_name: emailData.from?.displayName || '',
          subject: emailData.subject || '',
          body: emailData.body || '',
          ai_extraction: {},
          user_corrections: readForm(),
          graph_access_token: graph?.token || undefined,
          graph_message_id: graph?.message?.id || undefined,
          graph_conversation_id: graph?.message?.conversationId || undefined
        })
      });
      if (!resp.ok) throw new Error(`API ${resp.status}`);
      const result = await resp.json();
      setStatus(result?.message || 'Sent to Zoho successfully.');
    } catch (e) {
      setStatus(e.message || 'Failed', 'error');
    } finally {
      sendBtn.disabled = false;
    }
  }

  previewBtn.addEventListener('click', previewCurrentEmail);
  sendBtn.addEventListener('click', sendCurrentEmail);
})();


