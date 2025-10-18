const apiBase = (import.meta.env.VITE_API_BASE || 'https://8bislf9d0d.execute-api.us-east-1.amazonaws.com/prod').replace(/\/$/, '');
const TOKEN_STORAGE_KEY = 'spendoptimo.idToken';

const style = document.createElement('style');
style.textContent = `
  :root {
    color-scheme: dark;
    font-family: 'Inter', system-ui, sans-serif;
    background: #0c0d11;
    color: #e6e8f0;
  }
  body, html {
    margin: 0;
    min-height: 100vh;
    background: radial-gradient(120% 120% at 50% 0%, #11131c 0%, #090a0f 55%, #050509 100%);
  }
  .page {
    display: flex;
    flex-direction: column;
    min-height: 100vh;
  }
  header {
    padding: 20px 32px;
    background: linear-gradient(135deg, rgba(86, 105, 255, 0.85), rgba(73, 228, 255, 0.8));
    border-bottom: 1px solid rgba(118, 132, 255, 0.4);
    box-shadow: 0 8px 32px rgba(86, 105, 255, 0.25);
  }
  header h1 {
    margin: 0;
    font-size: 26px;
    font-weight: 700;
    letter-spacing: 0.5px;
    background: linear-gradient(135deg, #ffffff, #b8bef5);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
  }
  header p {
    margin: 6px 0 0;
    max-width: 580px;
    color: #e0e4f7;
    font-size: 14px;
    line-height: 1.5;
    font-weight: 400;
  }
  main {
    flex: 1;
    display: flex;
    overflow: hidden;
  }
  .chat {
    flex: 1;
    display: flex;
    flex-direction: column;
    padding: 24px 32px;
    gap: 16px;
  }
  .message-list {
    flex: 1;
    overflow-y: auto;
    padding-right: 8px;
    display: flex;
    flex-direction: column;
    gap: 12px;
  }
  .loading-message {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 16px 20px;
    background: rgba(86, 105, 255, 0.1);
    border: 1px solid rgba(86, 105, 255, 0.2);
    border-radius: 16px;
    color: #b8bef5;
    font-style: italic;
  }
  .spinner {
    width: 20px;
    height: 20px;
    border: 2px solid rgba(86, 105, 255, 0.3);
    border-top: 2px solid #5669ff;
    border-radius: 50%;
    animation: spin 1s linear infinite;
  }
  @keyframes spin {
    0% { transform: rotate(0deg); }
    100% { transform: rotate(360deg); }
  }
  
  .spinner {
    display: inline-block;
    width: 16px;
    height: 16px;
    border: 2px solid rgba(134, 169, 255, 0.3);
    border-top-color: #86a9ff;
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
    margin-right: 8px;
    vertical-align: middle;
  }
  .message {
    max-width: 640px;
    padding: 16px 18px;
    border-radius: 16px;
    line-height: 1.55;
    border: 1px solid transparent;
    box-shadow: 0 10px 30px rgba(0, 0, 0, 0.2);
  }
  .message.user {
    margin-left: auto;
    background: linear-gradient(135deg, rgba(86, 105, 255, 0.65), rgba(73, 228, 255, 0.65));
    color: #ffffff;
  }
  .message.agent {
    margin-right: auto;
    background: rgba(21, 23, 36, 0.75);
    border-color: rgba(86, 105, 255, 0.25);
  }
  .message pre {
    margin: 8px 0 0;
    background: rgba(15, 16, 24, 0.85);
    padding: 12px;
    border-radius: 12px;
    overflow-x: auto;
    font-family: 'Fira Code', monospace;
    font-size: 13px;
  }
  .composer {
    display: flex;
    gap: 12px;
    align-items: flex-end;
    padding: 20px 0 0;
    border-top: 1px solid rgba(118, 132, 255, 0.15);
  }
  .composer textarea {
    flex: 1;
    min-height: 72px;
    resize: vertical;
    padding: 14px 16px;
    border-radius: 14px;
    border: 1px solid rgba(85, 104, 255, 0.25);
    background: rgba(25, 28, 40, 0.9);
    color: inherit;
  }
  .composer button {
    border: none;
    padding: 14px 22px;
    border-radius: 14px;
    font-weight: 600;
    letter-spacing: 0.4px;
    cursor: pointer;
    background: linear-gradient(135deg, rgba(86, 105, 255, 0.95), rgba(73, 228, 255, 0.9));
    color: #ffffff;
    transition: transform 0.15s ease, box-shadow 0.15s ease;
  }
  .composer button.secondary {
    background: rgba(33, 37, 60, 0.85);
    color: #d2d7ff;
    border: 1px solid rgba(86, 105, 255, 0.6);
  }
  .chat-action-button {
    background: linear-gradient(135deg, rgba(86, 105, 255, 0.95), rgba(73, 228, 255, 0.9));
    color: #ffffff;
    border: none;
    border-radius: 8px;
    padding: 12px 20px;
    font-size: 14px;
    font-weight: 600;
    cursor: pointer;
    transition: transform 0.15s ease, box-shadow 0.15s ease;
  }
  .chat-action-button:hover {
    transform: translateY(-2px);
    box-shadow: 0 8px 25px rgba(86, 105, 255, 0.4);
  }
  .composer button:disabled {
    background: rgba(60, 60, 60, 0.5);
    color: #888;
    cursor: not-allowed;
    transform: none;
    box-shadow: none;
  }
  .composer button:hover {
    transform: translateY(-1px);
    box-shadow: 0 10px 25px rgba(82, 104, 255, 0.35);
  }
  .action-buttons, .workflow-buttons {
    display: flex;
    gap: 12px;
    padding: 16px 0 0;
    border-top: 1px solid rgba(118, 132, 255, 0.15);
    margin-top: 16px;
  }
  .action-buttons button, .workflow-buttons button {
    flex: 1;
    padding: 12px 18px;
    border-radius: 12px;
    font-weight: 600;
    cursor: pointer;
    transition: transform 0.15s ease, box-shadow 0.15s ease;
    background: linear-gradient(135deg, rgba(86, 105, 255, 0.95), rgba(73, 228, 255, 0.9));
    color: #ffffff;
    border: none;
  }
  .workflow-buttons {
    display: none;
    background: rgba(86, 105, 255, 0.1);
    border-radius: 12px;
    padding: 16px;
    margin-top: 12px;
  }
  .action-buttons button.secondary {
    background: rgba(33, 37, 60, 0.85);
    color: #d2d7ff;
    border: 1px solid rgba(86, 105, 255, 0.6);
  }
  .action-buttons button:hover {
    transform: translateY(-1px);
    box-shadow: 0 8px 20px rgba(82, 104, 255, 0.25);
  }
  aside {
    width: 320px;
    border-left: 1px solid rgba(118, 132, 255, 0.15);
    background: rgba(9, 10, 16, 0.65);
    padding: 24px;
    display: flex;
    flex-direction: column;
    gap: 18px;
  }
  aside h2 {
    margin: 0;
    font-size: 18px;
    font-weight: 600;
  }
  aside .card {
    background: rgba(14, 15, 24, 0.85);
    border-radius: 16px;
    padding: 18px;
    border: 1px solid rgba(86, 105, 255, 0.15);
    line-height: 1.5;
  }
  aside .card button {
    margin-top: 12px;
    width: 100%;
    background: rgba(86, 105, 255, 0.9);
    border-radius: 12px;
    border: none;
    padding: 12px 16px;
    color: #05060c;
    font-weight: 600;
    cursor: pointer;
  }
  aside .card button.secondary {
    background: rgba(33, 37, 60, 0.85);
    color: #d2d7ff;
    border: 1px solid rgba(86, 105, 255, 0.6);
  }
  .login-button {
    width: 100%;
    background: transparent !important;
    color: #ffffff !important;
    border: 2px solid #5669ff;
    box-shadow: 0 0 0 1px rgba(73, 228, 255, 0.5) inset;
    padding: 14px 22px;
    border-radius: 14px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s ease;
  }
  .login-button:hover {
    background: rgba(86, 105, 255, 0.1) !important;
    border-color: rgba(73, 228, 255, 0.8);
    color: #ffffff !important;
    transform: translateY(-1px);
    box-shadow: 0 0 0 1px rgba(73, 228, 255, 0.8) inset, 0 10px 25px rgba(82, 104, 255, 0.25);
  }
  aside .card textarea {
    width: 100%;
    min-height: 96px;
    margin-top: 10px;
    padding: 12px;
    border-radius: 12px;
    border: 1px solid rgba(86, 105, 255, 0.2);
    background: rgba(10, 11, 18, 0.85);
    color: inherit;
    resize: vertical;
  }
  .token-actions {
    display: flex;
    gap: 10px;
    margin-top: 12px;
  }
  .token-actions button {
    flex: 1;
    width: auto;
  }
  aside .card small {
    display: block;
    margin-top: 8px;
    color: rgba(186, 194, 255, 0.7);
    font-size: 12px;
  }
`;

