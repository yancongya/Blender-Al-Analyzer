import { API_BASE } from './state.js';

export async function testConnection() {
  const res = await fetch(`${API_BASE}/api/test-connection`);
  return res.json();
}

export async function fetchMessages() {
  const res = await fetch(`${API_BASE}/api/get-messages`);
  if (!res.ok) throw new Error('Failed to fetch history');
  return res.json();
}

export async function clearMessages() {
  const res = await fetch(`${API_BASE}/api/clear-messages`, { method: 'POST' });
  if (!res.ok) throw new Error('Failed to clear history');
  return res.json();
}

export async function triggerBlenderRefresh() {
  const res = await fetch(`${API_BASE}/api/trigger-blender-refresh`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ action: 'refresh_nodes' })
  });
  if (!res.ok) throw new Error('Failed to trigger Blender refresh');
  return res.json();
}

export async function getBlenderData() {
  const res = await fetch(`${API_BASE}/api/blender-data`, {
    method: 'GET',
    headers: { 'Content-Type': 'application/json' }
  });
  if (!res.ok) throw new Error('Failed to fetch Blender data');
  return res.json();
}

export async function pushWebContent({ content, question }) {
  const res = await fetch(`${API_BASE}/api/push-web-content`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ content, question, action: 'push_question_to_blender' })
  });
  if (!res.ok) throw new Error('Failed to push to Blender');
  return res.json();
}

export async function streamAiResponse({ question, content, onData }) {
  const res = await fetch(`${API_BASE}/api/stream-analyze`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question, content })
  });
  if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n\n');
    buffer = lines.pop();
    for (const line of lines) {
      if (line.startsWith('data: ')) {
        try {
          const data = JSON.parse(line.slice(6));
          onData?.(data);
        } catch {}
      }
    }
  }

  if (buffer.trim()) {
    try {
      const data = JSON.parse(buffer.slice(6));
      onData?.(data);
    } catch {}
  }
}
