// 配置
const API_BASE = 'http://127.0.0.1:5000';
let currentEventSource = null;

// DOM元素
const responseContainer = document.getElementById('responseContainer');
const sendContainer = document.getElementById('sendContainer');
const questionInput = document.getElementById('questionInput');
const refreshBtn = document.getElementById('refreshBtn');
const sendBtn = document.getElementById('sendBtn');
const stopBtn = document.getElementById('stopBtn');
const statusBar = document.getElementById('statusBar');
const blenderRefreshBtn = document.getElementById('blenderRefreshBtn');
const historyList = document.getElementById('historyList');

window.onload = function() {
  updateStatusBar('就绪 - 连接后端服务器...');
  testConnection();
  fetchAndDisplayHistory();
  addClearHistoryListener();
};

async function fetchAndDisplayHistory() {
  try {
    const response = await fetch(`${API_BASE}/api/get-messages`);
    if (!response.ok) return;
    const data = await response.json();
    historyList.innerHTML = '';
    if (data.messages && data.messages.length > 0) {
      data.messages.forEach(msg => {
        const li = document.createElement('li');
        const question = msg.message || 'No question';
        li.textContent = question.substring(0, 30) + (question.length > 30 ? '...' : '');
        li.dataset.fullMessage = JSON.stringify(msg);
        li.addEventListener('click', () => {
          const fullMsg = JSON.parse(li.dataset.fullMessage);
          responseContainer.innerHTML = `<p>${fullMsg.response || 'No response found.'}</p>`;
          questionInput.value = fullMsg.message || '';
        });
        historyList.appendChild(li);
      });
    } else {
      historyList.innerHTML = '<li>没有历史记录</li>';
    }
  } catch (error) {
    historyList.innerHTML = '<li>加载历史记录失败</li>';
  }
}

function addClearHistoryListener() {
  const clearBtn = document.createElement('button');
  clearBtn.textContent = '清空历史';
  clearBtn.className = 'clear-btn';
  const historyPanel = document.querySelector('.history-panel');
  if(historyPanel) {
    historyPanel.appendChild(clearBtn);
    clearBtn.addEventListener('click', async () => {
      if (!confirm('确定要清空所有对话历史吗？')) return;
      try {
        const response = await fetch(`${API_BASE}/api/clear-messages`, { method: 'POST' });
        if (response.ok) {
          fetchAndDisplayHistory();
          updateStatusBar('对话历史已清空');
        } else {
          updateStatusBar('清空历史失败');
        }
      } catch {
        updateStatusBar('清空历史时出错');
      }
    });
  }
}

async function testConnection() {
  try {
    const response = await fetch(`${API_BASE}/api/test-connection`);
    const data = await response.json();
    updateStatusBar(`已连接 - ${data.message}`);
  } catch (error) {
    updateStatusBar(`连接失败: ${error.message}`);
  }
}

function updateStatusBar(message) { statusBar.textContent = message; }

async function refreshContent() {
  updateStatusBar('正在触发Blender刷新...');
  try {
    const triggerResponse = await fetch(`${API_BASE}/api/trigger-blender-refresh`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ action: 'refresh_nodes' })
    });
    if (triggerResponse.ok) {
      updateStatusBar('Blender刷新已触发，正在获取内容...');
      await new Promise(resolve => setTimeout(resolve, 1000));
      const response = await fetch(`${API_BASE}/api/blender-data`, { method: 'GET', headers: { 'Content-Type': 'application/json' } });
      if (response.ok) {
        const data = await response.json();
        const content = data.nodes || '暂无数据';
        const currentText = questionInput.value;
        const questionMatch = currentText.match(/用户问题:\s*\n*([\s\S]*)/);
        const currentQuestion = questionMatch ? questionMatch[1].trim() : '';
        let newSendContent = content !== '暂无数据' ? `节点数据:\n${content}` : '';
        if (currentQuestion) newSendContent = newSendContent ? `${newSendContent}\n\n用户问题:\n${currentQuestion}` : `用户问题:\n${currentQuestion}`;
        questionInput.value = newSendContent || '发送内容将显示在此处...';
        updateStatusBar('内容已刷新');
      } else {
        questionInput.value = '无法从Blender获取数据，请确保Blender插件正在运行';
        updateStatusBar('未获取到数据');
      }
    } else {
      updateStatusBar('触发Blender刷新失败');
    }
  } catch (error) {
    questionInput.value = `刷新失败: ${error.message}`;
    updateStatusBar('刷新失败: ' + error.message);
  }
}

