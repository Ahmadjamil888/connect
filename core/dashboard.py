import os
import threading
from collections import deque
from datetime import datetime

from flask import Flask, jsonify, request
from flask_socketio import SocketIO


DASHBOARD_HTML = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>IMOS Dashboard</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
  <script src="https://cdn.socket.io/4.7.2/socket.io.min.js"></script>
  <style>
    :root {
      --bg: #0a0a0a;
      --panel: #111111;
      --text: #e8e8e8;
      --muted: #8e8e8e;
      --accent: #c8a96e;
      --border: #1e1e1e;
      --green: #6f8f5a;
      --yellow: #a88f52;
      --red: #9a5b5b;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font-family: Inter, ui-monospace, SFMono-Regular, Menlo, monospace;
    }
    .topbar, .bottombar {
      display: grid;
      grid-template-columns: 1fr 1fr 1fr;
      align-items: center;
      padding: 14px 18px;
      border-bottom: 1px solid var(--border);
      background: #0d0d0d;
      letter-spacing: 0.02em;
    }
    .bottombar {
      border-top: 1px solid var(--border);
      border-bottom: none;
      color: var(--muted);
      font-size: 12px;
    }
    .center { text-align: center; }
    .right { text-align: right; }
    .runtime-title { color: var(--accent); font-weight: 700; }
    .status-wrap { display: inline-flex; align-items: center; gap: 8px; justify-content: flex-end; }
    .status-dot {
      width: 10px; height: 10px; border-radius: 50%;
      background: var(--red); border: 1px solid #222;
      display: inline-block;
    }
    .status-green { background: var(--green); }
    .status-yellow { background: var(--yellow); }
    .status-red { background: var(--red); }
    .layout {
      display: grid;
      grid-template-columns: 22% 28% 28% 22%;
      gap: 14px;
      padding: 14px;
      min-height: calc(100vh - 104px);
    }
    .panel-chat {
      display: flex;
      flex-direction: column;
      min-height: 520px;
    }
    .chat-messages {
      flex: 1;
      min-height: 380px;
      max-height: calc(100vh - 220px);
      overflow-y: auto;
      border: 1px solid var(--border);
      padding: 12px;
      background: #080808;
      display: flex;
      flex-direction: column;
      gap: 10px;
    }
    .chat-bubble {
      max-width: 92%;
      padding: 10px 12px;
      border-radius: 10px;
      font-size: 12px;
      line-height: 1.5;
      white-space: pre-wrap;
      word-break: break-word;
    }
    .chat-bubble.user {
      align-self: flex-end;
      background: #1a1814;
      border: 1px solid #3d3528;
      color: var(--text);
    }
    .chat-bubble.assistant {
      align-self: flex-start;
      background: #0f0f0f;
      border: 1px solid var(--border);
      color: #d8d8d8;
    }
    .chat-bubble .chat-meta {
      display: block;
      font-size: 10px;
      color: var(--muted);
      margin-bottom: 4px;
      text-transform: uppercase;
      letter-spacing: 0.06em;
    }
    .chat-compose {
      display: flex;
      gap: 8px;
      margin-top: 12px;
    }
    .chat-compose input {
      flex: 1;
      border: 1px solid var(--border);
      background: #0d0d0d;
      color: var(--text);
      padding: 10px 12px;
      font-size: 12px;
      font-family: inherit;
    }
    .chat-compose input:focus {
      outline: none;
      border-color: #4a4030;
    }
    .chat-empty {
      color: var(--muted);
      font-size: 12px;
      text-align: center;
      margin: auto;
      padding: 24px 12px;
    }
    .panel {
      border: 1px solid var(--border);
      background: var(--panel);
      padding: 14px;
      min-height: 520px;
    }
    .panel h2 {
      margin: 0;
      font-size: 15px;
      color: var(--accent);
      font-weight: 600;
    }
    .subtext {
      margin-top: 4px;
      font-size: 12px;
      color: var(--muted);
    }
    .goal {
      margin-top: 18px;
      font-size: 22px;
      line-height: 1.3;
      color: var(--accent);
      min-height: 90px;
    }
    .meta-block, .task-list, .policy-grid, .provider-badges {
      margin-top: 18px;
    }
    .row {
      display: flex;
      justify-content: space-between;
      gap: 12px;
      padding: 6px 0;
      border-bottom: 1px solid #171717;
      font-size: 12px;
    }
    .row:last-child { border-bottom: none; }
    .label { color: var(--muted); }
    .progress-shell {
      margin-top: 14px;
      border: 1px solid var(--border);
      height: 12px;
      position: relative;
      background: #0c0c0c;
    }
    .progress-bar {
      height: 100%;
      width: 0%;
      background: linear-gradient(90deg, #6f603c, var(--accent));
      transition: width 0.25s ease;
    }
    .progress-text {
      margin-top: 8px;
      color: var(--muted);
      font-size: 12px;
    }
    .badge-row, .provider-badges {
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
      margin-top: 10px;
    }
    .badge {
      border: 1px solid var(--border);
      padding: 4px 8px;
      font-size: 11px;
      color: var(--text);
      background: #0d0d0d;
    }
    .log-panel-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 12px;
    }
    .btn {
      border: 1px solid var(--border);
      background: #0d0d0d;
      color: var(--text);
      padding: 6px 10px;
      font-size: 11px;
      cursor: pointer;
    }
    .btn:hover { color: var(--accent); }
    .log-feed, .think-feed {
      height: 34vh;
      overflow-y: auto;
      border: 1px solid var(--border);
      padding: 10px;
      background: #0b0b0b;
    }
    .think-feed { height: 28vh; margin-bottom: 10px; border-color: #2a2418; }
    .think-entry { color: #b8a078; font-size: 12px; padding: 6px 0; border-bottom: 1px solid #1a1814; }
    .services-grid { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 10px; }
    .service-pill {
      border: 1px solid var(--border);
      padding: 4px 8px;
      font-size: 10px;
      text-transform: uppercase;
      letter-spacing: 0.06em;
    }
    .service-pill.on { border-color: #3d4a32; color: #9cb87a; }
    .service-pill.off { color: var(--muted); opacity: 0.55; }
    .log-entry {
      border-bottom: 1px solid #171717;
      padding: 8px 0;
      font-size: 12px;
      line-height: 1.5;
      white-space: pre-wrap;
      word-break: break-word;
    }
    .log-entry:last-child { border-bottom: none; }
    .log-time { color: var(--muted); margin-right: 8px; }
    .tool-tag {
      color: var(--accent);
      margin-right: 8px;
    }
    .status-ok { color: var(--green); }
    .status-failed { color: var(--red); }
    .status-running { color: var(--yellow); }
    .task-item {
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 8px 0;
      font-size: 12px;
      border-bottom: 1px solid #171717;
    }
    .task-dot {
      width: 8px; height: 8px; border-radius: 50%;
      background: var(--yellow);
      flex: 0 0 8px;
    }
    .done { background: var(--green); }
    .failed { background: var(--red); }
    .running { background: var(--yellow); }
    .policy-grid .row span:last-child.allow { color: var(--green); }
    .policy-grid .row span:last-child.ask { color: var(--yellow); }
    .policy-grid .row span:last-child.deny { color: var(--red); }
    @media (max-width: 1200px) {
      .layout { grid-template-columns: 1fr 1fr; }
      .chat-messages { min-height: 280px; max-height: 40vh; }
    }
    @media (max-width: 980px) {
      .layout { grid-template-columns: 1fr; }
      .log-feed { height: 40vh; }
      .chat-messages { min-height: 240px; max-height: 50vh; }
      .topbar, .bottombar { grid-template-columns: 1fr; gap: 8px; }
      .center, .right { text-align: left; }
    }
  </style>
</head>
<body>
  <div class="topbar">
    <div class="runtime-title">IMOS    Operator Runtime</div>
    <div class="center" id="topCenter">session --  uptime --  provider --  <span id="authBadge">auth --</span></div>
    <div class="right">
      <span class="status-wrap">
        <span id="statusDot" class="status-dot status-red"></span>
        <span id="statusText">disconnected</span>
      </span>
    </div>
  </div>

  <div class="layout">
    <section class="panel">
      <h2>Project Storyboard</h2>
      <div class="subtext">Runtime flows  Session state</div>
      <div class="goal" id="goalText">Awaiting operator goal.</div>
      <div class="progress-shell"><div class="progress-bar" id="progressBar"></div></div>
      <div class="progress-text" id="progressText">[] 0/0</div>
      <div class="badge-row"><div class="badge" id="providerBadge">provider / model</div></div>
      <div class="meta-block">
        <div class="row"><span class="label">Session</span><span id="sessionId">--------</span></div>
        <div class="row"><span class="label">Messages</span><span id="messageCount">0</span></div>
        <div class="row"><span class="label">Providers</span><span id="providerChain">-</span></div>
      </div>
      <div class="task-list">
        <div class="subtext">Recent task flow</div>
        <div id="taskHistory"></div>
      </div>
    </section>

    <section class="panel panel-chat">
      <div class="log-panel-header">
        <div>
          <h2>Session Chat</h2>
          <div class="subtext">CLI and dashboard — live transcript</div>
        </div>
        <button class="btn" id="clearChatBtn">Clear</button>
      </div>
      <div class="chat-messages" id="chatMessages">
        <div class="chat-empty" id="chatEmpty">Messages from the operator CLI and this panel appear here.</div>
      </div>
      <form class="chat-compose" id="chatForm">
        <input id="chatInput" type="text" placeholder="Message IMOS…" autocomplete="off" />
        <button type="submit" class="btn">Send</button>
      </form>
    </section>

    <section class="panel">
      <div class="log-panel-header">
        <div>
          <h2>Operator Runtime</h2>
          <div class="subtext">Thinking  Execution</div>
        </div>
        <button class="btn" id="clearLogBtn">Clear</button>
      </div>
      <div class="subtext" style="margin-bottom:6px">Dynamic reasoning</div>
      <div class="think-feed" id="thinkFeed"></div>
      <div class="subtext" style="margin-bottom:6px">Tool execution</div>
      <div class="log-feed" id="logFeed"></div>
    </section>

    <section class="panel">
      <h2>Immersion Capsule</h2>
      <div class="subtext">Runtime state  Permissions</div>
      <div class="meta-block">
        <div class="row"><span class="label">Uptime</span><span id="uptimeValue">00:00:00</span></div>
        <div class="row"><span class="label">Memory entries</span><span id="memoryCount">0</span></div>
        <div class="row"><span class="label">Token estimate</span><span id="tokenEstimate">~0 tokens in session</span></div>
      </div>
      <div class="subtext" style="margin-top:12px">Models — add any provider</div>
      <div id="modelsList" style="font-size:11px;margin-bottom:8px;color:var(--muted)"></div>
      <form id="addModelForm" style="display:grid;gap:6px;margin-bottom:10px">
        <select id="modelType" class="btn" style="width:100%"></select>
        <input id="modelName" class="btn" placeholder="Model ID (any name)" />
        <input id="modelKey" class="btn" placeholder="API key (optional)" type="password" />
        <input id="modelBase" class="btn" placeholder="Base URL (optional)" />
        <button type="submit" class="btn">Add model</button>
      </form>
      <div class="subtext">Connected services</div>
      <div class="services-grid" id="servicesGrid"></div>
      <div class="policy-grid" id="policyGrid"></div>
      <div class="provider-badges" id="providerBadges"></div>
      <div style="margin-top:14px;">
        <button class="btn" id="refreshBtn">Refresh</button>
      </div>
    </section>
  </div>

  <div class="bottombar">
    <div>Sessions  Memory  Execution  All under one surface.</div>
    <div></div>
    <div></div>
  </div>

  <script>
    const socket = io();
    const logFeed = document.getElementById('logFeed');
    const thinkFeed = document.getElementById('thinkFeed');
    const chatMessages = document.getElementById('chatMessages');
    const chatEmpty = document.getElementById('chatEmpty');
    const chatForm = document.getElementById('chatForm');
    const chatInput = document.getElementById('chatInput');
    const servicesGrid = document.getElementById('servicesGrid');
    const modelsList = document.getElementById('modelsList');
    const modelType = document.getElementById('modelType');
    const addModelForm = document.getElementById('addModelForm');
    const progressBar = document.getElementById('progressBar');
    const progressText = document.getElementById('progressText');
    const goalText = document.getElementById('goalText');
    const providerBadge = document.getElementById('providerBadge');
    const taskHistory = document.getElementById('taskHistory');
    const policyGrid = document.getElementById('policyGrid');
    const providerBadges = document.getElementById('providerBadges');
    const statusDot = document.getElementById('statusDot');
    const statusText = document.getElementById('statusText');
    const topCenter = document.getElementById('topCenter');
    let lastEventAt = 0;
    let uptimeSeconds = 0;
    let currentTotal = 0;

    function appendThink(message) {
      const entry = document.createElement('div');
      entry.className = 'think-entry';
      entry.textContent = message;
      thinkFeed.appendChild(entry);
      while (thinkFeed.children.length > 40) thinkFeed.removeChild(thinkFeed.firstChild);
      thinkFeed.scrollTop = thinkFeed.scrollHeight;
    }

    function escapeHtml(text) {
      const div = document.createElement('div');
      div.textContent = text;
      return div.innerHTML;
    }

    function appendChat(role, content, timestamp) {
      if (!content) return;
      if (chatEmpty) chatEmpty.style.display = 'none';
      const normalized = (role || 'assistant').toLowerCase();
      const bubbleRole = normalized === 'user' ? 'user' : 'assistant';
      const label = bubbleRole === 'user' ? 'You' : 'IMOS';
      const entry = document.createElement('div');
      entry.className = 'chat-bubble ' + bubbleRole;
      const meta = document.createElement('span');
      meta.className = 'chat-meta';
      meta.textContent = label + (timestamp ? ' · ' + timestamp : '');
      const body = document.createElement('div');
      body.innerHTML = escapeHtml(content);
      entry.appendChild(meta);
      entry.appendChild(body);
      chatMessages.appendChild(entry);
      const bubbles = chatMessages.querySelectorAll('.chat-bubble');
      while (bubbles.length > 80) {
        bubbles[0].remove();
      }
      chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    async function fetchChatHistory() {
      try {
        const response = await fetch('/api/chat/messages');
        const data = await response.json();
        if (!Array.isArray(data) || !data.length) return;
        if (chatEmpty) chatEmpty.style.display = 'none';
        chatMessages.querySelectorAll('.chat-bubble').forEach((el) => el.remove());
        data.forEach((row) => {
          appendChat(row.role, row.content, row.timestamp);
        });
      } catch (err) {
        appendLog('chat history failed: ' + err, 'status-failed', 'chat');
      }
    }

    function renderServices(items) {
      servicesGrid.innerHTML = '';
      (items || []).forEach((svc) => {
        const pill = document.createElement('span');
        pill.className = 'service-pill ' + (svc.available ? 'on' : 'off');
        pill.title = svc.detail || '';
        pill.textContent = svc.label;
        servicesGrid.appendChild(pill);
      });
    }

    function appendLog(message, cls='', tag='', timestamp='') {
      const entry = document.createElement('div');
      entry.className = 'log-entry';
      const time = timestamp || new Date().toISOString();
      entry.innerHTML = '<span class="log-time">' + time + '</span>' +
        (tag ? '<span class="tool-tag">[' + tag + ']</span>' : '') +
        '<span class="' + cls + '">' + message + '</span>';
      logFeed.appendChild(entry);
      while (logFeed.children.length > 100) {
        logFeed.removeChild(logFeed.firstChild);
      }
      logFeed.scrollTop = logFeed.scrollHeight;
    }

    function renderPolicy(policy) {
      policyGrid.innerHTML = '<div class="subtext">Policy gates</div>';
      Object.entries(policy).forEach(([tool, value]) => {
        const row = document.createElement('div');
        row.className = 'row';
        row.innerHTML = '<span>' + tool + '</span><span class="' + value + '">' + value + '</span>';
        policyGrid.appendChild(row);
      });
    }

    function renderProviders(providers) {
      providerBadges.innerHTML = '';
      providers.forEach((provider) => {
        const badge = document.createElement('div');
        badge.className = 'badge';
        badge.textContent = provider;
        providerBadges.appendChild(badge);
      });
    }

    function renderTasks(tasks) {
      taskHistory.innerHTML = '';
      tasks.slice(0, 5).reverse().forEach((task) => {
        const item = document.createElement('div');
        item.className = 'task-item';
        const dot = document.createElement('div');
        dot.className = 'task-dot ' + task.status;
        const text = document.createElement('div');
        text.textContent = task.goal + '  ' + task.steps_done + '/' + task.steps_total;
        item.appendChild(dot);
        item.appendChild(text);
        taskHistory.appendChild(item);
      });
    }

    function setProgress(step, total) {
      currentTotal = total || 0;
      const width = total ? Math.max(0, Math.min(100, (step / total) * 100)) : 0;
      progressBar.style.width = width + '%';
      progressText.textContent = '[] ' + step + '/' + total;
    }

    function updateStatus(data) {
      providerBadge.textContent = data.provider + ' / ' + data.model;
      document.getElementById('sessionId').textContent = data.session_id;
      document.getElementById('messageCount').textContent = data.message_count;
      document.getElementById('providerChain').textContent = (data.providers_used || []).join('  ') || '-';
      document.getElementById('memoryCount').textContent = data.memory_count;
      document.getElementById('tokenEstimate').textContent = '~' + data.token_estimate + ' tokens in session';
      document.getElementById('uptimeValue').textContent = data.uptime;
      const auth = data.auth || {};
      const authBadge = document.getElementById('authBadge');
      if (authBadge) {
        authBadge.textContent = auth.signed_in ? ('signed in ' + (auth.email || '')) : 'not signed in';
        authBadge.style.color = auth.signed_in ? '#6f8f5a' : '#9a5b5b';
      }
      topCenter.textContent = 'session ' + data.session_id + '  uptime ' + data.uptime + '  ' + data.provider + ' / ' + data.model;
      renderPolicy(data.policy);
    }

    socket.on('auth', (data) => {
      const authBadge = document.getElementById('authBadge');
      if (authBadge) {
        authBadge.textContent = data.signed_in ? ('signed in ' + (data.email || '')) : 'not signed in';
        authBadge.style.color = data.signed_in ? '#6f8f5a' : '#9a5b5b';
      }
    });

    async function fetchStatus() {
      const response = await fetch('/api/status');
      const data = await response.json();
      updateStatus(data);
      const parts = data.uptime.split(':').map(Number);
      uptimeSeconds = (parts[0] * 3600) + (parts[1] * 60) + parts[2];
    }

    async function fetchTasks() {
      const response = await fetch('/api/tasks');
      const data = await response.json();
      renderTasks(data);
    }

    async function fetchMemory() {
      const response = await fetch('/api/memory');
      const data = await response.json();
      logFeed.innerHTML = '';
      data.forEach((item) => appendLog(item, '', '', 'memory'));
    }

    async function fetchProviders() {
      const response = await fetch('/api/providers');
      const data = await response.json();
      renderProviders(data);
    }

    async function fetchServices() {
      const response = await fetch('/api/services');
      const data = await response.json();
      renderServices(data);
    }

    function renderModels(payload) {
      const providers = payload.providers || payload || [];
      const def = payload.default || {};
      modelsList.innerHTML = providers.map(p =>
        '<div>' + (p.is_default ? '* ' : '  ') + p.id + ' — ' + p.type + ' / ' + (p.model || '') + '</div>'
      ).join('') || '<div>No models. Add one below.</div>';
      if (def.model) providerBadge.textContent = (def.type || '') + ' / ' + def.model;
    }

    async function fetchModels() {
      const response = await fetch('/api/models');
      const data = await response.json();
      renderModels(data);
      if (modelType && data.types) {
        modelType.innerHTML = data.types.map(t =>
          '<option value="' + t.type + '">' + t.name + '</option>'
        ).join('');
      }
    }

    if (addModelForm) {
      addModelForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const body = {
          type: modelType.value,
          model: document.getElementById('modelName').value,
          api_key: document.getElementById('modelKey').value,
          base_url: document.getElementById('modelBase').value,
          is_default: true
        };
        const res = await fetch('/api/models', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(body) });
        const data = await res.json();
        if (data.ok) {
          appendLog('model added: ' + data.provider.id + ' / ' + data.provider.model, 'status-ok', 'model');
          await fetchModels();
          await fetchServices();
        } else {
          appendLog('model add failed: ' + (data.error || 'unknown'), 'status-failed', 'model');
        }
      });
    }

    function tickUptime() {
      uptimeSeconds += 1;
      const h = String(Math.floor(uptimeSeconds / 3600)).padStart(2, '0');
      const m = String(Math.floor((uptimeSeconds % 3600) / 60)).padStart(2, '0');
      const s = String(uptimeSeconds % 60).padStart(2, '0');
      document.getElementById('uptimeValue').textContent = h + ':' + m + ':' + s;
    }

    function updateDotState() {
      const now = Date.now();
      statusDot.className = 'status-dot';
      if (!socket.connected) {
        statusDot.classList.add('status-red');
        statusText.textContent = 'disconnected';
        return;
      }
      if (now - lastEventAt > 30000) {
        statusDot.classList.add('status-yellow');
        statusText.textContent = 'idle';
      } else {
        statusDot.classList.add('status-green');
        statusText.textContent = 'connected';
      }
    }

    socket.on('connect', () => {
      lastEventAt = Date.now();
      updateDotState();
    });

    socket.on('disconnect', () => {
      updateDotState();
    });

    socket.on('step', (data) => {
      lastEventAt = Date.now();
      updateDotState();
      setProgress(data.step, data.total);
      const cls = data.status === 'done' ? 'status-ok' : (data.status === 'failed' ? 'status-failed' : 'status-running');
      appendLog('step ' + data.step + '/' + data.total + ' ' + data.status + '  ' + (data.output || data.description || ''), cls, data.tool);
    });

    socket.on('plan', (data) => {
      lastEventAt = Date.now();
      updateDotState();
      goalText.textContent = data.goal || 'Awaiting operator goal.';
      providerBadge.textContent = data.provider || providerBadge.textContent;
      setProgress(0, data.steps || 0);
      appendLog('plan started  ' + data.goal, 'status-running', 'plan');
      fetchTasks();
    });

    socket.on('log', (data) => {
      lastEventAt = Date.now();
      updateDotState();
      appendLog(data.message, '', '', data.timestamp);
    });

    socket.on('chat', (data) => {
      lastEventAt = Date.now();
      updateDotState();
      appendChat(data.role || 'assistant', data.content || '', data.timestamp);
    });

    socket.on('think', (data) => {
      lastEventAt = Date.now();
      updateDotState();
      if (data.analysis) appendThink('Analysis: ' + data.analysis);
      (data.reasoning_steps || []).forEach((step, idx) => appendThink((idx + 1) + '. ' + step));
      if (data.agents && data.agents.length) appendThink('Agents: ' + data.agents.join(', '));
    });

    socket.on('services', (data) => {
      renderServices(data.items || data);
    });

    document.getElementById('clearLogBtn').addEventListener('click', () => {
      logFeed.innerHTML = '';
      thinkFeed.innerHTML = '';
    });

    document.getElementById('clearChatBtn').addEventListener('click', () => {
      chatMessages.querySelectorAll('.chat-bubble').forEach((el) => el.remove());
      if (chatEmpty) {
        chatEmpty.style.display = '';
        if (!chatMessages.contains(chatEmpty)) chatMessages.appendChild(chatEmpty);
      }
    });

    if (chatForm) {
      chatForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const text = (chatInput.value || '').trim();
        if (!text) return;
        chatInput.value = '';
        chatInput.disabled = true;
        try {
          const res = await fetch('/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: text })
          });
          const data = await res.json();
          if (!data.ok) {
            appendChat('assistant', 'Send failed: ' + (data.error || 'unknown'));
          }
        } catch (err) {
          appendChat('assistant', 'Send failed: ' + err);
        } finally {
          chatInput.disabled = false;
          chatInput.focus();
        }
      });
    }

    document.getElementById('refreshBtn').addEventListener('click', async () => {
      await fetchStatus();
      await fetchTasks();
      await fetchProviders();
    });

    window.addEventListener('load', async () => {
      await fetchStatus();
      await fetchChatHistory();
      await fetchTasks();
      await fetchMemory();
      await fetchProviders();
      await fetchServices();
      await fetchModels();
      setInterval(tickUptime, 1000);
      setInterval(async () => {
        await fetchStatus();
      }, 5000);
      setInterval(updateDotState, 1000);
    });
  </script>
