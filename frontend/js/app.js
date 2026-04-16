const API_BASE_URL = (window.__API_BASE_URL__ !== undefined) ? window.__API_BASE_URL__ : 'http://localhost:5001';

let currentAbortController = null;
let currentReader = null;
let currentSessionId = null;
let currentMultiAgentId = null;

function setStreaming(isStreaming) {
    const sendBtn = document.getElementById('sendBtn');
    const stopBtn = document.getElementById('stopBtn');
    const input = document.getElementById('userInput');
    if (isStreaming) {
        sendBtn.style.display = 'none';
        stopBtn.style.display = 'inline-block';
        input.disabled = true;
        input.style.opacity = '0.5';
    } else {
        sendBtn.style.display = 'inline-block';
        stopBtn.style.display = 'none';
        input.disabled = false;
        input.style.opacity = '1';
        input.focus();
        currentAbortController = null;
        currentReader = null;
    }
}

function saveCurrentSessionId(sid) {
    currentSessionId = sid;
    localStorage.setItem('currentSessionId', sid);
}

function saveCurrentMultiAgentId(maId) {
    currentMultiAgentId = maId;
    localStorage.setItem('currentMultiAgentId', maId);
}

async function loadMultiAgents() {
    try {
        console.log('[loadMultiAgents] 开始加载多智能体列表...');
        const response = await fetch(`${API_BASE_URL}/api/multi-agents`);
        console.log('[loadMultiAgents] 响应状态:', response.status);
        const data = await response.json();
        console.log('[loadMultiAgents] 响应数据:', data);
        
        if (data.success) {
            const multiAgents = data.data;
            const select = document.getElementById('multiAgentSelect');
            select.innerHTML = '';
            
            console.log('[loadMultiAgents] 多智能体数量:', multiAgents.length);
            
            multiAgents.forEach(ma => {
                if (ma.is_active === true) {
                    const option = document.createElement('option');
                    option.value = ma.id;
                    option.textContent = ma.name;
                    select.appendChild(option);
                }
            });
            
            let savedMultiAgentId = localStorage.getItem('currentMultiAgentId');
            if (savedMultiAgentId && multiAgents.some(ma => ma.id === savedMultiAgentId)) {
                select.value = savedMultiAgentId;
                currentMultiAgentId = savedMultiAgentId;
            } else {
                const defaultAgent = multiAgents.find(ma => ma.is_default === true);
                if (defaultAgent) {
                    select.value = defaultAgent.id;
                    currentMultiAgentId = defaultAgent.id;
                    saveCurrentMultiAgentId(defaultAgent.id);
                } else if (multiAgents.length > 0) {
                    select.value = multiAgents[0].id;
                    currentMultiAgentId = multiAgents[0].id;
                    saveCurrentMultiAgentId(multiAgents[0].id);
                }
            }
            
            console.log('[loadMultiAgents] 加载完成，当前选中:', currentMultiAgentId);
        } else {
            console.error('[loadMultiAgents] API 返回失败:', data);
            document.getElementById('multiAgentSelect').innerHTML = '<option value="">加载失败</option>';
        }
    } catch (error) {
        console.error('[loadMultiAgents] 加载多智能体列表失败:', error);
        document.getElementById('multiAgentSelect').innerHTML = '<option value="">加载失败</option>';
    }
}

async function createNewChat() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/session/new`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });
        const data = await response.json();
        if (data.success) {
            saveCurrentSessionId(data.session_id);
            document.getElementById('chatContainer').innerHTML = '';
            addMessage('你好！我是iservice智能客服助手，请问有什么可以帮助你的？', false);
            loadSessionList();
        } else {
            alert('创建新会话失败: ' + (data.error || '未知错误'));
        }
    } catch (error) {
        alert('创建新会话失败: ' + error.message);
    }
}

async function loadSessionList() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/session/list`);
        const data = await response.json();
        if (data.success) {
            const sessionList = document.getElementById('sessionList');
            sessionList.innerHTML = '';
            data.sessions.forEach(s => {
                const sessionItem = document.createElement('div');
                sessionItem.className = 'session-item' + (s.session_id === currentSessionId ? ' active' : '');
                const preview = s.latest_message || '空会话';
                const shortId = s.session_id.substring(0, 8);
                sessionItem.innerHTML = `
                    <div class="session-id">会话 ${shortId}...</div>
                    <div class="session-preview">${preview}</div>
                `;
                sessionItem.onclick = () => selectSession(s.session_id);
                sessionList.appendChild(sessionItem);
            });
        }
    } catch (error) {
        console.error('加载会话列表失败:', error);
    }
}

async function selectSession(sessionId) {
    saveCurrentSessionId(sessionId);
    await loadSessionHistory(sessionId);
    loadSessionList();
}

