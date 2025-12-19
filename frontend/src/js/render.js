import { els } from './state.js';

function appendParagraph(text, strong = false, em = false) {
  const p = document.createElement('p');
  if (strong) {
    const b = document.createElement('strong');
    b.textContent = text;
    p.appendChild(b);
  } else if (em) {
    const i = document.createElement('em');
    i.textContent = text;
    p.appendChild(i);
  } else {
    p.textContent = text;
  }
  els.responseContainer.appendChild(p);
  els.responseContainer.scrollTop = els.responseContainer.scrollHeight;
}

function renderCodeBlock(code) {
  const pre = document.createElement('pre');
  const codeEl = document.createElement('code');
  codeEl.textContent = code;
  pre.appendChild(codeEl);
  els.responseContainer.appendChild(pre);
  els.responseContainer.scrollTop = els.responseContainer.scrollHeight;
}

export function renderStart(message) { appendParagraph(message, false, true); }
export function renderProgress(message) { appendParagraph(message, false, true); }
export function renderChunk(content) {
  const triple = content.match(/^```[\s\S]*\n([\s\S]*?)\n```$/);
  if (triple) {
    renderCodeBlock(triple[1]);
  } else {
    appendParagraph(content);
  }
}
export function renderComplete(message) { appendParagraph(message, true, false); }
export function renderError(message) {
  const p = document.createElement('p');
  p.style.color = 'red';
  p.textContent = `错误: ${message}`;
  els.responseContainer.appendChild(p);
  els.responseContainer.scrollTop = els.responseContainer.scrollHeight;
}
export function clearResponse() { els.responseContainer.innerHTML = ''; }
export function showResponseSkeleton() {
  els.responseContainer.innerHTML = '';
  for (let i = 0; i < 3; i++) {
    const s = document.createElement('div');
    s.className = 'skeleton';
    s.style.height = '16px';
    s.style.marginBottom = '8px';
    els.responseContainer.appendChild(s);
  }
}