</body>
</html>
"""


class Dashboard:
    def __init__(self, memory, policy, tracker, ctx_getter, provider_getter, start_time) -> None:
        self.memory = memory
        self.policy = policy
        self.tracker = tracker
        self.ctx_getter = ctx_getter
        self.provider_getter = provider_getter
        self.start_time = start_time
        self.app = Flask(__name__)
        self.socketio = SocketIO(self.app, cors_allowed_origins="*", async_mode="threading")
        self._thread = None
        self._port = None
        self._chat_lock = threading.Lock()
        self._chat_inbox: deque[str] = deque()
        self._configure_routes()

    def _configure_routes(self) -> None:
        @self.app.get("/")
        def index():
            return DASHBOARD_HTML

        @self.app.get("/api/status")
        def api_status():
            provider, model = self.provider_getter()
            ctx = self.ctx_getter()
            stats = ctx.get_stats()
            tasks = self.tracker.all()
            done_count = sum(1 for task in tasks if task.get("status") == "done")
            running_count = sum(1 for task in tasks if task.get("status") == "running")
            failed_count = sum(1 for task in tasks if task.get("status") == "failed")
            delta = datetime.now() - self.start_time
            total_seconds = int(delta.total_seconds())
            hours, remainder = divmod(total_seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            auth_info = {"signed_in": False, "email": ""}
            try:
                from imos.auth import current_user

                auth_info = current_user()
            except Exception:
                pass
            return jsonify(
                {
                    "provider": provider,
                    "model": model,
                    "uptime": f"{hours:02d}:{minutes:02d}:{seconds:02d}",
                    "memory_count": len(self.memory.all().get("log", [])),
                    "tasks": {"done": done_count, "running": running_count, "failed": failed_count},
                    "policy": self.policy.all(),
                    "session_id": stats["session_id"][:8],
                    "message_count": stats["message_count"],
                    "token_estimate": stats["token_estimate"],
                    "providers_used": stats["providers_used"],
                    "auth": auth_info,
                }
            )

        @self.app.get("/api/tasks")
        def api_tasks():
            return jsonify(self.tracker.list_recent(20))

        @self.app.get("/api/memory")
        def api_memory():
            return jsonify(self.memory.get_log(30))

        @self.app.get("/api/session")
        def api_session():
            return jsonify(self.ctx_getter().get_stats())

        @self.app.get("/api/providers")
        def api_providers():
            available = []
            checks = {
                "anthropic": "ANTHROPIC_API_KEY",
                "openai": "OPENAI_API_KEY",
                "groq": "GROQ_API_KEY",
                "gemini": "GOOGLE_GEMINI_API_KEY",
                "openrouter": "OPENROUTER_API_KEY",
                "ollama": None,
                "huggingface": "HUGGINGFACE_API_KEY",
            }
            for provider, key in checks.items():
                if key is None or os.getenv(key):
                    available.append(provider)
            return jsonify(available)

        @self.app.get("/api/services")
        def api_services():
            from core.services_catalog import list_all_services

            return jsonify(list_all_services())

        @self.app.get("/api/models")
        def api_models():
            from core import model_manager
            from core.services_catalog import list_provider_types

            return jsonify(
                {
                    "providers": model_manager.load_providers(),
                    "default": model_manager.get_default(),
                    "types": list_provider_types(),
                }
            )

        @self.app.post("/api/models")
        def api_models_add():
            from core import model_manager

            payload = request.get_json(silent=True) or {}
            provider_type = str(payload.get("type") or payload.get("provider", "")).strip().lower()
            model_name = str(payload.get("model", "")).strip()
            if not provider_type or not model_name:
                return jsonify({"ok": False, "error": "type and model are required"}), 400
            if provider_type not in model_manager.PROVIDER_TYPES:
                return jsonify({"ok": False, "error": f"unknown provider type: {provider_type}"}), 400
            row = model_manager.add_provider(
                {
                    "id": str(payload.get("id") or f"{provider_type}-{model_name.replace('/', '-')[:28]}"),
                    "name": str(payload.get("name") or f"{model_manager.PROVIDER_TYPES[provider_type]['name']} ({model_name})"),
                    "type": provider_type,
                    "model": model_name,
                    "api_key": str(payload.get("api_key", "")).strip(),
                    "base_url": str(payload.get("base_url") or model_manager.PROVIDER_TYPES[provider_type].get("base_url", "")).strip(),
                    "enabled": True,
                    "is_default": bool(payload.get("is_default", True)),
                }
            )
            return jsonify({"ok": True, "provider": row, "default": model_manager.get_default()})

        @self.app.post("/api/models/<provider_id>/default")
        def api_models_default(provider_id: str):
            from core import model_manager

            try:
                row = model_manager.set_default(provider_id)
            except KeyError:
                return jsonify({"ok": False, "error": "not found"}), 404
            return jsonify({"ok": True, "provider": row})

        @self.app.get("/api/chat/messages")
        def api_chat_messages():
            ctx = self.ctx_getter()
            items = []
            for row in ctx.data.get("messages", [])[-100:]:
                role = str(row.get("role", "")).strip().lower()
                if role not in {"user", "assistant"}:
                    continue
                content = str(row.get("content", "")).strip()
                if not content:
                    continue
                items.append(
                    {
                        "role": role,
                        "content": content,
                        "timestamp": row.get("timestamp", ""),
                    }
                )
            return jsonify(items)

        @self.app.post("/api/chat")
        def api_chat_send():
            payload = request.get_json(silent=True) or {}
            text = str(payload.get("message") or payload.get("text") or "").strip()
            if not text:
                return jsonify({"ok": False, "error": "message is required"}), 400
            provider, model = self.provider_getter()
            ctx = self.ctx_getter()
            ctx.add_message("user", text, provider, model)
            self.emit_chat("user", text)
            with self._chat_lock:
                self._chat_inbox.append(text)
            self.emit_log(f"dashboard chat queued: {text[:120]}")
            return jsonify({"ok": True, "queued": True})

    def pop_chat_inbox(self) -> str | None:
        with self._chat_lock:
            if not self._chat_inbox:
                return None
            return self._chat_inbox.popleft()

    def start(self, port=7070) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._port = port

        def _run():
            self.socketio.run(self.app, host="127.0.0.1", port=port, allow_unsafe_werkzeug=True)

        self._thread = threading.Thread(target=_run, daemon=True)
        self._thread.start()
        print(f"imos  dashboard live at http://localhost:{port}")

    def emit_step(self, step_data: dict) -> None:
        try:
            self.socketio.emit("step", step_data)
        except Exception:
            return

    def emit_plan(self, plan_data: dict) -> None:
        try:
            self.socketio.emit("plan", plan_data)
        except Exception:
            return

    def emit_log(self, message: str) -> None:
        try:
            self.socketio.emit("log", {"message": message, "timestamp": datetime.now().isoformat()})
        except Exception:
            return

    def emit_chat(self, role: str, content: str) -> None:
        try:
            self.socketio.emit(
                "chat",
                {
                    "role": role,
                    "content": content,
                    "timestamp": datetime.now().isoformat(),
                },
            )
        except Exception:
            return

    def emit_think(self, think_data: dict) -> None:
        try:
            self.socketio.emit("think", think_data)
        except Exception:
            return

    def emit_services(self, services: list) -> None:
        try:
            self.socketio.emit("services", {"items": services})
        except Exception:
            return

    def emit_models(self, providers: list, default: dict | None = None) -> None:
        try:
            self.socketio.emit("models", {"providers": providers, "default": default or {}})
        except Exception:
            return

    def emit_auth(self, auth_info: dict) -> None:
        try:
            self.socketio.emit("auth", auth_info)
        except Exception:
            return
