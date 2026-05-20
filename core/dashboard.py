import os
import threading
from datetime import datetime

from flask import Flask, jsonify
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
      grid-template-columns: 30% 40% 30%;
      gap: 14px;
      padding: 14px;
      min-height: calc(100vh - 104px);
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
    .log-feed {
      height: 76vh;
      overflow-y: auto;
      border: 1px solid var(--border);
      padding: 10px;
      background: #0b0b0b;
    }
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
    @media (max-width: 980px) {
      .layout { grid-template-columns: 1fr; }
      .log-feed { height: 40vh; }
      .topbar, .bottombar { grid-template-columns: 1fr; gap: 8px; }
      .center, .right { text-align: left; }
    }
  </style>
</head>
<body>
  <div class="topbar">
    <div class="runtime-title">IMOS    Operator Runtime</div>
    <div class="center" id="topCenter">session --  uptime --  provider --</div>
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

    <section class="panel">
      <div class="log-panel-header">
        <div>
          <h2>Smart Critiques</h2>
          <div class="subtext">Execution log  Tool results</div>
        </div>
        <button class="btn" id="clearLogBtn">Clear</button>
      </div>
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
      topCenter.textContent = 'session ' + data.session_id + '  uptime ' + data.uptime + '  ' + data.provider + ' / ' + data.model;
      renderPolicy(data.policy);
    }

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

    document.getElementById('clearLogBtn').addEventListener('click', () => {
      logFeed.innerHTML = '';
    });

    document.getElementById('refreshBtn').addEventListener('click', async () => {
      await fetchStatus();
      await fetchTasks();
      await fetchProviders();
    });

    window.addEventListener('load', async () => {
      await fetchStatus();
      await fetchTasks();
      await fetchMemory();
      await fetchProviders();
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