document.head.appendChild(style);

const app = document.getElementById('app');
app.innerHTML = `
  <div class="page">
    <header>
      <h1>SpendOptimo</h1>
      <p>Amazon AgentCore powered FinOps for autonomous AWS cost optimization</p>
    </header>
    <main>
      <section class="chat">
        <div class="message-list" id="messages"></div>
        <div class="composer">
          <textarea id="messageInput" placeholder="Ask SpendOptimo about AWS spend or request an optimization plan..."></textarea>
          <button id="sendBtn">Send</button>
        </div>
      <div class="action-buttons" id="actionButtons" style="display: none;">
        <button class="secondary" id="analyzeBtn">Analyze Spend</button>
        <button class="secondary" id="trendsBtn">Weekly Trends</button>
        <button class="secondary" id="anomaliesBtn">Find Cost Anomalies</button>
      </div>
      </section>
      <aside>
        <h2>Session</h2>
        <div class="card">
          <strong>Authentication</strong>
          <div id="authSection">
            <button id="loginBtn" class="login-button">Sign In with Cognito</button>
            <div id="userInfo" style="display: none;">
              <p>Welcome, <span id="userName"></span>!</p>
              <button id="logoutBtn" class="secondary">Sign Out</button>
            </div>
          </div>
          <small id="tokenStatus">Not authenticated.</small>
        </div>
        <div class="card" id="statusCard" style="display: none;">
          <strong>Status Lookup</strong>
          <input id="executionInput" placeholder="Execution ARN..." style="width:100%;margin-bottom:8px;padding:10px;border-radius:10px;border:1px solid rgba(86,105,255,0.2);background:rgba(10,11,18,0.8);color:inherit;" />
        </div>
      </aside>
    </main>
  </div>
`;

