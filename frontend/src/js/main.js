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


// 初始化
window.onload = function() {
    updateStatusBar('就绪 - 连接后端服务器...');
    testConnection();
};

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
    statusBar.textContent = message;
}

// 刷新内容 - 触发Blender刷新后获取AINodeRefreshContent
async function refreshContent() {
    updateStatusBar('正在触发Blender刷新...');
    try {
        // 首先触发Blender中的刷新操作
        const triggerResponse = await fetch(`${API_BASE}/api/trigger-blender-refresh`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                action: 'refresh_nodes'
            })
        });

        if (triggerResponse.ok) {
            updateStatusBar('Blender刷新已触发，正在获取内容...');

            // 等待短暂时间让Blender完成刷新操作
            await new Promise(resolve => setTimeout(resolve, 1000));

            // 然后获取刷新后的内容
            const response = await fetch(`${API_BASE}/api/blender-data`, {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json'
                }
            });

            if (response.ok) {
                const data = await response.json();
                // 更新发送内容区域
                const content = data.nodes || '暂无数据';
                originalNodeData = content; // 保存原始节点数据

                // 获取当前文本区域中的问题部分（如果存在）
                const currentText = questionInput.value;
                const questionMatch = currentText.match(/用户问题:\s*\n*([\s\S]*)/);
                const currentQuestion = questionMatch ? questionMatch[1].trim() : '';

                // 组合节点数据和问题
                let newSendContent = '';
                if (content !== '暂无数据') {
                    newSendContent = `节点数据:\n${content}`;
                }

                if (currentQuestion) {
                    if (newSendContent) {
                        newSendContent += `\n\n用户问题:\n${currentQuestion}`;
                    } else {
                        newSendContent = `用户问题:\n${currentQuestion}`;
                    }
                }

                // 更新textarea内容
                questionInput.value = newSendContent || '发送内容将显示在此处...';

                updateStatusBar('内容已刷新');
            } else {
                // 如果无法从后端获取数据，提示用户
                questionInput.value = '无法从Blender获取数据，请确保Blender插件正在运行';
                originalNodeData = '';
                updateStatusBar('未获取到数据');
            }
        } else {
            updateStatusBar('触发Blender刷新失败');
        }
    } catch (error) {
        console.error('刷新内容失败:', error);
        questionInput.value = `刷新失败: ${error.message}`;
        originalNodeData = '';
        updateStatusBar('刷新失败: ' + error.message);
    }
}

// 发送问题到AI
async function sendQuestion() {
    // 从textarea获取当前内容，解析出节点数据和问题
    const currentContent = questionInput.value;

    // 解析内容获取节点数据和问题
    const nodeDataMatch = currentContent.match(/节点数据:\s*\n*([\s\S]*?)(?=\n\s*用户问题:|$)/);
    const questionMatch = currentContent.match(/用户问题:\s*\n*([\s\S]*)/);

    const contentToSend = nodeDataMatch ? nodeDataMatch[1].trim() : '';
    const question = questionMatch ? questionMatch[1].trim() : '';

    if (!question) {
        updateStatusBar('请输入问题');
        return;
    }

    if (!contentToSend || contentToSend === '暂无数据') {
        updateStatusBar('请先刷新节点数据');
        return;
    }

    // 禁用发送按钮，启用终止按钮
    sendBtn.disabled = true;
    stopBtn.disabled = false;
    updateStatusBar('正在发送请求...');

    // 清空之前的响应
    responseContainer.innerHTML = '';

    try {
        const response = await fetch(`${API_BASE}/api/stream-ai-response`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                question: question,
                content: contentToSend  // 发送解析出的节点数据
            })
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
            const { done, value } = await reader.read();

            if (done) break;

            buffer += decoder.decode(value, { stream: true });

            // 查找完整的消息（以 \n\n 分隔）
            const lines = buffer.split('\n\n');
            buffer = lines.pop(); // 保留未完成的部分

            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    try {
                        const data = JSON.parse(line.slice(6)); // 移除 'data: ' 前缀
                        handleStreamData(data);
                    } catch (e) {
                        console.error('解析流数据失败:', e);
                    }
                }
            }
        }

        // 处理剩余的缓冲数据
        if (buffer.trim()) {
            try {
                const data = JSON.parse(buffer.slice(6));
                handleStreamData(data);
            } catch (e) {
                console.error('解析剩余流数据失败:', e);
            }
        }

    } catch (error) {
        if (error.name !== 'AbortError') {
            console.error('发送问题失败:', error);
            responseContainer.innerHTML += `<p>错误: ${error.message}</p>`;
            updateStatusBar('发送失败: ' + error.message);
        }
    } finally {
        // 恢复按钮状态
        sendBtn.disabled = false;
        stopBtn.disabled = true;
    }
}

