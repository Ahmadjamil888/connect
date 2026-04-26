from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict
from urllib.parse import parse_qs, urlparse

from gateway_runtime.node_client import render_node_client_html
from gateway_runtime.runtime import AgentRuntime


def render_dashboard_html() -> str:
    return """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>CONNECT Operator Dashboard</title>
  <style>
    :root {
      --bg: #212121;
      --bg-soft: #171717;
      --sidebar: #1b1b1b;
      --panel: #262626;
      --panel-2: #2f2f2f;
      --line: #353535;
      --text: #f5f5f5;
      --muted: #a8a8a8;
      --accent: #27F3A9;
      --accent-soft: rgba(39, 243, 169, 0.16);
      --accent-strong: rgba(39, 243, 169, 0.28);
      --danger: #ff6b6b;
    }
    * { box-sizing: border-box; }
    html, body { height: 100%; }
    body {
      margin: 0;
      background:
        radial-gradient(circle at top center, rgba(39,243,169,0.05), transparent 28%),
        var(--bg);
      color: var(--text);
      font-family: Inter, "Segoe UI", sans-serif;
    }
    button, input, select, textarea {
      font: inherit;
      color: inherit;
    }
    button {
      cursor: pointer;
      border: 0;
    }
    .app {
      min-height: 100vh;
      display: grid;
      grid-template-columns: 76px minmax(0, 1fr);
    }
    .rail {
      background: var(--sidebar);
      border-right: 1px solid var(--line);
      display: flex;
      flex-direction: column;
      align-items: center;
      padding: 12px 0;
      gap: 14px;
      position: sticky;
      top: 0;
      height: 100vh;
    }
    .brand {
      width: 44px;
      height: 44px;
      border-radius: 14px;
      background: linear-gradient(180deg, rgba(39,243,169,0.14), rgba(39,243,169,0.05));
      border: 1px solid rgba(39,243,169,0.18);
      display: grid;
      place-items: center;
      font-weight: 800;
      letter-spacing: 0.08em;
    }
    .rail-btn, .profile-chip {
      width: 52px;
      height: 52px;
      border-radius: 16px;
      background: transparent;
      color: var(--text);
      border: 1px solid transparent;
      display: grid;
      place-items: center;
      font-size: 20px;
    }
    .rail-btn.active {
      background: rgba(255,255,255,0.06);
      border-color: rgba(255,255,255,0.06);
    }
    .rail-spacer { flex: 1; }
    .profile-chip {
      width: 40px;
      height: 40px;
      border-radius: 999px;
      background: rgba(39,243,169,0.16);
      color: var(--accent);
      font-size: 14px;
      margin-bottom: 8px;
    }
    .main {
      min-width: 0;
      display: flex;
      flex-direction: column;
      min-height: 100vh;
    }
    .topbar {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 16px 24px 0;
      gap: 16px;
    }
    .topbar-title {
      display: flex;
      align-items: center;
      gap: 10px;
      font-size: 22px;
      font-weight: 700;
    }
    .topbar-title small {
      color: var(--muted);
      font-size: 13px;
      font-weight: 500;
    }
    .topbar-actions {
      display: flex;
      align-items: center;
      gap: 12px;
    }
    .plus-badge {
      border-radius: 999px;
      padding: 14px 20px;
      background: rgba(39,243,169,0.18);
      color: var(--text);
      font-weight: 700;
      border: 1px solid rgba(39,243,169,0.18);
    }
    .icon-ghost {
      width: 36px;
      height: 36px;
      border-radius: 999px;
      display: grid;
      place-items: center;
      color: var(--muted);
    }
    .hero {
      flex: 1;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      padding: 30px 24px 20px;
      min-height: 520px;
    }
    .hero-title {
      font-size: clamp(42px, 4vw, 64px);
      line-height: 1.08;
      font-weight: 500;
      letter-spacing: -0.03em;
      margin: 0 0 28px;
      text-align: center;
    }
    .composer {
      width: min(100%, 1150px);
      border-radius: 30px;
      background: #2f2f2f;
      border: 1px solid #3a3a3a;
      box-shadow: 0 16px 40px rgba(0,0,0,0.26);
      padding: 12px 16px;
    }
    .composer-row {
      display: grid;
      grid-template-columns: 44px 1fr 40px 56px;
      gap: 12px;
      align-items: center;
    }
    .composer-icon, .voice-btn {
      width: 44px;
      height: 44px;
      border-radius: 999px;
      background: transparent;
      display: grid;
      place-items: center;
      color: var(--text);
      font-size: 18px;
    }
    .composer-input {
      border: 0;
      outline: 0;
      background: transparent;
      font-size: 18px;
      color: var(--text);
      min-width: 0;
    }
    .composer-input::placeholder { color: #b5b5b5; }
    .send-btn {
      width: 56px;
      height: 56px;
      border-radius: 999px;
      background: #f3f3f3;
      color: #111;
      font-size: 20px;
      box-shadow: 0 0 0 8px rgba(255,255,255,0.03);
    }
    .hero-actions {
      display: flex;
      gap: 12px;
      flex-wrap: wrap;
      justify-content: center;
      margin-top: 22px;
    }
    .chip {
      border-radius: 999px;
      padding: 14px 20px;
      background: transparent;
      border: 1px solid #4a4a4a;
      color: var(--text);
      font-size: 15px;
    }
    .content {
      display: grid;
      grid-template-columns: minmax(0, 1.18fr) minmax(320px, 0.82fr);
      gap: 18px;
      padding: 0 24px 24px;
    }
    .stack {
      display: grid;
      gap: 18px;
      min-width: 0;
    }
    .panel {
      border-radius: 22px;
      background: var(--panel);
      border: 1px solid var(--line);
      padding: 18px;
      min-width: 0;
    }
    .section-head {
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 12px;
      margin-bottom: 14px;
    }
    .section-head h2 {
      margin: 0;
      font-size: 15px;
      font-weight: 600;
    }
    .subtle {
      color: var(--muted);
      font-size: 12px;
      letter-spacing: 0.02em;
      text-transform: uppercase;
    }
    .status-badge {
      border-radius: 999px;
      padding: 6px 10px;
      background: var(--accent-soft);
      color: var(--accent);
      font-size: 12px;
      font-weight: 700;
    }
    .metric-grid {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 12px;
    }
    .metric {
      border-radius: 18px;
      background: #2d2d2d;
      border: 1px solid #383838;
      padding: 14px;
    }
    .metric-label {
      color: var(--muted);
      font-size: 12px;
    }
    .metric-value {
      font-size: 24px;
      font-weight: 700;
      margin-top: 6px;
    }
    .panel-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 18px;
    }
    .card-list {
      display: grid;
      gap: 10px;
    }
    .row-card {
      border-radius: 16px;
      background: var(--panel-2);
      border: 1px solid #393939;
      padding: 12px 14px;
      min-width: 0;
    }
    .row-title {
      font-weight: 600;
      margin-bottom: 4px;
      word-break: break-word;
    }
    .row-meta, .row-extra {
      color: var(--muted);
      font-size: 13px;
      line-height: 1.45;
      word-break: break-word;
    }
    .row-extra { margin-top: 6px; }
    .toolbar {
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
      margin-bottom: 12px;
    }
    .select, .field {
      background: #2c2c2c;
      border: 1px solid #3b3b3b;
      border-radius: 14px;
      outline: 0;
      padding: 11px 13px;
      color: var(--text);
      width: 100%;
    }
    .toolbar .select {
      width: auto;
      min-width: 180px;
    }
    .json-box {
      margin: 0;
      white-space: pre-wrap;
      word-break: break-word;
      font-family: Consolas, "SFMono-Regular", monospace;
      font-size: 12px;
      line-height: 1.5;
      color: #d4d4d4;
      background: #212121;
      border: 1px solid #343434;
      border-radius: 16px;
      padding: 14px;
      max-height: 260px;
      overflow: auto;
    }
    .integration-grid {
      display: grid;
      gap: 12px;
    }
    .integration-card {
      border-radius: 18px;
      background: #2e2e2e;
      border: 1px solid #393939;
      padding: 14px;
    }
    .integration-top {
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: flex-start;
      margin-bottom: 10px;
    }
    .integration-card h3 {
      margin: 0 0 4px;
      font-size: 15px;
    }
    .integration-card p {
      margin: 0;
      color: var(--muted);
      font-size: 13px;
      line-height: 1.45;
    }
    .integration-form {
      display: grid;
      gap: 8px;
      margin-top: 10px;
    }
    .save-btn {
      border-radius: 12px;
      background: var(--accent);
      color: #042b1c;
      padding: 10px 12px;
      font-weight: 700;
    }
    .ghost-btn {
      border-radius: 12px;
      background: #313131;
      color: var(--text);
      padding: 10px 12px;
      border: 1px solid #3c3c3c;
    }
    .status-ok { color: var(--accent); }
    .status-bad { color: var(--danger); }
    .footer-note {
      color: var(--muted);
      font-size: 12px;
      padding-top: 6px;
    }
    @media (max-width: 1180px) {
      .content, .panel-grid {
        grid-template-columns: 1fr;
      }
      .metric-grid {
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }
    }
    @media (max-width: 860px) {
      .app {
        grid-template-columns: 1fr;
      }
      .rail {
        display: none;
      }
      .topbar {
        padding: 16px 16px 0;
      }
      .hero {
        padding: 24px 16px 18px;
        min-height: 420px;
      }
      .hero-title {
        font-size: clamp(34px, 8vw, 48px);
        margin-bottom: 20px;
      }
      .composer-row {
        grid-template-columns: 38px 1fr 34px 48px;
        gap: 8px;
      }
      .composer-icon, .voice-btn {
        width: 38px;
        height: 38px;
      }
      .send-btn {
        width: 48px;
        height: 48px;
      }
      .content {
        padding: 0 16px 16px;
      }
    }
  </style>
</head>
<body>
  <div class="app">
    <aside class="rail">
      <div class="brand">C</div>
      <button class="rail-btn active" title="Operator">✎</button>
      <button class="rail-btn" title="Search">⌕</button>
      <button class="rail-btn" title="Sessions">◌</button>
      <button class="rail-btn" title="Integrations">⌁</button>
      <div class="rail-spacer"></div>
      <div class="profile-chip">CN</div>
    </aside>
    <main class="main">
      <div class="topbar">
        <div class="topbar-title">
          <span>CONNECT Operator</span>
          <small id="topbarSubtext">operator dashboard</small>
        </div>
        <div class="topbar-actions">
          <div class="plus-badge" id="plusBadge">Gateway</div>
          <div class="icon-ghost">⌔</div>
          <div class="icon-ghost">⟳</div>
        </div>
      </div>
      <section class="hero">
        <h1 class="hero-title">What should CONNECT handle next?</h1>
        <div class="composer">
          <div class="composer-row">
            <button class="composer-icon" title="New session">＋</button>
            <input id="askInput" class="composer-input" placeholder="Ask CONNECT to code, search, route, inspect, or message..." />
            <button class="voice-btn" id="refreshButton" title="Refresh">↻</button>
            <button class="send-btn" id="askButton" title="Run">➤</button>
          </div>
        </div>
        <div class="hero-actions">
          <button class="chip">Connect an integration</button>
          <button class="chip">Write or edit code</button>
          <button class="chip">Look something up</button>
        </div>
      </section>
      <section class="content">
        <div class="stack">
          <section class="panel">
            <div class="section-head">
              <div>
                <div class="subtle">Live control plane</div>
                <h2>Runtime overview</h2>
              </div>
              <span class="status-badge" id="providerBadge">provider</span>
            </div>
            <div class="metric-grid">
              <div class="metric"><div class="metric-label">Provider</div><div class="metric-value" id="providerValue">-</div></div>
              <div class="metric"><div class="metric-label">Sessions</div><div class="metric-value" id="sessionValue">0</div></div>
              <div class="metric"><div class="metric-label">Tools</div><div class="metric-value" id="toolValue">0</div></div>
              <div class="metric"><div class="metric-label">Live Services</div><div class="metric-value" id="serviceValue">0</div></div>
            </div>
          </section>
          <section class="panel">
            <div class="section-head">
              <div>
                <div class="subtle">Conversation</div>
                <h2>Quick Ask</h2>
              </div>
              <span class="status-badge" id="chatBadge">history</span>
            </div>
            <pre class="json-box" id="askOutput">No request yet.</pre>
          </section>
          <section class="panel">
            <div class="section-head">
              <div>
                <div class="subtle">Memory and sessions</div>
                <h2>Recent activity</h2>
              </div>
              <span class="status-badge" id="sessionBadge">idle</span>
            </div>
            <div class="panel-grid">
              <div>
                <div class="toolbar"><button class="ghost-btn" type="button">Sessions</button></div>
                <div id="sessionList" class="card-list"></div>
              </div>
              <div>
                <div class="toolbar"><button class="ghost-btn" type="button">Memory</button></div>
                <div id="memoryList" class="card-list"></div>
              </div>
            </div>
          </section>
          <section class="panel">
            <div class="section-head">
              <div>
                <div class="subtle">Tools</div>
                <h2>Typed capability catalog</h2>
              </div>
              <span class="status-badge" id="toolBadge">catalog</span>
            </div>
            <div class="toolbar">
              <select id="groupFilter" class="select">
                <option value="">All groups</option>
              </select>
            </div>
            <div id="toolList" class="card-list"></div>
          </section>
        </div>
        <div class="stack">
          <section class="panel">
            <div class="section-head">
              <div>
                <div class="subtle">Connectors</div>
                <h2>Integrations</h2>
              </div>
              <span class="status-badge">dashboard</span>
            </div>
            <div id="integrationList" class="integration-grid"></div>
          </section>
          <section class="panel">
            <div class="section-head">
              <div>
                <div class="subtle">Active thread</div>
                <h2>Chat Session</h2>
              </div>
              <span class="status-badge" id="nodeBadge">nodes</span>
            </div>
            <div id="chatList" class="card-list"></div>
          </section>
          <section class="panel">
            <div class="section-head">
              <div>
                <div class="subtle">Devices and canvas</div>
                <h2>Nodes and surface state</h2>
              </div>
              <span class="status-badge" id="canvasBadge">canvas</span>
            </div>
            <div class="panel-grid">
              <div>
                <div class="toolbar"><button class="ghost-btn" type="button">Nodes</button></div>
                <div id="nodeList" class="card-list"></div>
              </div>
              <div>
                <div class="toolbar"><button class="ghost-btn" type="button">Canvas</button></div>
                <div id="canvasList" class="card-list"></div>
              </div>
            </div>
          </section>
          <section class="panel">
            <div class="section-head">
              <div>
                <div class="subtle">Diagnostics</div>
                <h2>Gateway status</h2>
              </div>
              <span class="status-badge" id="statusBadge">live</span>
            </div>
            <pre class="json-box" id="statusOutput">Loading...</pre>
            <div class="footer-note">This panel reads live runtime state. It does not claim a service is running unless the local runtime reports it.</div>
          </section>
        </div>
      </section>
    </main>
  </div>
  <script>
    let sessions = [];
    let tools = [];

    async function loadJson(url, options) {
      const res = await fetch(url, options);
      return await res.json();
    }

    function escapeHtml(value) {
      return String(value || "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#39;");
    }

    function rowHtml(title, meta, extra) {
      return `<div class="row-card"><div class="row-title">${escapeHtml(title)}</div><div class="row-meta">${escapeHtml(meta)}</div>${extra ? `<div class="row-extra">${escapeHtml(extra)}</div>` : ""}</div>`;
    }

    function integrationCard(kind, title, description, connected, fields) {
      const formFields = fields.map(field => `<input class="field" data-kind="${kind}" data-field="${field.name}" placeholder="${escapeHtml(field.placeholder)}" type="${field.type || "text"}" />`).join("");
      return `
        <div class="integration-card">
          <div class="integration-top">
            <div>
              <h3>${escapeHtml(title)}</h3>
              <p>${escapeHtml(description)}</p>
            </div>
            <div class="${connected ? "status-ok" : "status-bad"}">${connected ? "Connected" : "Not connected"}</div>
          </div>
          <div class="integration-form">
            ${formFields}
            <button class="save-btn" data-save-kind="${kind}">Save ${escapeHtml(title)}</button>
          </div>
        </div>`;
    }

    function renderSessions() {
      const target = document.getElementById("sessionList");
      document.getElementById("sessionValue").textContent = String(sessions.length);
      document.getElementById("sessionBadge").textContent = sessions.length ? "active" : "empty";
      target.innerHTML = sessions.length
        ? sessions.map(s => rowHtml(`${s.name} - ${s.id}`, `status=${s.status} profile=${s.profile}`, `updated ${s.updated_at}`)).join("")
        : rowHtml("No sessions", "Create one by asking CONNECT a question.");
    }

    function renderMemory(items) {
      const target = document.getElementById("memoryList");
      target.innerHTML = items.length
        ? items.slice().reverse().map(i => rowHtml(i.kind || "memory", i.content || "", i.ts || "")).join("")
        : rowHtml("No memory yet", "Recent context will appear here.");
    }

    function renderChat(items) {
      const target = document.getElementById("chatList");
      document.getElementById("chatBadge").textContent = `${items.length} msgs`;
      target.innerHTML = items.length
        ? items.slice().reverse().map(i => rowHtml(i.role || "message", i.content || "", i.ts || "")).join("")
        : rowHtml("No chat yet", "Run a task from the composer to create history.");
    }

    function renderNodes(items) {
      const target = document.getElementById("nodeList");
      document.getElementById("nodeBadge").textContent = `${items.length} nodes`;
      target.innerHTML = items.length
        ? items.map(n => rowHtml(`${n.name} - ${n.node_id}`, `${n.platform} - last seen ${n.last_seen}`, Object.keys(n.location || {}).length ? JSON.stringify(n.location) : "")).join("")
        : rowHtml("No paired nodes", "Pair a node from the mobile client when ready.");
    }

    function renderCanvas(snapshot) {
      const cards = snapshot.cards || [];
      document.getElementById("canvasBadge").textContent = `${cards.length} cards`;
      document.getElementById("canvasList").innerHTML = cards.length
        ? cards.slice().reverse().map(c => rowHtml(c.title || c.id, c.kind || "note", c.content || "")).join("")
        : rowHtml("Canvas empty", "Use canvas tools to publish cards.");
    }

    function renderStatus(status) {
      const liveServices = Object.values(status.services || {}).filter(s => s && s.running).length;
      document.getElementById("providerValue").textContent = status.provider || "none";
      document.getElementById("providerBadge").textContent = status.provider || "none";
      document.getElementById("toolValue").textContent = String(status.tool_count || 0);
      document.getElementById("serviceValue").textContent = String(liveServices);
      document.getElementById("toolBadge").textContent = `${status.implemented_tool_count || 0} live / ${status.stubbed_tool_count || 0} stub`;
      document.getElementById("topbarSubtext").textContent = status.signed_in ? `signed in as ${status.current_user || "operator"}` : "operator dashboard";
      document.getElementById("plusBadge").textContent = liveServices ? `${liveServices} live` : "idle";
      document.getElementById("statusBadge").textContent = liveServices ? "live" : "idle";
      document.getElementById("statusOutput").textContent = JSON.stringify(status, null, 2);
    }

    function renderTools() {
      const filter = document.getElementById("groupFilter").value;
      const visible = filter ? tools.filter(t => t.group === filter) : tools;
      document.getElementById("toolList").innerHTML = visible.length
        ? visible.map(t => rowHtml(t.name, `${t.group} - ${t.implemented ? "implemented" : "stub"}`, t.description || "")).join("")
        : rowHtml("No tools", "The selected group has no tools.");
    }

    function fillGroups() {
      const select = document.getElementById("groupFilter");
      const current = select.value;
      const groups = [...new Set(tools.map(t => t.group))].sort();
      select.innerHTML = `<option value="">All groups</option>` + groups.map(g => `<option value="${escapeHtml(g)}">${escapeHtml(g)}</option>`).join("");
      select.value = groups.includes(current) ? current : "";
      select.onchange = renderTools;
    }

    function renderIntegrations(snapshot) {
      document.getElementById("integrationList").innerHTML = [
        integrationCard("github", "GitHub", "Store a personal token for repository operations.", !!snapshot.github?.connected, [
          {name: "token", placeholder: "GitHub token", type: "password"}
        ]),
        integrationCard("telegram", "Telegram", "Bot token plus default chat id for send and receive.", !!snapshot.telegram?.connected, [
          {name: "bot_token", placeholder: "Telegram bot token", type: "password"},
          {name: "default_chat_id", placeholder: "Default chat id"}
        ]),
        integrationCard("slack_webhook", "Slack webhook", "Simple outbound Slack delivery by named webhook.", !!snapshot.slack_webhooks?.connected, [
          {name: "name", placeholder: "Webhook name"},
          {name: "webhook_url", placeholder: "Slack webhook URL", type: "password"}
        ]),
        integrationCard("slack_bot", "Slack bot", "Bidirectional bot mode with bot token and signing secret.", !!snapshot.slack_bot?.connected, [
          {name: "bot_token", placeholder: "Slack bot token", type: "password"},
          {name: "signing_secret", placeholder: "Slack signing secret", type: "password"}
        ]),
        integrationCard("discord", "Discord", "Send messages through named Discord webhooks.", !!snapshot.discord?.connected, [
          {name: "name", placeholder: "Webhook name"},
          {name: "webhook_url", placeholder: "Discord webhook URL", type: "password"}
        ]),
        integrationCard("whatsapp", "WhatsApp", "Twilio WhatsApp connector for inbound and outbound delivery.", !!snapshot.whatsapp?.connected, [
          {name: "account_sid", placeholder: "Twilio account SID"},
          {name: "auth_token", placeholder: "Twilio auth token", type: "password"},
          {name: "from_number", placeholder: "whatsapp:+1234567890"}
        ])
      ].join("");

      document.querySelectorAll("[data-save-kind]").forEach(button => {
        button.onclick = async () => {
          const kind = button.getAttribute("data-save-kind");
          const payload = {};
          document.querySelectorAll(`[data-kind="${kind}"]`).forEach(field => {
            payload[field.getAttribute("data-field")] = field.value;
          });
          const original = button.textContent;
          button.textContent = "Saving...";
          const result = await loadJson("/api/integrations", {
            method: "POST",
            headers: {"Content-Type":"application/json"},
            body: JSON.stringify({kind, payload})
          });
          button.textContent = result.ok ? "Saved" : "Save failed";
          setTimeout(() => { button.textContent = original; }, 1200);
          refresh();
        };
      });
    }

    async function refresh() {
      const [status, toolRows, sessionRows, memoryRows, nodeRows, canvasSnapshot, integrationRows] = await Promise.all([
        loadJson("/api/status"),
        loadJson("/api/tools"),
        loadJson("/api/sessions"),
        loadJson("/api/memory"),
        loadJson("/api/nodes"),
        loadJson("/api/canvas"),
        loadJson("/api/integrations")
      ]);
      tools = toolRows.items || [];
      sessions = sessionRows.items || [];
      const activeSessionId = (sessions[0] || {}).id || "";
      const historyRows = activeSessionId ? await loadJson(`/api/session-history?session_id=${encodeURIComponent(activeSessionId)}&limit=12`) : {items: []};
      renderStatus(status);
      renderSessions();
      renderMemory(memoryRows.items || []);
      renderChat(historyRows.items || []);
      renderNodes(nodeRows.items || []);
      renderCanvas(canvasSnapshot);
      fillGroups();
      renderTools();
      renderIntegrations(integrationRows);
    }

    async function ask() {
      const input = document.getElementById("askInput");
      const content = input.value.trim();
      if (!content) return;
      document.getElementById("askOutput").textContent = "Running...";
      const result = await loadJson("/api/ask", {
        method: "POST",
        headers: {"Content-Type":"application/json"},
        body: JSON.stringify({content})
      });
      document.getElementById("askOutput").textContent = JSON.stringify(result, null, 2);
      input.value = "";
      refresh();
    }

    document.getElementById("askButton").onclick = ask;
    document.getElementById("refreshButton").onclick = refresh;
    document.getElementById("askInput").addEventListener("keydown", (event) => {
      if (event.key === "Enter") ask();
    });
    refresh();
    setInterval(refresh, 5000);
  </script>
</body>
</html>"""


