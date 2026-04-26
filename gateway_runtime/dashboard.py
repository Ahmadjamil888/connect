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
      --bg: #0d1117;
      --panel: #111827;
      --muted: #9fb0c3;
      --text: #eef6ff;
      --line: #263244;
      --accent: #48c7ff;
      --accent-2: #ffb347;
      --ok: #4fd18b;
      --bad: #ff6b6b;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: "Segoe UI", "IBM Plex Sans", sans-serif;
      color: var(--text);
      background:
        radial-gradient(circle at top left, rgba(72,199,255,0.16), transparent 30%),
        radial-gradient(circle at top right, rgba(255,179,71,0.12), transparent 28%),
        linear-gradient(180deg, #091018, var(--bg));
    }
    .shell {
      max-width: 1360px;
      margin: 0 auto;
      padding: 28px;
    }
    .hero {
      display: grid;
      gap: 18px;
      grid-template-columns: 1.2fr 0.8fr;
      align-items: stretch;
      margin-bottom: 22px;
    }
    .card {
      background: rgba(17,24,39,0.9);
      border: 1px solid var(--line);
      border-radius: 20px;
      padding: 20px;
      backdrop-filter: blur(10px);
      box-shadow: 0 18px 45px rgba(0,0,0,0.22);
    }
    .title {
      font-size: 38px;
      font-weight: 800;
      letter-spacing: 0.02em;
      margin: 0 0 6px;
    }
    .subtitle {
      color: var(--muted);
      margin: 0;
      max-width: 70ch;
      line-height: 1.5;
    }
    .stats {
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 14px;
      margin-top: 18px;
    }
    .stat {
      padding: 14px;
      border-radius: 16px;
      background: rgba(255,255,255,0.03);
      border: 1px solid rgba(255,255,255,0.05);
    }
    .stat .k { color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: 0.08em; }
    .stat .v { font-size: 26px; font-weight: 800; margin-top: 6px; }
    .grid {
      display: grid;
      grid-template-columns: 0.9fr 1.1fr;
      gap: 18px;
    }
    .stack { display: grid; gap: 18px; }
    .section-title {
      display: flex; justify-content: space-between; align-items: center;
      margin-bottom: 14px; font-size: 14px; text-transform: uppercase; letter-spacing: 0.08em; color: var(--muted);
    }
    .pill {
      border-radius: 999px;
      padding: 6px 10px;
      border: 1px solid var(--line);
      background: rgba(72,199,255,0.08);
      color: var(--text);
      font-size: 12px;
    }
    .list { display: grid; gap: 10px; }
    .row {
      padding: 12px 14px;
      border-radius: 14px;
      border: 1px solid rgba(255,255,255,0.06);
      background: rgba(255,255,255,0.02);
    }
    .row strong { display: block; margin-bottom: 4px; }
    .meta { color: var(--muted); font-size: 13px; }
    .toolbar {
      display: flex; gap: 10px; flex-wrap: wrap; margin-top: 16px;
    }
    input, button, select {
      border-radius: 12px;
      border: 1px solid var(--line);
      background: #0f1724;
      color: var(--text);
      padding: 10px 12px;
      font: inherit;
    }
    button {
      cursor: pointer;
      background: linear-gradient(135deg, rgba(72,199,255,0.22), rgba(255,179,71,0.18));
    }
    pre {
      margin: 0;
      white-space: pre-wrap;
      word-break: break-word;
      color: #d8e7f5;
      font-family: Consolas, "SFMono-Regular", monospace;
      font-size: 13px;
      line-height: 1.5;
    }
    .ok { color: var(--ok); }
    .bad { color: var(--bad); }
    @media (max-width: 980px) {
      .hero, .grid { grid-template-columns: 1fr; }
      .stats { grid-template-columns: repeat(2, 1fr); }
    }
  </style>