const messages = document.getElementById('messages');
const input = document.getElementById('messageInput');
const sendBtn = document.getElementById('sendBtn');
const analyzeBtn = document.getElementById('analyzeBtn');
const trendsBtn = document.getElementById('trendsBtn');
const anomaliesBtn = document.getElementById('anomaliesBtn');
const executionInput = document.getElementById('executionInput');
// Token input elements removed - using Cognito login only
const tokenStatus = document.getElementById('tokenStatus');
const loginBtn = document.getElementById('loginBtn');
const logoutBtn = document.getElementById('logoutBtn');
const userInfo = document.getElementById('userInfo');
const userName = document.getElementById('userName');
const authSection = document.getElementById('authSection');
const actionButtons = document.getElementById('actionButtons');
const statusCard = document.getElementById('statusCard');

// Cognito configuration - these should be set in your environment
const COGNITO_CONFIG = {
  userPoolId: 'us-east-1_di7kBd1Co',
  clientId: '79sli5ed5m44crt752i43iai1i',
  domain: 'spendoptimo-905418470400-us-east-1.auth.us-east-1.amazoncognito.com',
  redirectUri: window.location.origin + '/'
};

let authToken = localStorage.getItem(TOKEN_STORAGE_KEY) || '';

// Check if user is already authenticated
function checkAuthStatus() {
  if (authToken) {
    try {
      const payload = JSON.parse(atob(authToken.split('.')[1]));
      if (payload.exp * 1000 > Date.now()) {
        showAuthenticatedState(payload);
        return;
      }
    } catch (e) {
      // Token is invalid
    }
  }
  showUnauthenticatedState();
}

function showAuthenticatedState(payload) {
  if (userInfo) userInfo.style.display = 'block';
  if (authSection) authSection.style.display = 'none';
  if (userName) userName.textContent = payload.email || payload['cognito:username'] || 'User';
  if (tokenStatus) {
    tokenStatus.innerHTML = '<span style="color: #2ecc71; font-weight: bold; margin-right: 6px;">✓</span>Authenticated';
    tokenStatus.style.color = '#2ecc71';
  }
}

function showUnauthenticatedState() {
  if (userInfo) userInfo.style.display = 'none';
  if (authSection) authSection.style.display = 'block';
  if (tokenStatus) {
    tokenStatus.innerHTML = '<span style="color: #e74c3c; font-weight: bold; margin-right: 6px;">✗</span>Not authenticated';
    tokenStatus.style.color = '#e74c3c';
  }
}

function initiateCognitoLogin() {
  const loginUrl = `https://${COGNITO_CONFIG.domain}/login?response_type=token&client_id=${encodeURIComponent(COGNITO_CONFIG.clientId)}&redirect_uri=${encodeURIComponent(COGNITO_CONFIG.redirectUri)}&scope=openid+email+profile`;
  window.location.assign(loginUrl);
}

function handleCognitoCallback() {
  const hash = window.location.hash;
  if (hash) {
    const params = new URLSearchParams(hash.substring(1));
    const token = params.get('id_token');
    if (token) {
      authToken = token;
      localStorage.setItem(TOKEN_STORAGE_KEY, token);
      checkAuthStatus();
      // Clear the hash from URL
      window.history.replaceState({}, document.title, window.location.pathname);
    }
  }
}

function logout() {
  authToken = '';
  localStorage.removeItem(TOKEN_STORAGE_KEY);
  checkAuthStatus();
}

function abbreviateToken(token) {
  if (!token) return '';
  if (token.length <= 18) return token;
  return `${token.slice(0, 10)}…${token.slice(-8)}`;
}

function updateTokenStatus() {
  if (!tokenStatus) return;
  if (authToken) {
    tokenStatus.textContent = `Token loaded (${abbreviateToken(authToken)})`;
  } else {
    tokenStatus.textContent = 'No token stored.';
  }
}

// Initialize authentication
checkAuthStatus();
handleCognitoCallback();

const conversation = [];

