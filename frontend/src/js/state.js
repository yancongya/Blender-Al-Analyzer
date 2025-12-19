export const API_BASE = 'http://127.0.0.1:5000';

export const els = {
  responseContainer: document.getElementById('responseContainer'),
  sendContainer: document.getElementById('sendContainer'),
  questionInput: document.getElementById('questionInput'),
  refreshBtn: document.getElementById('refreshBtn'),
  sendBtn: document.getElementById('sendBtn'),
  stopBtn: document.getElementById('stopBtn'),
  statusBar: document.getElementById('statusBar'),
  blenderRefreshBtn: document.getElementById('blenderRefreshBtn'),
  historyList: document.getElementById('historyList')
};

export let originalNodeData = '';
export function setOriginalNodeData(v) { originalNodeData = v; }

export let connectionStatus = 'idle';
export function setConnectionStatus(v) { connectionStatus = v; }
