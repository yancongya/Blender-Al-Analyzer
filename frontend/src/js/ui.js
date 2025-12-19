import { els } from './state.js';

export function updateStatusBar(message, type = 'normal') {
  els.statusBar.textContent = message;
  els.statusBar.classList.toggle('status-bar--error', type === 'error');
}

export function fillTextarea(content) {
  els.questionInput.value = content || '';
}

export function setButtonsState({ sending }) {
  els.sendBtn.disabled = !!sending;
  els.stopBtn.disabled = !sending;
}