function formatResponse(text) {
  // Split into lines for processing
  const lines = text.split('\n');
  const formatted = [];
  
  for (let i = 0; i < lines.length; i++) {
    let line = lines[i];
    
    // Skip completely empty lines
    if (line.trim() === '') {
      // Only add spacing div if previous line wasn't empty
      if (i > 0 && lines[i-1].trim() !== '') {
        formatted.push('<div style="margin: 6px 0;"></div>');
      }
      continue;
    }
    
    // Headers
    if (line.startsWith('### ')) {
      formatted.push(`<h3 style="color: #86a9ff; margin: 10px 0 4px 0; font-size: 16px; font-weight: 600;">${line.substring(4)}</h3>`);
    } else if (line.startsWith('## ')) {
      formatted.push(`<h2 style="color: #86a9ff; margin: 12px 0 5px 0; font-size: 18px; font-weight: 600;">${line.substring(3)}</h2>`);
    } else if (line.startsWith('# ')) {
      formatted.push(`<h1 style="color: #86a9ff; margin: 12px 0 6px 0; font-size: 20px; font-weight: 600;">${line.substring(2)}</h1>`);
    }
    // Numbered lists
    else if (/^\d+\.\s+/.test(line)) {
      const match = line.match(/^(\d+)\.\s+(.+)$/);
      if (match) {
        const content = match[2].replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>').replace(/\*(.*?)\*/g, '<em>$1</em>');
        formatted.push(`<div style="margin: 3px 0; padding-left: 20px;"><span style="color: #86a9ff; font-weight: bold;">${match[1]}.</span> ${content}</div>`);
      }
    }
    // Bullet points (-, *, or •)
    else if (/^[-*•]\s+/.test(line)) {
      const content = line.substring(2).replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>').replace(/\*(.*?)\*/g, '<em>$1</em>');
      formatted.push(`<div style="margin: 3px 0; padding-left: 20px;"><span style="color: #86a9ff;">•</span> ${content}</div>`);
    }
    // Indented content (sub-items with leading spaces)
    else if (/^\s{2,}-\s+/.test(line)) {
      const content = line.trim().substring(2).replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>').replace(/\*(.*?)\*/g, '<em>$1</em>');
      formatted.push(`<div style="margin: 2px 0; padding-left: 40px; font-size: 14px;"><span style="color: #86a9ff;">–</span> ${content}</div>`);
    }
    // Regular text
    else {
      const content = line.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>').replace(/\*(.*?)\*/g, '<em>$1</em>');
      formatted.push(content);
    }
  }
  
  return formatted.join('');
}

function pushMessage(message) {
  conversation.push(message);
  const wrapper = document.createElement('div');
  wrapper.className = `message ${message.role}`;
  
  // Format the content for better readability
  let content = message.content;
  if (message.role === 'agent' && typeof content === 'string') {
    content = formatResponse(content);
  }
  
  // Check if the message has a button from the agent
  let buttonHtml = '';
  let buttonId = '';
  if (message.role === 'agent' && message.button) {
    buttonId = `chat-button-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
    buttonHtml = `
      <div style="margin-top: 16px;">
        <button id="${buttonId}" class="chat-action-button" data-action="${message.button.action}">
          ${message.button.text}
        </button>
      </div>
    `;
  }
  
  wrapper.innerHTML = `
    <div>${content}</div>
    ${buttonHtml}
    ${message.meta ? `<details style="margin-top: 12px;"><summary style="cursor: pointer; color: #86a9ff; font-size: 12px;">Technical Details</summary><pre style="margin-top: 8px; padding: 8px; background: rgba(0,0,0,0.3); border-radius: 8px; font-size: 11px; overflow-x: auto;">${JSON.stringify(message.meta, null, 2)}</pre></details>` : ''}
  `;
  messages.appendChild(wrapper);
  messages.scrollTop = messages.scrollHeight;
  
  // Add event listener for chat buttons
  if (message.role === 'agent' && message.button && buttonId) {
    const button = wrapper.querySelector(`#${buttonId}`);
    if (button) {
      button.addEventListener('click', async () => {
        console.log('Button clicked! Button data:', message.button);
        console.log('Recommendations:', message.button.recommendations);
        
        if (message.button.action === 'rightsizing_workflow') {
          await executeRightsizingWorkflow(message.button.recommendations || []);
        } else if (message.button.action === 'deploy_and_optimize_workflow') {
          await executeDeployAndOptimizeWorkflow();
        }
      });
    }
  }
  
  // Show action buttons based on response content
  if (message.role === 'agent' && actionButtons) {
    const content = message.content.toLowerCase();
    
    // Show general action buttons for most responses
    if (content.includes('cost') || content.includes('spend') || content.includes('aws')) {
      actionButtons.style.display = 'flex';
    }
    
    // Show workflow buttons only for rightsizing recommendations
  }
}

function api(path, options) {
  if (!apiBase) {
    throw new Error('VITE_API_BASE is not configured.');
  }
  const init = { ...(options || {}) };
  const headers = {
    'content-type': 'application/json',
    ...((options && options.headers) || {}),
  };
  if (authToken) {
    headers.Authorization = `Bearer ${authToken}`;
  }
  init.headers = headers;
  return fetch(apiBase + path, init).then((res) => {
    if (!res.ok) {
      return res.text().then((text) => {
        throw new Error(text || res.statusText);
      });
    }
    return res.json();
  });
}

