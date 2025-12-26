(function() {
    // --- Configuration ---
    const API_BASE = 'http://127.0.0.1:5000';
    let currentEventSource = null;

    // --- State & Elements ---
    const els = {
        chatContainer: document.getElementById('chatContainer'),
        questionInput: document.getElementById('questionInput'),
        sendBtn: document.getElementById('sendBtn'),
        stopBtn: document.getElementById('stopBtn'),
        blenderRefreshBtn: document.getElementById('blenderRefreshBtn'),
        historyList: document.getElementById('historyList'),
        statusBar: document.getElementById('statusBar'),
        statusDot: document.getElementById('statusDot'),
        newChatBtn: document.getElementById('newChatBtn'),
        mobileMenuBtn: document.getElementById('mobileMenuBtn'),
        sidebar: document.getElementById('sidebar'),
        welcomeScreen: document.getElementById('welcomeScreen'),
        nodeDataStatus: document.getElementById('nodeDataStatus'),
        // Modal elements
        dataModal: document.getElementById('dataModal'),
        closeModalBtn: document.getElementById('closeModalBtn'),
        nodeDataContent: document.getElementById('nodeDataContent'),
        copyDataBtn: document.getElementById('copyDataBtn')
    };

    let originalNodeData = '';
    let isGenerating = false;
    let autoScroll = true;
    let currentConversationId = null;

    // --- Utils ---
    function generateUUID() {
        return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
            var r = Math.random() * 16 | 0, v = c == 'x' ? r : (r & 0x3 | 0x8);
            return v.toString(16);
        });
    }

    // --- UI Helpers ---
    function updateStatusBar(message, type = 'normal') {
        if (els.statusBar) els.statusBar.textContent = message;
        if (els.statusDot) {
            els.statusDot.className = `w-2 h-2 rounded-full ${type === 'error' ? 'bg-red-500' : type === 'success' ? 'bg-green-500' : 'bg-blue-500'}`;
        }
    }

    function toggleLoading(isLoading) {
        isGenerating = isLoading;
        if (els.sendBtn) els.sendBtn.disabled = isLoading;
        if (els.stopBtn) {
            els.stopBtn.classList.toggle('hidden', !isLoading);
            els.stopBtn.classList.toggle('flex', isLoading);
        }
        if (els.questionInput) els.questionInput.disabled = isLoading;
    }

    function scrollToBottom() {
        if (els.chatContainer && autoScroll) {
            els.chatContainer.scrollTo({
                top: els.chatContainer.scrollHeight,
                behavior: 'smooth'
            });
        }
    }

    // Smart scroll detection
    if (els.chatContainer) {
        els.chatContainer.addEventListener('scroll', () => {
            const { scrollTop, scrollHeight, clientHeight } = els.chatContainer;
            // If user scrolled up (more than 50px from bottom), disable auto-scroll
            if (scrollHeight - scrollTop - clientHeight > 50) {
                autoScroll = false;
            } else {
                autoScroll = true;
            }
        });
    }

    function hideWelcomeScreen() {
        if (els.welcomeScreen) els.welcomeScreen.classList.add('hidden');
    }

    function showWelcomeScreen() {
        if (els.welcomeScreen) els.welcomeScreen.classList.remove('hidden');
    }

    // --- Modal Logic ---
    function openNodeDataModal() {
        if (!originalNodeData) return;
        if (els.nodeDataContent) els.nodeDataContent.textContent = originalNodeData;
        if (els.dataModal) els.dataModal.classList.remove('hidden');
    }

    function closeNodeDataModal() {
        if (els.dataModal) els.dataModal.classList.add('hidden');
    }

    function copyNodeData() {
        if (!originalNodeData) return;
        navigator.clipboard.writeText(originalNodeData).then(() => {
            const originalText = els.copyDataBtn.textContent;
            els.copyDataBtn.textContent = '已复制!';
            setTimeout(() => {
                els.copyDataBtn.textContent = originalText;
            }, 2000);
        });
    }

    // --- Render Logic ---
    function createMessageElement(isUser, content = '') {
        const wrapper = document.createElement('div');
        wrapper.className = `flex w-full ${isUser ? 'justify-end' : 'justify-start'}`;
        
        const bubble = document.createElement('div');
        bubble.className = `max-w-[85%] rounded-2xl px-4 py-3 text-sm leading-relaxed shadow-sm ${
            isUser 
                ? 'bg-blue-600 text-white rounded-br-none' 
                : 'bg-gray-800 text-gray-100 rounded-bl-none border border-gray-700'
        }`;

        if (!isUser) {
            // AI message container for streaming/markdown
            bubble.innerHTML = '<div class="markdown-body animate-pulse">...</div>';
        } else {
            bubble.textContent = content;
        }

        wrapper.appendChild(bubble);
        return { wrapper, bubble };
    }

    function renderMarkdown(element, markdown) {
        if (!window.marked) {
            element.textContent = markdown;
            return;
        }
        
        // Configure marked for highlighting
        marked.setOptions({
            highlight: function(code, lang) {
                if (lang && hljs.getLanguage(lang)) {
                    return hljs.highlight(code, { language: lang }).value;
                }
                return hljs.highlightAuto(code).value;
            },
            breaks: true
        });

        element.innerHTML = marked.parse(markdown);
        
        // Post-process links to open in new tab
        element.querySelectorAll('a').forEach(a => {
            a.target = '_blank';
            a.rel = 'noopener noreferrer';
            a.className = 'text-blue-400 hover:underline';
        });

        // Style code blocks
        element.querySelectorAll('pre').forEach(pre => {
            pre.className = 'bg-[#1a1b26] p-3 rounded-lg overflow-x-auto my-2 text-xs border border-gray-700';
        });
    }

    // --- API ---
    async function apiTestConnection() {
        const res = await fetch(`${API_BASE}/api/test-connection`);
        return res.json();
    }

    async function fetchMessages() {
        const res = await fetch(`${API_BASE}/api/get-messages`);
        if (!res.ok) throw new Error('Failed to fetch history');
        return res.json();
    }

    async function getBlenderData() {
        const res = await fetch(`${API_BASE}/api/blender-data`, {
            method: 'GET',
            headers: { 'Content-Type': 'application/json' }
        });
        if (!res.ok) throw new Error('Failed to fetch Blender data');
        return res.json();
    }

    // --- Main Logic ---
    async function init() {
        // Setup Event Listeners
        if (els.sendBtn) els.sendBtn.addEventListener('click', handleSend);
        if (els.stopBtn) els.stopBtn.addEventListener('click', handleStop);
        if (els.blenderRefreshBtn) els.blenderRefreshBtn.addEventListener('click', handleBlenderRefresh);
        if (els.newChatBtn) els.newChatBtn.addEventListener('click', handleNewChat);
        
        // Modal listeners
        if (els.closeModalBtn) els.closeModalBtn.addEventListener('click', closeNodeDataModal);
        if (els.copyDataBtn) els.copyDataBtn.addEventListener('click', copyNodeData);
        if (els.nodeDataStatus) els.nodeDataStatus.addEventListener('click', openNodeDataModal);

        if (els.questionInput) {
            els.questionInput.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    handleSend();
                }
            });
            // Auto-resize
            els.questionInput.addEventListener('input', function() {
                this.style.height = 'auto';
                this.style.height = (this.scrollHeight) + 'px';
            });
        }

        // Mobile menu
        if (els.mobileMenuBtn && els.sidebar) {
            els.mobileMenuBtn.addEventListener('click', () => {
                els.sidebar.classList.toggle('hidden');
                els.sidebar.classList.toggle('fixed');
                els.sidebar.classList.toggle('inset-0');
                els.sidebar.classList.toggle('z-50');
            });
        }

        // Check connection
        try {
            updateStatusBar('连接中...', 'normal');
            const data = await apiTestConnection();
            updateStatusBar('已连接', 'success');
            loadHistory();
        } catch (error) {
            updateStatusBar('未连接 (请确保后端运行)', 'error');
            console.error(error);
        }
    }

    async function loadHistory() {
        try {
            const data = await fetchMessages();
            els.historyList.innerHTML = '';
            
            if (data.messages && data.messages.length > 0) {
                data.messages.forEach(msg => {
                    const li = document.createElement('li');
                    li.className = 'px-3 py-2 text-sm text-gray-400 rounded cursor-pointer hover:bg-gray-800 truncate transition-colors';
                    li.textContent = msg.message || 'New Chat';
                    li.onclick = () => loadChatSession(msg);
                    els.historyList.appendChild(li);
                });
            } else {
                els.historyList.innerHTML = '<li class="px-3 py-2 text-sm text-gray-500 italic">暂无历史记录</li>';
            }
        } catch (e) {
            console.error('History load error', e);
        }
    }

    function loadChatSession(msg) {
        hideWelcomeScreen();
        els.chatContainer.innerHTML = ''; // Clear current view
        
        currentConversationId = msg.conversationId;

        // Re-render user message
        const userEl = createMessageElement(true, msg.message);
        els.chatContainer.appendChild(userEl.wrapper);
        
        // Re-render AI message
        const aiEl = createMessageElement(false);
        renderMarkdown(aiEl.bubble, msg.response || '(No response)');
        els.chatContainer.appendChild(aiEl.wrapper);
        
        autoScroll = true;
        scrollToBottom();
    }

    function handleNewChat() {
        showWelcomeScreen();
        els.chatContainer.innerHTML = '';
        els.chatContainer.appendChild(els.welcomeScreen);
        els.questionInput.value = '';
        els.questionInput.style.height = 'auto';
    }

    async function handleBlenderRefresh() {
        try {
            els.blenderRefreshBtn.disabled = true;
            els.blenderRefreshBtn.innerHTML = '<span class="animate-spin">↻</span> 刷新中...';
            
            const data = await getBlenderData();
            originalNodeData = data.nodes || '';
            
            if (originalNodeData) {
                if (els.nodeDataStatus) {
                    els.nodeDataStatus.classList.remove('hidden');
                    // Add View button styled link
                    els.nodeDataStatus.innerHTML = `
                        <span class="cursor-pointer hover:text-blue-400 border-b border-dashed border-gray-600 hover:border-blue-400 transition" title="点击查看详情">
                            已加载 ${originalNodeData.length} 字节数据
                        </span>
                    `;
                    els.nodeDataStatus.classList.add('text-green-500');
                    // Re-bind click event since we changed innerHTML
                    els.nodeDataStatus.onclick = openNodeDataModal;
                }
                updateStatusBar('节点数据已更新', 'success');
            } else {
                updateStatusBar('未检测到节点数据', 'error');
            }
        } catch (e) {
            updateStatusBar('获取Blender数据失败', 'error');
        } finally {
            els.blenderRefreshBtn.disabled = false;
            els.blenderRefreshBtn.innerHTML = `
                <svg xmlns="http://www.w3.org/2000/svg" class="h-3.5 w-3.5" viewBox="0 0 20 20" fill="currentColor">
                    <path fill-rule="evenodd" d="M4 2a1 1 0 011 1v2.101a7.002 7.002 0 0111.601 2.566 1 1 0 11-1.885.666A5.002 5.002 0 005.999 7H9a1 1 0 010 2H4a1 1 0 01-1-1V3a1 1 0 011-1zm.008 9.057a1 1 0 011.276.61A5.002 5.002 0 0014.001 13H11a1 1 0 110-2h5a1 1 0 011 1v5a1 1 0 11-2 0v-2.101a7.002 7.002 0 01-11.601-2.566 1 1 0 01.61-1.276z" clip-rule="evenodd" />
                </svg>
                刷新节点数据
            `;
        }
    }

    async function handleSend() {
        const question = els.questionInput.value.trim();
        if (!question) return;

        // UI Updates
        hideWelcomeScreen();
        toggleLoading(true);
        els.questionInput.value = '';
        els.questionInput.style.height = 'auto';

        // 1. User Message
        const userEl = createMessageElement(true, question);
        els.chatContainer.appendChild(userEl.wrapper);
        autoScroll = true;
        scrollToBottom();

        // 2. AI Placeholder
        const aiEl = createMessageElement(false);
        els.chatContainer.appendChild(aiEl.wrapper);
        scrollToBottom();

        let fullResponse = '';

        try {
            const controller = new AbortController();
            currentEventSource = controller;

            const response = await fetch(`${API_BASE}/api/stream-analyze`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    question: question,
                    content: originalNodeData || "No node data provided. User just wants to chat."
                }),
                signal: controller.signal
            });

            if (!response.ok) throw new Error(`Server error: ${response.status}`);

            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                
                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n');
                
                // Process all complete lines
                buffer = lines.pop(); // Keep the last incomplete line in buffer

                for (const line of lines) {
                    if (line.trim() === '') continue;
                    
                    if (line.startsWith('data: ')) {
                        try {
                            const jsonStr = line.slice(6);
                            if (jsonStr === '[DONE]') break; // Standard SSE close

                            const data = JSON.parse(jsonStr);
                            
                            if (data.type === 'start' && data.conversationId) {
                                currentConversationId = data.conversationId;
                            } else if (data.type === 'chunk' && data.content) {
                                fullResponse += data.content;
                                renderMarkdown(aiEl.bubble, fullResponse);
                                scrollToBottom();
                            } else if (data.type === 'error') {
                                throw new Error(data.message);
                            }
                            // Ignore 'start', 'progress', 'complete' unless needed
                        } catch (e) {
                            console.warn('Parse error:', e, line);
                        }
                    }
                }
            }
            
            // Reload history to show saved chat
            loadHistory();

        } catch (error) {
            if (error.name === 'AbortError') {
                renderMarkdown(aiEl.bubble, fullResponse + '\n\n*(Stopped by user)*');
            } else {
                aiEl.bubble.innerHTML += `<div class="text-red-400 mt-2 text-xs">Error: ${error.message}</div>`;
            }
        } finally {
            toggleLoading(false);
            currentEventSource = null;
        }
    }

    function handleStop() {
        if (currentEventSource) {
            currentEventSource.abort();
        }
        toggleLoading(false);
        updateStatusBar('已停止', 'normal');
    }

    // Initialize
    window.onload = init;

})();
