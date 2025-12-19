// 配置
const API_BASE = 'http://127.0.0.1:5000';
let currentEventSource = null; // 用于终止流式请求

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


// 初始化
window.onload = function() {
    updateStatusBar('就绪 - 连接后端服务器...');
    init();
};

async function init() {
    try {
        const data = await apiTestConnection();
        updateStatusBar(`已连接 - ${data.message}`);
        fetchAndDisplayHistory();
        addClearHistoryListener();
    } catch (error) {
        updateStatusBar(`连接失败: ${error.message}`);
    }
}

// 获取并显示历史记录
async function fetchAndDisplayHistory() {
    try {
        historyList.innerHTML = '';
        for (let i = 0; i < 3; i++) {
            const li = document.createElement('li');
            li.className = 'skeleton';
            li.style.height = '24px';
            historyList.appendChild(li);
        }
        const data = await fetchMessages();
        historyList.innerHTML = '';
        if (data.messages && data.messages.length > 0) {
            data.messages.forEach(msg => {
                const li = document.createElement('li');
                const question = msg.message || 'No question';
                li.textContent = question.substring(0, 30) + (question.length > 30 ? '...' : '');
                li.dataset.fullMessage = JSON.stringify(msg);
                li.addEventListener('click', () => {
                    const fullMsg = JSON.parse(li.dataset.fullMessage);
                    clearResponse();
                    renderChunk(fullMsg.response || '');
                    fillTextarea(fullMsg.message || '');
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

// 添加清空历史记录事件
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
                await clearMessages();
                fetchAndDisplayHistory();
                updateStatusBar('对话历史已清空');
            } catch (error) {
                updateStatusBar('清空历史失败');
            }
        });
    }
}


// 测试连接
async function testConnection() {
    try {
        const response = await fetch(`${API_BASE}/api/test-connection`);
        const data = await response.json();
        updateStatusBar(`已连接 - ${data.message}`);
    } catch (error) {
        updateStatusBar(`连接失败: ${error.message}`);
        console.error('连接测试失败:', error);
    }
}

// 更新状态栏
function updateStatusBar(message) {
    uiUpdateStatusBar(message);
}

// 刷新内容 - 触发Blender刷新后获取AINodeRefreshContent
async function refreshContent() {
    updateStatusBar('正在触发Blender刷新...');
    try {
        await triggerBlenderRefresh();
        updateStatusBar('Blender刷新已触发，正在获取内容...');
        await new Promise(resolve => setTimeout(resolve, 1000));
        const data = await getBlenderData();
        const content = data.nodes || '暂无数据';
        setOriginalNodeData(content);
        const currentText = els.questionInput.value;
        const questionMatch = currentText.match(/用户问题:\s*\n*([\s\S]*)/);
        const currentQuestion = questionMatch ? questionMatch[1].trim() : '';
        let newSendContent = '';
        if (content !== '暂无数据') {
            newSendContent = `节点数据:\n${content}`;
        }
        if (currentQuestion) {
            newSendContent = newSendContent ? `${newSendContent}\n\n用户问题:\n${currentQuestion}` : `用户问题:\n${currentQuestion}`;
        }
        els.questionInput.value = newSendContent || '发送内容将显示在此处...';
        updateStatusBar('内容已刷新');
    } catch (error) {
        els.questionInput.value = '无法从Blender获取数据，请确保Blender插件正在运行';
        setOriginalNodeData('');
        updateStatusBar('未获取到数据');
    }
}

// 发送问题到AI
async function sendQuestion() {
    const currentContent = els.questionInput.value;
    const nodeDataMatch = currentContent.match(/节点数据:\s*\n*([\s\S]*?)(?=\n\s*用户问题:|$)/);
    const questionMatch = currentContent.match(/用户问题:\s*\n*([\s\S]*)/);
    const contentToSend = nodeDataMatch ? nodeDataMatch[1].trim() : '';
    const question = questionMatch ? questionMatch[1].trim() : '';
    if (!question) { updateStatusBar('请输入问题'); return; }
    if (!contentToSend || contentToSend === '暂无数据') { updateStatusBar('请先刷新节点数据'); return; }
    setButtonsState({ sending: true });
    updateStatusBar('正在发送请求...');
    showResponseSkeleton();
    try {
        await streamAiResponse({ question, content: contentToSend, onData: handleStreamData });
    } catch (error) {
        if (error.name !== 'AbortError') {
            renderError(error.message);
            updateStatusBar('发送失败: ' + error.message);
        }
    } finally {
        setButtonsState({ sending: false });
    }
}

// 处理流数据
function handleStreamData(data) {
    switch (data.type) {
        case 'start':
            renderStart(data.message);
            updateStatusBar(data.message);
            break;
        case 'progress':
            renderProgress(data.message);
            updateStatusBar(data.message);
            break;
        case 'chunk':
            renderChunk(data.content);
            updateStatusBar(`接收中... (${data.index + 1} 部分)`);
            break;
        case 'complete':
            renderComplete(data.message);
            updateStatusBar(data.message);
            break;
        case 'error':
            renderError(data.message);
            updateStatusBar(`错误: ${data.message}`);
            break;
    }
}

// 终止请求
function stopRequest() {
    updateStatusBar('请求已终止');
    setButtonsState({ sending: false });
}

// 保存原始节点数据
let originalNodeData = '';



// 推送内容到Blender（将当前问题推送至Blender的问题输入框）
async function triggerBlenderAnalysis() {
    updateStatusBar('正在推送问题到Blender...');
    try {
        const currentContent = els.questionInput.value;
        const nodeDataMatch = currentContent.match(/节点数据:\s*\n*([\s\S]*?)(?=\n\s*用户问题:|$)/);
        const questionMatch = currentContent.match(/用户问题:\s*\n*([\s\S]*)/);
        const content = nodeDataMatch ? nodeDataMatch[1].trim() : '';
        const question = questionMatch ? questionMatch[1].trim() : '';
        const data = await pushWebContent({ content, question });
        updateStatusBar(data.message);
        setTimeout(() => { updateStatusBar('问题已推送到Blender，等待Blender处理...'); }, 1000);
    } catch (error) {
        updateStatusBar('推送问题到Blender失败: ' + error.message);
    }
}

// 绑定事件
els.refreshBtn.addEventListener('click', refreshContent);
els.blenderRefreshBtn.addEventListener('click', triggerBlenderAnalysis);
els.sendBtn.addEventListener('click', sendQuestion);
els.stopBtn.addEventListener('click', stopRequest);

// 监听 Enter 键发送 (Ctrl+Enter 换行)
els.questionInput.addEventListener('keydown', function(e) {
    if (e.key === 'Enter' && e.ctrlKey) {
        // Ctrl+Enter 发送
        e.preventDefault();
        sendQuestion();
    }
});
const themeToggle = document.getElementById('themeToggle');
if (themeToggle) {
  const saved = localStorage.getItem('ainode-theme');
  if (saved) document.documentElement.setAttribute('data-theme', saved);
  themeToggle.addEventListener('click', () => {
    const current = document.documentElement.getAttribute('data-theme');
    const next = current === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', next);
    localStorage.setItem('ainode-theme', next);
  });
}

import { els, setOriginalNodeData } from './state.js';
import { testConnection as apiTestConnection, fetchMessages, clearMessages, triggerBlenderRefresh, getBlenderData, pushWebContent, streamAiResponse } from './api.js';
import { updateStatusBar as uiUpdateStatusBar, fillTextarea, setButtonsState } from './ui.js';
import { renderStart, renderProgress, renderChunk, renderComplete, renderError, clearResponse, showResponseSkeleton } from './render.js';