async function sendChat() {
  const text = input.value.trim();
  if (!text) return;
  if (!authToken) {
    pushMessage({
      role: 'agent',
      content: 'Provide an identity token in the Session panel before chatting with SpendOptimo.',
    });
    return;
  }
  
  // Add user message
  pushMessage({ role: 'user', content: text });
  input.value = '';
  
  // Disable send button and show loading
  sendBtn.disabled = true;
  sendBtn.textContent = 'Sending...';
  
  // Add loading message
  const loadingId = 'loading-' + Date.now();
  const loadingDiv = document.createElement('div');
  loadingDiv.id = loadingId;
  loadingDiv.className = 'loading-message';
  loadingDiv.innerHTML = `
    <div class="spinner"></div>
    <span>SpendOptimo is analyzing your request...</span>
  `;
  messages.appendChild(loadingDiv);
  messages.scrollTop = messages.scrollHeight;
  
  try {
    const resp = await api('/v1/chat', {
      method: 'POST',
      body: JSON.stringify({ goal: text }),
    });
    
    // Remove loading message
    const loadingElement = document.getElementById(loadingId);
    if (loadingElement) {
      loadingElement.remove();
    }
    
    const agent = resp.agent || {};
    let reply = agent.completion || agent.raw?.response || agent.raw?.completion || agent.raw?.output || 'No response generated.';
    let button = null;
    
    // Parse and format the response if it's JSON (double-encoded from AgentCore)
    try {
      if (typeof reply === 'string' && (reply.includes('"message"') || reply.includes('"button"'))) {
        const parsed = JSON.parse(reply);
        if (parsed.message) {
          reply = parsed.message;
        }
        if (parsed.button) {
          button = parsed.button;
          console.log('Extracted button from completion:', button);
        }
      }
    } catch (e) {
      console.log('Failed to parse completion JSON:', e);
      // If parsing fails, use the original reply
    }
    
    // Format the response for better readability
    reply = formatResponse(reply);
    
    // Push message with button if available
    if (button) {
      console.log('Pushing message with button:', button);
      pushMessage({ role: 'agent', content: reply, meta: agent, button: button });
    } else {
    pushMessage({ role: 'agent', content: reply, meta: agent });
    }
  } catch (error) {
    // Remove loading message
    const loadingElement = document.getElementById(loadingId);
    if (loadingElement) {
      loadingElement.remove();
    }
    pushMessage({ role: 'agent', content: 'Execution failed.', meta: { error: String(error) } });
  } finally {
    // Re-enable send button
    sendBtn.disabled = false;
    sendBtn.textContent = 'Send';
  }
}

async function runAnalysis() {
  if (!authToken) {
    pushMessage({
      role: 'agent',
      content: 'Provide an identity token in the Session panel before running analysis.',
    });
    return;
  }
  
  // Disable analyze button and show loading
  analyzeBtn.disabled = true;
  analyzeBtn.textContent = 'Analyzing...';
  
  try {
    pushMessage({ role: 'agent', content: 'Analyzing your AWS spending...' });
    
    // Use the AgentCore chat endpoint instead of direct API calls
    const resp = await api('/v1/chat', {
      method: 'POST',
      body: JSON.stringify({
        prompt: 'Analyze my AWS spending and provide a comprehensive cost analysis. Show me total spend, top services, trends, and optimization recommendations.'
      })
    });
    
    // AgentCore response is nested under 'agent' key and may be double-encoded JSON
    const agentResponse = resp.agent || resp;
    let message = agentResponse.message;
    let button = agentResponse.button;
    
    // If completion is a JSON string, parse it
    if (!message && agentResponse.completion) {
      try {
        const parsed = JSON.parse(agentResponse.completion);
        message = parsed.message;
        button = parsed.button;
      } catch (e) {
        message = agentResponse.completion;
      }
    }
    
    // Fallback
    message = message || resp.message || 'Analysis complete.';
    
    // Check if there's a button
    if (button) {
      pushMessage({ role: 'agent', content: message, meta: resp, button: button });
    } else {
      pushMessage({ role: 'agent', content: message, meta: resp });
    }
  } catch (error) {
    pushMessage({ role: 'agent', content: 'Unable to analyze spending.', meta: { error: String(error) } });
  } finally {
    // Re-enable analyze button
    analyzeBtn.disabled = false;
    analyzeBtn.textContent = 'Analyze Spend';
  }
}

async function runTrends() {
  if (!authToken) {
    pushMessage({
      role: 'agent',
      content: 'Provide an identity token in the Session panel before analyzing trends.',
    });
    return;
  }
  
  try {
    pushMessage({ role: 'agent', content: 'Analyzing weekly cost trends...' });
    
    // Use the AgentCore chat endpoint instead of direct API calls
    const response = await api('/v1/chat', {
      method: 'POST',
      body: JSON.stringify({
        prompt: 'Analyze my AWS cost trends for the last 14 days. Show me spending patterns, trends, and any cost optimization opportunities.'
      })
    });
    
    // AgentCore response is nested under 'agent' key and may be double-encoded JSON
    const agentResponse = response.agent || response;
    let message = agentResponse.message;
    let button = agentResponse.button;
    
    // If completion is a JSON string, parse it
    if (!message && agentResponse.completion) {
      try {
        const parsed = JSON.parse(agentResponse.completion);
        message = parsed.message;
        button = parsed.button;
      } catch (e) {
        message = agentResponse.completion;
      }
    }
    
    // Fallback
    message = message || response.message || 'Trend analysis complete.';
    
    // Check if there's a button
    if (button) {
      pushMessage({ role: 'agent', content: message, meta: response, button: button });
    } else {
      pushMessage({ role: 'agent', content: message, meta: response });
    }
  } catch (error) {
    pushMessage({ role: 'agent', content: 'Unable to analyze trends.', meta: { error: String(error) } });
  }
}