function stopGeneration() {
    if (currentReader) {
        currentReader.cancel().catch(() => {});
    }
    if (currentAbortController) {
        currentAbortController.abort();
    }
    removeLoadingMessage();
    setStreaming(false);
}

function addMessage(message, isUser = false, agentName = '') {
    const chatContainer = document.getElementById('chatContainer');
    const messageDiv = document.createElement('div');
    messageDiv.className = isUser ? 'message user-message' : 'message system-message';
    let agentInfo = '';
    if (!isUser && agentName) {
        agentInfo = `<div class="agent-info">来自: ${agentName}</div>`;
    }
    messageDiv.innerHTML = `
        ${agentInfo}
        <div class="message-content">${message}</div>
        <div class="message-info">${new Date().toLocaleTimeString()}</div>
    `;
    chatContainer.appendChild(messageDiv);
    chatContainer.scrollTop = chatContainer.scrollHeight;
    return messageDiv;
}

function addLoadingMessage(text) {
    const chatContainer = document.getElementById('chatContainer');
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message loading-message';
    messageDiv.id = 'loadingMsg';
    messageDiv.innerHTML = `
        <div class="loading-spinner"></div>
        <div class="loading-text" id="loadingText">${text}</div>
    `;
    chatContainer.appendChild(messageDiv);
    chatContainer.scrollTop = chatContainer.scrollHeight;
}

function updateLoadingText(text) {
    const el = document.getElementById('loadingText');
    if (el) el.textContent = text;
}

function removeLoadingMessage() {
    const el = document.getElementById('loadingMsg');
    if (el) el.remove();
}

function recognize() {
    const userInput = document.getElementById('userInput').value.trim();
    if (!userInput) {
        alert('请输入内容');
        return;
    }
    if (!currentSessionId) {
        alert('会话未初始化，请刷新页面');
        return;
    }

    addMessage(userInput, true);
    document.getElementById('userInput').value = '';
    setStreaming(true);
    addLoadingMessage('正在识别意图...');

    fetch(`${API_BASE_URL}/api/recognize`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ input: userInput, multi_agent_id: currentMultiAgentId })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            const method = data.recognition_method === 'embedding' ? 'Embedding向量匹配' : 'LLM推理';
            const confidence = data.confidence ? (data.confidence * 100).toFixed(1) : '0';
            updateLoadingText(`识别完成 [${method}, 置信度: ${confidence}%] → 正在调用 Agent: ${data.agent_name || '无'}...`);

            if (!data.agent_id) {
                removeLoadingMessage();
                addMessage('识别失败：未找到对应的智能体', false);
                setStreaming(false);
                return;
            }

            const msgDiv = addMessage('', false, data.agent_name);
            msgDiv.style.display = 'none';
            const contentEl = msgDiv.querySelector('.message-content');
            let firstChunk = true;

            const abortController = new AbortController();
            currentAbortController = abortController;

            return fetch(`${API_BASE_URL}/api/recognize/execute/stream`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ input: userInput, agent_id: data.agent_id, session_id: currentSessionId }),
                signal: abortController.signal
            }).then(response => {
                const reader = response.body.getReader();
                currentReader = reader;
                const decoder = new TextDecoder();
                let buffer = '';

                function read() {
                    reader.read().then(({ done, value }) => {
                        if (done) {
                            removeLoadingMessage();
                            msgDiv.style.display = '';
                            loadSessionList();
                            setStreaming(false);
                            return;
                        }
                        buffer += decoder.decode(value, { stream: true });
                        const lines = buffer.split('\n');
                        buffer = lines.pop();
                        for (const line of lines) {
                            if (line.startsWith('data: ')) {
                                const payload = line.slice(6);
                                if (payload.trim() === '[DONE]') {
                                    removeLoadingMessage();
                                    msgDiv.style.display = '';
                                    loadSessionList();
                                    setStreaming(false);
                                    return;
                                }
                                try {
                                    const chunk = JSON.parse(payload);
                                    if (chunk.error) {
                                        removeLoadingMessage();
                                        msgDiv.style.display = '';
                                        contentEl.textContent += '错误: ' + chunk.error;
                                        setStreaming(false);
                                    } else if (chunk.content) {
                                        if (firstChunk) {
                                            firstChunk = false;
                                            removeLoadingMessage();
                                            msgDiv.style.display = '';
                                        }
                                        contentEl.textContent += chunk.content;
                                        document.getElementById('chatContainer').scrollTop = document.getElementById('chatContainer').scrollHeight;
                                    }
                                } catch (e) {}
                            }
                        }
                        read();
                    }).catch(err => {
                        if (err.name === 'AbortError') {
                            if (contentEl.textContent) {
                                contentEl.textContent += ' [已停止]';
                            } else {
                                msgDiv.remove();
                            }
                        } else {
                            removeLoadingMessage();
                            msgDiv.style.display = '';
                            contentEl.textContent += '读取错误: ' + err.message;
                        }
                        setStreaming(false);
                    });
                }
                read();
            }).catch(err => {
                if (err.name === 'AbortError') {
                    if (contentEl.textContent) {
                        contentEl.textContent += ' [已停止]';
                    } else {
                        msgDiv.remove();
                    }
                } else {
                    removeLoadingMessage();
                    msgDiv.style.display = '';
                    contentEl.textContent += '请求错误: ' + err.message;
                }
                setStreaming(false);
            });
        } else {
            removeLoadingMessage();
            addMessage(`识别失败：${data.error}`, false);
            setStreaming(false);
        }
    })
    .catch(error => {
        removeLoadingMessage();
        addMessage(`请求失败：${error.message}`, false);
        setStreaming(false);
    });
}