class DashboardServer:
    def __init__(self, runtime: AgentRuntime, host: str = "127.0.0.1", port: int = 18890):
        self.runtime = runtime
        self.host = host
        self.port = port

    def make_handler(self):
        runtime = self.runtime

        class Handler(BaseHTTPRequestHandler):
            def _auth_required(self) -> bool:
                return runtime.auth.requires_auth(runtime.config.deployment_mode)

            def _request_authenticated(self) -> bool:
                return runtime.auth.request_authenticated(self.headers)

            def _redirect(self, location: str):
                self.send_response(302)
                self.send_header("Location", location)
                self.end_headers()

            def _send_json(self, payload: Dict[str, Any], status: int = 200):
                raw = json.dumps(payload).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            def _send_html(self, html: str):
                raw = html.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            def log_message(self, format: str, *args):
                return

            def do_GET(self):
                parsed = urlparse(self.path)
                if parsed.path == "/auth/login":
                    next_path = parse_qs(parsed.query).get("next", ["/"])[0]
                    self._send_html(runtime.auth.render_signin_html("/auth/clerk/callback", next_path))
                    return
                if parsed.path == "/":
                    if self._auth_required() and not self._request_authenticated():
                        self._redirect("/auth/login?next=/")
                        return
                    self._send_html(render_dashboard_html())
                    return
                if parsed.path == "/node-client":
                    if self._auth_required() and not self._request_authenticated():
                        self._redirect("/auth/login?next=/node-client")
                        return
                    self._send_html(render_node_client_html())
                    return
                if self._auth_required() and parsed.path.startswith("/api/") and parsed.path not in {"/api/node/manifest"} and not self._request_authenticated():
                    self._send_json({"ok": False, "error": "authentication required"}, status=401)
                    return
                if parsed.path == "/api/status":
                    self._send_json(runtime.gateway_status())
                    return
                if parsed.path == "/api/tools":
                    self._send_json({"items": runtime.catalog.list()})
                    return
                if parsed.path == "/api/sessions":
                    self._send_json({"items": runtime.sessions.list()})
                    return
                if parsed.path == "/api/session-history":
                    query = parse_qs(parsed.query)
                    session_id = query.get("session_id", [""])[0]
                    limit = int(query.get("limit", ["20"])[0])
                    self._send_json({"items": runtime.sessions.history(session_id, limit) if session_id else []})
                    return
                if parsed.path == "/api/memory":
                    query = parse_qs(parsed.query)
                    session_id = query.get("session_id", [""])[0]
                    limit = int(query.get("limit", ["10"])[0])
                    self._send_json({"items": runtime.memory.get_recent(session_id, limit)})
                    return
                if parsed.path == "/api/nodes":
                    self._send_json({"items": runtime.nodes.list_nodes()})
                    return
                if parsed.path == "/api/node/manifest":
                    self._send_json(runtime.node_manifest())
                    return
                if parsed.path == "/api/canvas":
                    self._send_json(runtime.canvas.snapshot())
                    return
                if parsed.path == "/api/workflows":
                    self._send_json({"items": runtime.workflows.list_workflows()})
                    return
                if parsed.path == "/api/integrations":
                    self._send_json(runtime.integration_snapshot())
                    return
                self._send_json({"error": "not found"}, status=404)

            def do_POST(self):
                if self.path not in {
                    "/api/ask",
                    "/api/node/pair",
                    "/api/node/register",
                    "/api/node/screen",
                    "/api/node/camera",
                    "/api/node/location",
                    "/api/workflows/run",
                    "/api/webhooks/trigger",
                    "/api/slack/events",
                    "/api/whatsapp/inbound",
                    "/api/integrations",
                    "/auth/clerk/callback",
                }:
                    self._send_json({"error": "not found"}, status=404)
                    return
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                    raw_body = self.rfile.read(length)
                    content_type = (self.headers.get("Content-Type", "") or "").lower()
                    if "application/json" in content_type:
                        payload = json.loads(raw_body.decode("utf-8") or "{}")
                    else:
                        payload = {k: v[0] if len(v) == 1 else v for k, v in parse_qs(raw_body.decode("utf-8")).items()}
                    if self.path == "/auth/clerk/callback":
                        state = runtime.auth.complete_login(str(payload.get("token", "")), str(payload.get("email", "")))
                        self.send_response(200)
                        self.send_header("Content-Type", "application/json; charset=utf-8")
                        self.send_header("Set-Cookie", f"connect_session={state.local_session_id}; Path=/; HttpOnly; SameSite=Lax")
                        raw = json.dumps({"ok": True, "next_path": str(payload.get("next_path", "/"))}).encode("utf-8")
                        self.send_header("Content-Length", str(len(raw)))
                        self.end_headers()
                        self.wfile.write(raw)
                        return
                    if self._auth_required() and self.path not in {"/api/slack/events", "/api/whatsapp/inbound"} and not self._request_authenticated():
                        self._send_json({"ok": False, "error": "authentication required"}, status=401)
                        return
                    if self.path == "/api/ask":
                        session_id = payload.get("session_id") or runtime.ensure_default_session()
                        result = runtime.run_turn(session_id, str(payload.get("content", "")).strip())
                        self._send_json(result)
                        return
                    if self.path == "/api/node/pair":
                        self._send_json(runtime.nodes.create_pairing(str(payload.get("label", "mobile"))))
                        return
                    if self.path == "/api/node/register":
                        self._send_json(runtime.nodes.register_node(payload["pair_code"], payload["pair_secret"], payload.get("node_name", "mobile"), payload.get("platform", "unknown")))
                        return
                    if self.path == "/api/node/screen":
                        runtime.nodes.update_screen(payload["node_id"], payload.get("screen", ""))
                        self._send_json({"ok": True})
                        return
                    if self.path == "/api/node/camera":
                        runtime.nodes.update_camera(payload["node_id"], payload.get("camera", ""))
                        self._send_json({"ok": True})
                        return
                    if self.path == "/api/node/location":
                        runtime.nodes.update_location(payload["node_id"], payload.get("location", {}))
                        self._send_json({"ok": True})
                        return
                    if self.path == "/api/workflows/run":
                        session_id = payload.get("session_id") or runtime.ensure_default_session()
                        self._send_json(runtime.workflows.run_named(payload["name"], payload.get("payload", {}), session_id=session_id))
                        return
                    if self.path == "/api/webhooks/trigger":
                        if runtime.config.webhook_bearer_token and not runtime.auth.validate_bearer(self.headers.get("Authorization", "")):
                            self._send_json({"ok": False, "error": "invalid webhook bearer token"}, status=401)
                            return
                        session_id = payload.get("session_id") or runtime.ensure_default_session()
                        self._send_json(runtime.workflows.trigger_webhook(payload["name"], payload.get("payload", {}), session_id=session_id))
                        return
                    if self.path == "/api/slack/events":
                        if runtime.slack_bot:
                            signature = self.headers.get("X-Slack-Signature", "")
                            timestamp = self.headers.get("X-Slack-Request-Timestamp", "")
                            if signature and timestamp and not runtime.slack_bot.verify_signature(timestamp, raw_body, signature):
                                self._send_json({"ok": False, "error": "invalid slack signature"}, status=401)
                                return
                        self._send_json(runtime.handle_slack_event(payload))
                        return
                    if self.path == "/api/whatsapp/inbound":
                        self._send_json(runtime.handle_whatsapp_inbound(payload))
                        return
                    if self.path == "/api/integrations":
                        self._send_json(runtime.save_integration(str(payload.get("kind", "")).strip(), payload.get("payload", {}) or {}))
                        return
                    self._send_json({"error": "not found"}, status=404)
                    return
                except Exception as exc:
                    self._send_json({"ok": False, "error": str(exc)}, status=500)

        return Handler

    def serve(self):
        httpd = ThreadingHTTPServer((self.host, self.port), self.make_handler())
        self.runtime.set_service_state("dashboard", True, self.host, self.port)
        print(f"Dashboard listening on http://{self.host}:{self.port}")
        try:
            httpd.serve_forever()
        finally:
            self.runtime.set_service_state("dashboard", False, self.host, self.port)