async function runAnomalies() {
  if (!authToken) {
    pushMessage({
      role: 'agent',
      content: 'Provide an identity token in the Session panel before checking for anomalies.',
    });
    return;
  }
  
  try {
    pushMessage({ role: 'agent', content: 'Checking for cost anomalies...' });
    // Use the AgentCore chat endpoint instead of direct API calls
    const response = await api('/v1/chat', {
      method: 'POST',
      body: JSON.stringify({
        prompt: 'Check for cost anomalies in my AWS billing for the last 7 days. Identify any unusual spending patterns or unexpected cost increases.'
      })
    });
    
    // AgentCore response is nested under 'agent' key and may be double-encoded JSON
    const agentResponse = response.agent || response;
    let message = agentResponse.message;
    let button = agentResponse.button;
    
    // If completion is a JSON string, parse it
    if (!message && agentResponse.completion) {
      try {
        const parsed = JSON.parse(agentResponse.completion);
        message = parsed.message;
        button = parsed.button;
      } catch (e) {
        message = agentResponse.completion;
      }
    }
    
    // Fallback
    message = message || response.message || 'Anomaly check complete.';
    
    // Check if there's a button
    if (button) {
      pushMessage({ role: 'agent', content: message, meta: response, button: button });
    } else {
      pushMessage({ role: 'agent', content: message, meta: response });
    }
  } catch (error) {
    pushMessage({ role: 'agent', content: 'Unable to check for anomalies.', meta: { error: String(error) } });
  }
}

async function executeRightsizingWorkflow(recommendations = []) {
  if (!authToken) {
    pushMessage({
      role: 'agent',
      content: 'Provide an identity token in the Session panel before executing rightsizing workflow.',
    });
    return;
  }
  
  try {
    // Call the automation endpoint with recommendations (no separate spinner)
    const response = await api('/v1/automation', {
      method: 'POST',
      body: JSON.stringify({
        action: 'optimize_existing_instances',
        context: {
          recommendations: recommendations || []
        }
      })
    });
    
    // Format the response from workflow agent
    let message = '<div style="font-family: monospace; background: rgba(0,0,0,0.2); padding: 16px; border-radius: 8px; margin: 12px 0;">';
    
    // Check if this is an async accepted response (202)
    if (response.status === 'accepted') {
      message += '<div style="font-size: 18px; font-weight: bold; color: #4ade80; margin-bottom: 12px;">✅ Workflow Started</div>';
    } else {
      message += '<div style="font-size: 18px; font-weight: bold; color: #4ade80; margin-bottom: 12px;">✅ Workflow Completed</div>';
    }
    
    if (response.result) {
      const result = response.result;
      message += `<div style="margin: 12px 0;">${formatResponse(result.message || result.execution_details || 'Workflow executed')}</div>`;
      
      if (result.recommendations_processed) {
        message += `<div style="margin-top: 12px; padding: 8px; background: rgba(134,169,255,0.1); border-radius: 4px;">`;
        message += `<div style="color: #4ade80;">✅ Processing ${result.recommendations_processed} recommendation(s)</div>`;
        message += `</div>`;
      }
      
      if (response.execution_id) {
        message += `<div style="margin-top: 12px; padding: 8px; background: rgba(134,169,255,0.05); border-radius: 4px; font-size: 12px; color: #999;">`;
        message += `Execution ID: ${response.execution_id}`;
        message += `</div>`;
      }
    } else {
      message += '<div style="color: #999;">Workflow execution details not available</div>';
    }
    
    message += '</div>';
    
    pushMessage({ role: 'agent', content: message, meta: response });
    
  } catch (error) {
    pushMessage({ role: 'agent', content: 'Workflow execution failed.', meta: { error: String(error) } });
  }
}