async function sendQuestion() {
  const currentContent = questionInput.value;
  const nodeDataMatch = currentContent.match(/节点数据:\s*\n*([\s\S]*?)(?=\n\s*用户问题:|$)/);
  const questionMatch = currentContent.match(/用户问题:\s*\n*([\s\S]*)/);
  const contentToSend = nodeDataMatch ? nodeDataMatch[1].trim() : '';
  const question = questionMatch ? questionMatch[1].trim() : '';
  if (!question) { updateStatusBar('请输入问题'); return; }
  if (!contentToSend || contentToSend === '暂无数据') { updateStatusBar('请先刷新节点数据'); return; }
  sendBtn.disabled = true; stopBtn.disabled = false; updateStatusBar('正在发送请求...');
  responseContainer.innerHTML = '';
  try {
    const response = await fetch(`${API_BASE}/api/stream-ai-response`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ question, content: contentToSend })
    });
    if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
    const reader = response.body.getReader(); const decoder = new TextDecoder(); let buffer = '';
    while (true) {
      const { done, value } = await reader.read(); if (done) break;
      buffer += decoder.decode(value, { stream: true }); const lines = buffer.split('\n\n'); buffer = lines.pop();
      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try { const data = JSON.parse(line.slice(6)); handleStreamData(data); } catch {}
        }
      }
    }
    if (buffer.trim()) { try { const data = JSON.parse(buffer.slice(6)); handleStreamData(data); } catch {} }
  } catch (error) {
    if (error.name !== 'AbortError') {
      responseContainer.innerHTML += `<p>错误: ${error.message}</p>`;
      updateStatusBar('发送失败: ' + error.message);
    }
  } finally {
    sendBtn.disabled = false; stopBtn.disabled = true;
  }
}

function handleStreamData(data) {
  switch (data.type) {
    case 'start': responseContainer.innerHTML += `<p><em>${data.message}</em></p>`; updateStatusBar(data.message); break;
    case 'progress': responseContainer.innerHTML += `<p><em>${data.message}</em></p>`; updateStatusBar(data.message); break;
    case 'chunk': responseContainer.innerHTML += `<p>${data.content}</p>`; updateStatusBar(`接收中... (${data.index + 1} 部分)`); break;
    case 'complete': responseContainer.innerHTML += `<p><strong>${data.message}</strong></p>`; updateStatusBar(data.message); break;
    case 'error': responseContainer.innerHTML += `<p style="color: red;">错误: ${data.message}</p>`; updateStatusBar(`错误: ${data.message}`); break;
  }
  responseContainer.scrollTop = responseContainer.scrollHeight;
}

function stopRequest() {
  if (currentEventSource) { currentEventSource.close(); currentEventSource = null; }
  updateStatusBar('请求已终止'); stopBtn.disabled = true; sendBtn.disabled = false;
}

async function triggerBlenderAnalysis() {
  updateStatusBar('正在推送问题到Blender...');
  try {
    const currentContent = questionInput.value;
    const nodeDataMatch = currentContent.match(/节点数据:\s*\n*([\s\S]*?)(?=\n\s*用户问题:|$)/);
    const questionMatch = currentContent.match(/用户问题:\s*\n*([\s\S]*)/);
    const content = nodeDataMatch ? nodeDataMatch[1].trim() : '';
    const question = questionMatch ? questionMatch[1].trim() : '';
    const response = await fetch(`${API_BASE}/api/push-web-content`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ content, question, action: 'push_question_to_blender' })
    });
    if (response.ok) {
      const data = await response.json(); updateStatusBar(data.message);
      setTimeout(() => { updateStatusBar('问题已推送到Blender，等待Blender处理...'); }, 1000);
    } else {
      updateStatusBar('推送问题到Blender失败');
    }
  } catch (error) {
    updateStatusBar('推送问题到Blender失败: ' + error.message);
  }
}

refreshBtn.addEventListener('click', refreshContent);
blenderRefreshBtn.addEventListener('click', triggerBlenderAnalysis);
sendBtn.addEventListener('click', sendQuestion);
stopBtn.addEventListener('click', stopRequest);

questionInput.addEventListener('keydown', function(e) {
  if (e.key === 'Enter' && e.ctrlKey) { e.preventDefault(); sendQuestion(); }
});