document.getElementById('userInput').addEventListener('keypress', function(e) {
    if (e.key === 'Enter') {
        recognize();
    }
});

document.getElementById('multiAgentSelect').addEventListener('change', function(e) {
    const selectedId = e.target.value;
    saveCurrentMultiAgentId(selectedId);
    currentMultiAgentId = selectedId;
});

async function loadSessionHistory(sessionId) {
    if (!sessionId) return;
    try {
        const response = await fetch(`${API_BASE_URL}/api/session/history?session_id=${sessionId}`);
        const data = await response.json();
        if (data.success) {
            document.getElementById('chatContainer').innerHTML = '';
            if (data.history.length > 0) {
                data.history.forEach(item => {
                    if (item.user_input) addMessage(item.user_input, true);
                    if (item.response && item.response !== '新会话') addMessage(item.response, false, item.agent_name);
                });
            }
            if (document.getElementById('chatContainer').innerHTML.trim() === '') {
                addMessage('你好！我是iservice智能客服助手，请问有什么可以帮助你的？', false);
            }
        }
    } catch (error) {
        console.error('加载会话历史失败:', error);
    }
}

async function clearSession() {
    if (!currentSessionId) return;
    if (confirm('确定要清空当前会话的历史记录吗？')) {
        try {
            const response = await fetch(`${API_BASE_URL}/api/session/clear`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ session_id: currentSessionId })
            });
            const data = await response.json();
            if (data.success) {
                document.getElementById('chatContainer').innerHTML = '';
                addMessage('你好！我是iservice智能客服助手，请问有什么可以帮助你的？', false);
                loadSessionList();
            }
        } catch (error) {
            console.error('清空会话失败:', error);
            alert('清空会话失败');
        }
    }
}

async function initApp() {
    await loadMultiAgents();
    
    let savedSessionId = localStorage.getItem('currentSessionId');
    console.log('[initApp] 检查 localStorage 中的 currentSessionId:', savedSessionId);

    if (!savedSessionId) {
        console.log('[initApp] 没有保存的 session_id，创建新会话...');
        const response = await fetch(`${API_BASE_URL}/api/session/new`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });
        const data = await response.json();
        
        if (data.success) {
            saveCurrentSessionId(data.session_id);
            document.getElementById('chatContainer').innerHTML = '';
            addMessage('你好！我是iservice智能客服助手，请问有什么可以帮助你的？', false);
            loadSessionList();
        } else {
            console.error('创建新会话失败:', data.error);
            alert('创建新会话失败');
        }
    } else {
        console.log('[initApp] 找到保存的 session_id，加载历史...');
        currentSessionId = savedSessionId;
        const historyResponse = await fetch(`${API_BASE_URL}/api/session/history?session_id=${savedSessionId}`);
        const historyData = await historyResponse.json();
        
        if (historyData.success && historyData.history && historyData.history.length > 0) {
            await loadSessionHistory(savedSessionId);
            loadSessionList();
        } else {
            console.log('[initApp] 历史记录为空或加载失败，创建新会话...');
            const response = await fetch(`${API_BASE_URL}/api/session/new`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });
            const data = await response.json();
            
            if (data.success) {
                saveCurrentSessionId(data.session_id);
                addMessage('你好！我是iservice智能客服助手，请问有什么可以帮助你的？', false);
                loadSessionList();
            } else {
                console.error('创建新会话失败:', data.error);
                alert('创建新会话失败');
            }
        }
    }
}

document.addEventListener('DOMContentLoaded', async function() {
    console.log('[DOMContentLoaded] 页面加载完成，开始初始化应用...');
    await initApp();
    console.log('[DOMContentLoaded] 应用初始化完成');
});