// 处理流数据
function handleStreamData(data) {
    switch (data.type) {
        case 'start':
            responseContainer.innerHTML += `<p><em>${data.message}</em></p>`;
            updateStatusBar(data.message);
            break;
        case 'progress':
            responseContainer.innerHTML += `<p><em>${data.message}</em></p>`;
            updateStatusBar(data.message);
            break;
        case 'chunk':
            responseContainer.innerHTML += `<p>${data.content}</p>`;
            updateStatusBar(`接收中... (${data.index + 1} 部分)`);
            break;
        case 'complete':
            responseContainer.innerHTML += `<p><strong>${data.message}</strong></p>`;
            updateStatusBar(data.message);
            break;
        case 'error':
            responseContainer.innerHTML += `<p style="color: red;">错误: ${data.message}</p>`;
            updateStatusBar(`错误: ${data.message}`);
            break;
    }

    // 滚动到底部
    responseContainer.scrollTop = responseContainer.scrollHeight;
}

// 终止请求
function stopRequest() {
    if (currentEventSource) {
        currentEventSource.close();
        currentEventSource = null;
    }
    
    updateStatusBar('请求已终止');
    stopBtn.disabled = true;
    sendBtn.disabled = false;
}

// 保存原始节点数据
let originalNodeData = '';

// 推送内容到Blender（将当前问题推送至Blender的问题输入框）
async function triggerBlenderAnalysis() {
    updateStatusBar('正在推送问题到Blender...');
    try {
        // 从textarea获取当前内容，解析出节点数据和问题
        const currentContent = questionInput.value;

        // 解析内容获取节点数据和问题
        const nodeDataMatch = currentContent.match(/节点数据:\s*\n*([\s\S]*?)(?=\n\s*用户问题:|$)/);
        const questionMatch = currentContent.match(/用户问题:\s*\n*([\s\S]*)/);

        const content = nodeDataMatch ? nodeDataMatch[1].trim() : '';
        const question = questionMatch ? questionMatch[1].trim() : '';

        const response = await fetch(`${API_BASE}/api/push-web-content`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                content: content, // 节点数据
                question: question, // 当前问题
                action: 'push_question_to_blender'
            })
        });

        if (response.ok) {
            const data = await response.json();
            updateStatusBar(data.message);

            // 提示用户问题已推送
            setTimeout(() => {
                updateStatusBar('问题已推送到Blender，等待Blender处理...');
            }, 1000);
        } else {
            updateStatusBar('推送问题到Blender失败');
        }
    } catch (error) {
        console.error('推送问题到Blender失败:', error);
        updateStatusBar('推送问题到Blender失败: ' + error.message);
    }
}

// 绑定事件
refreshBtn.addEventListener('click', refreshContent);
blenderRefreshBtn.addEventListener('click', triggerBlenderAnalysis);
sendBtn.addEventListener('click', sendQuestion);
stopBtn.addEventListener('click', stopRequest);

// 监听 Enter 键发送 (Ctrl+Enter 换行)
questionInput.addEventListener('keydown', function(e) {
    if (e.key === 'Enter' && e.ctrlKey) {
        // Ctrl+Enter 发送
        e.preventDefault();
        sendQuestion();
    }
});