// Keep old implementation for backward compatibility
async function executeRightsizingWorkflowOld() {
  if (!authToken) {
    pushMessage({
      role: 'agent',
      content: 'Provide an identity token in the Session panel before executing rightsizing workflow.',
    });
    return;
  }
  
  try {
    pushMessage({ role: 'agent', content: 'Executing rightsizing workflow with agent recommendations...' });
    
    // Call the automation endpoint with the specific recommendations from the agent
    const response = await api('/v1/automation', {
      method: 'POST',
      body: JSON.stringify({
        action: 'optimize_existing_instances',
        context: {
          service: 'Amazon Elastic Compute Cloud - Compute',
          requestedBy: 'chat_button',
          workflow_type: 'execute_agent_recommendations',
          recommendations: []
        }
      })
    });
    
    // Format the response as a visual pipeline
    let message = '<div style="font-family: monospace; background: rgba(0,0,0,0.2); padding: 16px; border-radius: 8px; margin: 12px 0;">';
    message += '<div style="font-size: 18px; font-weight: bold; color: #86a9ff; margin-bottom: 12px;">🔄 Optimization Workflow Pipeline</div>';
    
    if (response.execution) {
      const execution = response.execution;
      message += `<div style="font-size: 12px; color: #999; margin-bottom: 16px;">Execution ID: ${execution.id || 'N/A'}</div>`;
      
      if (execution.payload && execution.payload.workflow) {
        const workflow = execution.payload.workflow;
        
        // Define steps in order
        const steps = [
          { key: 'validate_recommendations', name: '1. Validate Recommendations' },
          { key: 'apply_rightsizing', name: '2. Apply Changes' },
          { key: 'verify_optimization', name: '3. Verify' }
        ];
        
        let hasResults = false;
        
        // Render pipeline
        steps.forEach((stepDef, idx) => {
          const stepData = workflow[stepDef.key];
          const isComplete = stepData && stepData.status !== 'failed';
          const isFailed = stepData && stepData.status === 'failed';
          
          // Step box
          message += '<div style="display: flex; align-items: center; margin: 8px 0;">';
          
          // Status indicator - spinner or checkmark
          if (isComplete) {
            // Filled circle (checkmark)
            message += '<div style="width: 20px; height: 20px; border-radius: 50%; background: #4ade80; display: flex; align-items: center; justify-content: center; margin-right: 12px; font-size: 12px; color: #000;">✓</div>';
          } else if (isFailed) {
            // Red X
            message += '<div style="width: 20px; height: 20px; border-radius: 50%; background: #f87171; display: flex; align-items: center; justify-content: center; margin-right: 12px; font-size: 12px; color: #000;">✗</div>';
    } else {
            // Empty circle (not executed)
            message += '<div style="width: 20px; height: 20px; border-radius: 50%; border: 2px solid #666; margin-right: 12px;"></div>';
          }
          
          // Step name
          message += `<div style="flex: 1; ${isComplete ? 'color: #86a9ff; font-weight: 500;' : 'color: #666;'}">${stepDef.name}</div>`;
          
          // Step result summary
          if (stepData) {
            hasResults = true;
            if (stepDef.key === 'discover_instances') {
              const count = stepData.instances?.length || 0;
              message += `<div style="color: #86a9ff; font-size: 12px;">${count} instances</div>`;
            } else if (stepDef.key === 'analyze_optimization') {
              const toOptimize = stepData.summary?.instances_to_optimize || 0;
              message += `<div style="color: ${toOptimize > 0 ? '#fbbf24' : '#4ade80'}; font-size: 12px;">${toOptimize} to optimize</div>`;
            } else if (stepDef.key === 'apply_rightsizing') {
              const modified = stepData.summary?.instances_modified || 0;
              message += `<div style="color: ${modified > 0 ? '#4ade80' : '#666'}; font-size: 12px;">${modified} modified</div>`;
            }
          }
          
          message += '</div>';
          
          // Connection line (except for last step)
          if (idx < steps.length - 1) {
            const nextStepData = workflow[steps[idx + 1].key];
            const nextStepStarted = nextStepData && (nextStepData.status === 'success' || nextStepData.status === 'failed');
            message += `<div style="margin-left: 10px; width: 2px; height: 20px; background: ${isComplete && nextStepStarted ? '#4ade80' : '#333'};"></div>`;
          }
        });
        
        // Detailed results section
        if (hasResults) {
          message += '<div style="margin-top: 16px; padding-top: 12px; border-top: 1px solid #333;">';
          message += '<div style="font-weight: bold; margin-bottom: 8px;">📋 Execution Summary</div>';
          
          // Analysis results
          if (workflow.analyze_optimization) {
            const summary = workflow.analyze_optimization.summary || {};
            message += `<div style="margin: 4px 0;">• Found: ${summary.total_instances || 0} instances</div>`;
            message += `<div style="margin: 4px 0;">• To Optimize: ${summary.instances_to_optimize || 0}</div>`;
            message += `<div style="margin: 4px 0;">• Est. Savings: ${summary.total_estimated_savings || '$0/month'}</div>`;
          }
          
          // Modifications
          if (workflow.apply_rightsizing) {
            const summary = workflow.apply_rightsizing.summary || {};
            const modified = summary.instances_modified || 0;
            if (modified > 0) {
              message += `<div style="margin: 4px 0; color: #4ade80;">✓ Successfully modified ${modified} instance(s)</div>`;
            } else {
              message += `<div style="margin: 4px 0; color: #fbbf24;">ℹ No modifications needed - all instances optimal</div>`;
            }
          }
          
          message += '</div>';
        }
        
        // Overall status
        message += '<div style="margin-top: 16px; padding: 8px; background: rgba(134,169,255,0.1); border-radius: 4px;">';
        if (workflow.status === 'completed') {
          message += `<div style="color: #4ade80;">✅ ${workflow.message || 'Workflow completed successfully'}</div>`;
        } else {
          message += `<div style="color: #fbbf24;">⚠️ ${workflow.message || 'Workflow completed with warnings'}</div>`;
        }
        message += '</div>';
        
      } else {
        message += '<div style="color: #999;">Workflow executed - check technical details</div>';
      }
    }
    
    message += '</div>';
    
    pushMessage({ role: 'agent', content: message, meta: response });
  } catch (error) {
    pushMessage({ role: 'agent', content: 'Unable to execute rightsizing workflow.', meta: { error: String(error) } });
  }
}

