from __future__ import annotations


def render_node_client_html() -> str:
    return """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>CONNECT Node Client</title>
  <style>
    body {
      margin: 0;
      font-family: "Segoe UI", sans-serif;
      background: linear-gradient(180deg, #0c1220, #101b2d);
      color: #eef5ff;
      padding: 18px;
    }
    .card {
      max-width: 760px;
      margin: 0 auto 16px;
      background: rgba(16, 27, 45, 0.92);
      border: 1px solid rgba(255,255,255,0.08);
      border-radius: 18px;
      padding: 18px;
    }
    h1, h2 { margin: 0 0 10px; }
    p { color: #b2c3d8; }
    input, textarea, button {
      width: 100%;
      padding: 12px;
      border-radius: 12px;
      border: 1px solid rgba(255,255,255,0.12);
      background: #0a1322;
      color: #eef5ff;
      margin-top: 10px;
      box-sizing: border-box;
      font: inherit;
    }
    button {
      cursor: pointer;
      background: linear-gradient(135deg, rgba(79,209,139,0.25), rgba(72,199,255,0.22));
    }
    pre {
      white-space: pre-wrap;
      word-break: break-word;
      background: #08111d;
      border-radius: 12px;
      padding: 12px;
      color: #d9e7f5;
      font-size: 13px;
    }
  </style>
</head>
<body>
  <div class="card">
    <h1>CONNECT Node Client</h1>
    <p>Minimal browser-based prototype for pairing a mobile device and pushing screen/camera/location payloads into the local gateway.</p>
  </div>
  <div class="card">
    <h2>1. Create Pairing</h2>
    <input id="pairLabel" placeholder="Label (e.g. phone)" value="phone" />
    <button onclick="createPair()">Create Pairing Code</button>
    <pre id="pairOutput">No pairing created yet.</pre>
  </div>
  <div class="card">
    <h2>2. Register Node</h2>
    <input id="pairCode" placeholder="Pair Code" />
    <input id="pairSecret" placeholder="Pair Secret" />
    <input id="nodeName" placeholder="Node Name" value="Mobile Browser" />
    <input id="platform" placeholder="Platform" value="mobile-web" />
    <button onclick="registerNode()">Register Node</button>
    <pre id="registerOutput">No node registered yet.</pre>
  </div>
  <div class="card">
    <h2>3. Push Updates</h2>
    <input id="nodeId" placeholder="Node ID" />
    <textarea id="screenPayload" rows="4" placeholder="Screen text or base64 payload"></textarea>
    <button onclick="pushScreen()">Push Screen</button>
    <textarea id="cameraPayload" rows="4" placeholder="Camera text or base64 payload"></textarea>
    <button onclick="pushCamera()">Push Camera</button>
    <textarea id="locationPayload" rows="4" placeholder='{"lat":24.86,"lng":67.01,"accuracy":10}'></textarea>
    <button onclick="pushLocation()">Push Location</button>
    <pre id="updateOutput">No updates pushed yet.</pre>
  </div>
  <script>
    async function post(url, body) {
      const res = await fetch(url, {
        method: "POST",
        headers: {"Content-Type":"application/json"},
        body: JSON.stringify(body)
      });
      return await res.json();
    }
    async function createPair() {
      const out = await post("/api/node/pair", {label: document.getElementById("pairLabel").value.trim() || "phone"});
      document.getElementById("pairOutput").textContent = JSON.stringify(out, null, 2);
      document.getElementById("pairCode").value = out.pair_code || "";
      document.getElementById("pairSecret").value = out.pair_secret || "";
    }
    async function registerNode() {
      const out = await post("/api/node/register", {
        pair_code: document.getElementById("pairCode").value.trim(),
        pair_secret: document.getElementById("pairSecret").value.trim(),
        node_name: document.getElementById("nodeName").value.trim() || "Mobile Browser",
        platform: document.getElementById("platform").value.trim() || "mobile-web"
      });
      document.getElementById("registerOutput").textContent = JSON.stringify(out, null, 2);
      document.getElementById("nodeId").value = out.node_id || "";
    }
    async function pushScreen() {
      const out = await post("/api/node/screen", {
        node_id: document.getElementById("nodeId").value.trim(),
        screen: document.getElementById("screenPayload").value
      });
      document.getElementById("updateOutput").textContent = JSON.stringify(out, null, 2);
    }
    async function pushCamera() {
      const out = await post("/api/node/camera", {
        node_id: document.getElementById("nodeId").value.trim(),
        camera: document.getElementById("cameraPayload").value
      });
      document.getElementById("updateOutput").textContent = JSON.stringify(out, null, 2);
    }
    async function pushLocation() {
      let location = {};
      try { location = JSON.parse(document.getElementById("locationPayload").value || "{}"); } catch (e) {}
      const out = await post("/api/node/location", {
        node_id: document.getElementById("nodeId").value.trim(),
        location
      });
      document.getElementById("updateOutput").textContent = JSON.stringify(out, null, 2);
    }
  </script>
</body>
</html>"""