</head>
<body>
  <div class="shell">
    <section class="hero">
      <div class="card">
        <h1 class="title">CONNECT Operator</h1>
        <p class="subtitle">Local-first gateway, session router, coding runtime, and memory-backed operator loop. This dashboard refreshes live state directly from the local control plane.</p>
        <div class="stats">
        <div class="stat"><div class="k">Provider</div><div class="v" id="providerValue">-</div></div>
          <div class="stat"><div class="k">Sessions</div><div class="v" id="sessionValue">0</div></div>
          <div class="stat"><div class="k">Tools</div><div class="v" id="toolValue">0</div></div>
          <div class="stat"><div class="k">Live Services</div><div class="v" id="serviceValue">0</div></div>
        </div>
      </div>
      <div class="card">
        <div class="section-title"><span>Quick Ask</span><span class="pill">dynamic runtime</span></div>
        <div class="toolbar">
          <input id="askInput" style="flex:1; min-width:220px" placeholder="Ask the operator to do something..." />
          <button id="askButton">Run</button>
        </div>
        <div style="margin-top:16px">
          <pre id="askOutput">No request yet.</pre>
        </div>
      </div>
    </section>
    <section class="grid">
      <div class="stack">
        <div class="card">
          <div class="section-title"><span>Sessions</span><span class="pill" id="sessionBadge">idle</span></div>
          <div id="sessionList" class="list"></div>
        </div>
        <div class="card">
          <div class="section-title"><span>Recent Memory</span><span class="pill">context</span></div>
          <div id="memoryList" class="list"></div>
        </div>
        <div class="card">
          <div class="section-title"><span>Chat Session</span><span class="pill" id="chatBadge">history</span></div>
          <div id="chatList" class="list"></div>
        </div>
        <div class="card">
          <div class="section-title"><span>Paired Nodes</span><span class="pill" id="nodeBadge">nodes</span></div>
          <div id="nodeList" class="list"></div>
        </div>
      </div>
      <div class="stack">
        <div class="card">
          <div class="section-title"><span>Gateway Status</span><span class="pill" id="providerBadge">provider</span></div>
          <pre id="statusOutput">Loading...</pre>
        </div>
        <div class="card">
          <div class="section-title"><span>Typed Tools</span><span class="pill" id="toolBadge">catalog</span></div>
          <div class="toolbar">
            <select id="groupFilter">
              <option value="">All groups</option>
            </select>
          </div>
          <div id="toolList" class="list" style="margin-top:14px"></div>
        </div>
        <div class="card">
          <div class="section-title"><span>Canvas</span><span class="pill" id="canvasBadge">canvas</span></div>
          <div id="canvasList" class="list"></div>
        </div>
      </div>
    </section>
  </div>
  <script>
    let sessions = [];
    let tools = [];
    async function loadJson(url, options) {
      const res = await fetch(url, options);
      return await res.json();
    }
    function rowHtml(title, meta, extra) {
      return `<div class="row"><strong>${title}</strong><div class="meta">${meta}</div>${extra ? `<div class="meta" style="margin-top:6px">${extra}</div>` : ""}</div>`;
    }
    function renderSessions() {
      const target = document.getElementById("sessionList");
      document.getElementById("sessionValue").textContent = String(sessions.length);
      document.getElementById("sessionBadge").textContent = sessions.length ? "active" : "empty";
      target.innerHTML = sessions.length ? sessions.map(s => rowHtml(`${s.name} · ${s.id}`, `status=${s.status} profile=${s.profile}`, `updated ${s.updated_at}`)).join("") : rowHtml("No sessions", "Create one by asking the operator a question.");
    }
    function renderMemory(items) {
      const target = document.getElementById("memoryList");
      target.innerHTML = items.length ? items.slice().reverse().map(i => rowHtml(i.kind || "memory", i.content || "", i.ts || "")).join("") : rowHtml("No memory yet", "Recent context will appear here.");
    }
    function renderChat(items) {
      const target = document.getElementById("chatList");
      document.getElementById("chatBadge").textContent = `${items.length} msgs`;
      target.innerHTML = items.length ? items.slice().reverse().map(i => rowHtml(i.role || "message", i.content || "", i.ts || "")).join("") : rowHtml("No chat yet", "Use Quick Ask to create conversation history.");
    }
    function renderNodes(items) {
      const target = document.getElementById("nodeList");
      document.getElementById("nodeBadge").textContent = `${items.length} paired`;
      target.innerHTML = items.length ? items.map(n => rowHtml(`${n.name} · ${n.node_id}`, `${n.platform} · last seen ${n.last_seen}`, Object.keys(n.location || {}).length ? JSON.stringify(n.location) : "")).join("") : rowHtml("No paired nodes", "Use node pairing to register a mobile client.");
    }
    function renderCanvas(snapshot) {
      const cards = (snapshot.cards || []);
      document.getElementById("canvasBadge").textContent = `${cards.length} cards`;
      document.getElementById("canvasList").innerHTML = cards.length ? cards.slice().reverse().map(c => rowHtml(c.title || c.id, c.kind || "note", c.content || "")).join("") : rowHtml("Canvas empty", "Use canvas_present to push live cards.");
    }
    function renderStatus(status) {
      document.getElementById("providerValue").textContent = status.provider || "none";
      document.getElementById("providerBadge").textContent = status.provider || "none";
      document.getElementById("toolValue").textContent = String(status.tool_count || 0);
      document.getElementById("serviceValue").textContent = String(Object.values(status.services || {}).filter(s => s && s.running).length);
      document.getElementById("toolBadge").textContent = `${status.implemented_tool_count || 0} live / ${status.stubbed_tool_count || 0} stub`;
      document.getElementById("statusOutput").textContent = JSON.stringify(status, null, 2);
    }
    function renderTools() {
      const filter = document.getElementById("groupFilter").value;
      const visible = filter ? tools.filter(t => t.group === filter) : tools;
      document.getElementById("toolList").innerHTML = visible.map(t => rowHtml(`${t.name}`, `${t.group} · ${t.implemented ? "implemented" : "stub"}`, t.description || "")).join("");
    }
    function fillGroups() {
      const select = document.getElementById("groupFilter");
      const groups = [...new Set(tools.map(t => t.group))].sort();
      select.innerHTML = `<option value="">All groups</option>` + groups.map(g => `<option value="${g}">${g}</option>`).join("");
      select.onchange = renderTools;
    }
    async function refresh() {
      const [status, toolRows, sessionRows, memoryRows, nodeRows, canvasSnapshot] = await Promise.all([
        loadJson("/api/status"),
        loadJson("/api/tools"),
        loadJson("/api/sessions"),
        loadJson("/api/memory"),
        loadJson("/api/nodes"),
        loadJson("/api/canvas")
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