async function executeDeployAndOptimizeWorkflow() {
  if (!authToken) {
    pushMessage({ 
      role: 'agent', 
      content: 'Provide an identity token in the Session panel before executing deploy and optimize workflow.',
    });
    return;
  }
  
  try {
    pushMessage({ role: 'agent', content: '🚀 Executing optimization workflow... This will analyze your existing instances.' });
    
    // Call the automation endpoint directly to execute the workflow
    const response = await api('/v1/automation', {
      method: 'POST',
      body: JSON.stringify({
        action: 'optimize_existing_instances',
        context: {
          service: 'Amazon Elastic Compute Cloud - Compute',
          requestedBy: 'chat_button',
          workflow_type: 'optimize_existing_instances'
        }
      })
    });
    
    // Format the response for display
    let message = '🚀 Optimization workflow executed successfully!\n\n';
    if (response.execution) {
      const execution = response.execution;
      message += `**Execution ID**: ${execution.id || 'N/A'}\n`;
      
      if (execution.payload && execution.payload.workflow) {
        const workflow = execution.payload.workflow;
        
        message += "\n**Workflow Steps Completed:**\n";
        
        // Show each step result
        if (workflow.deploy_test_instance) {
          const step = workflow.deploy_test_instance;
          message += `✅ **Deploy Test Instance**: ${step.message || 'Completed'}\n`;
          if (step.instance_id) {
            message += `   - Instance ID: ${step.instance_id}\n`;
            message += `   - Instance Type: ${step.instance_type || 'N/A'}\n`;
          }
        }
        
        if (workflow.collect_usage_metrics) {
          const step = workflow.collect_usage_metrics;
          message += `✅ **Collect Usage Metrics**: ${step.message || 'Completed'}\n`;
          if (step.metrics) {
            const metrics = step.metrics;
            const cpu_avg = metrics.cpu_utilization?.average || 0;
            message += `   - Average CPU: ${cpu_avg}%\n`;
          }
        }
        
        if (workflow.analyze_optimization) {
          const step = workflow.analyze_optimization;
          message += `✅ **Analyze Optimization**: ${step.message || 'Completed'}\n`;
          if (step.analysis) {
            const analysis = step.analysis;
            message += `   - Current Type: ${analysis.current_instance_type || 'N/A'}\n`;
            message += `   - Recommended Type: ${analysis.recommended_instance_type || 'N/A'}\n`;
            message += `   - Estimated Savings: $${analysis.estimated_monthly_savings || 0}/month\n`;
            message += `   - Confidence: ${analysis.confidence_level || 'N/A'}\n`;
          }
        }
        
        if (workflow.apply_rightsizing) {
          const step = workflow.apply_rightsizing;
          if (step.status === 'success') {
            message += `✅ **Apply Rightsizing**: ${step.message || 'Completed'}\n`;
            if (step.previous_type && step.new_type) {
              message += `   - Changed: ${step.previous_type} → ${step.new_type}\n`;
            }
          } else if (step.status === 'skipped') {
            message += `⏭️ **Apply Rightsizing**: ${step.message || 'Skipped'}\n`;
          } else {
            message += `❌ **Apply Rightsizing**: ${step.message || 'Failed'}\n`;
          }
        }
        
        if (workflow.verify_optimization) {
          const step = workflow.verify_optimization;
          message += `✅ **Verify Optimization**: ${step.message || 'Completed'}\n`;
        }
        
        if (workflow.cleanup_test_resources) {
          const step = workflow.cleanup_test_resources;
          message += `✅ **Cleanup Resources**: ${step.message || 'Completed'}\n`;
          if (step.cleaned_up_instance) {
            message += `   - Cleaned up: ${step.cleaned_up_instance}\n`;
          }
        }
        
        // Add overall workflow status
        if (workflow.status === 'completed') {
          message += `\n🎉 **Overall Status**: ${workflow.message || 'Workflow completed successfully'}`;
        } else {
          message += `\n⚠️ **Overall Status**: ${workflow.message || 'Workflow completed with warnings'}`;
        }
      } else {
        message += "**Workflow executed** - check the execution details for results.";
      }
    }
    
    pushMessage({ role: 'agent', content: message, meta: response });
  } catch (error) {
    pushMessage({ role: 'agent', content: 'Unable to execute optimization workflow.', meta: { error: String(error) } });
  }
}

// Event listeners
sendBtn.addEventListener('click', sendChat);
analyzeBtn.addEventListener('click', runAnalysis);
trendsBtn.addEventListener('click', runTrends);
anomaliesBtn.addEventListener('click', runAnomalies);
loginBtn.addEventListener('click', initiateCognitoLogin);
logoutBtn.addEventListener('click', logout);
input.addEventListener('keydown', (event) => {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault();
    sendChat();
  }
});

pushMessage({
  role: 'agent',
  content: 'Hello! I am SpendOptimo. Ask me about your AWS spend, review findings, or launch a Strand for automated remediation.',
});



