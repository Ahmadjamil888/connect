from __future__ import annotations

import base64
import json
import os
import threading
import time
import webbrowser
from dataclasses import dataclass
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from urllib.parse import parse_qs, urlencode, urlparse

import jwt


CLI_SIGNIN_ORIGIN = "https://connect-ai-pi.vercel.app"
CLI_SIGNIN_PATH = "/auth/cli"


def clerk_domain_from_publishable_key(publishable_key: str) -> str:
    parts = (publishable_key or "").split("_")
    if len(parts) < 3:
        raise ValueError("invalid Clerk publishable key")
    encoded = parts[2]
    padding = "=" * (-len(encoded) % 4)
    return base64.b64decode((encoded + padding).encode("utf-8")).decode("utf-8")[:-1]


@dataclass
class AuthState:
    signed_in: bool = False
    local_session_id: str = ""
    user_id: str = ""
    email: str = ""
    token: str = ""
    updated_at: float = 0.0


class ClerkAuthManager:
    def __init__(self, workspace_root: Path, publishable_key: str = "", enabled: bool = False, webhook_bearer_token: str = "", secret_key: str = ""):
        self.workspace_root = workspace_root
        self.auth_dir = workspace_root / "auth"
        self.auth_dir.mkdir(parents=True, exist_ok=True)
        self.publishable_key = (publishable_key or os.getenv("NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY", "")).strip()
        self.secret_key = (secret_key or os.getenv("CLERK_SECRET_KEY", "")).strip()
        self.enabled = bool(enabled)
        self.webhook_bearer_token = webhook_bearer_token.strip()
        self.state_path = self.auth_dir / "clerk_session.json"

    def requires_auth(self, deployment_mode: str) -> bool:
        return self.enabled or str(deployment_mode).lower() == "cloud"

    def is_configured(self) -> bool:
        return bool(self.publishable_key)

    def load_state(self) -> AuthState:
        if not self.state_path.exists():
            return AuthState()
        try:
            payload = json.loads(self.state_path.read_text(encoding="utf-8"))
            return AuthState(
                signed_in=bool(payload.get("signed_in", False)),
                local_session_id=str(payload.get("local_session_id", "")),
                user_id=str(payload.get("user_id", "")),
                email=str(payload.get("email", "")),
                token=str(payload.get("token", "")),
                updated_at=float(payload.get("updated_at", 0.0)),
            )
        except Exception:
            return AuthState()

    def save_state(self, state: AuthState):
        payload = {
            "signed_in": state.signed_in,
            "local_session_id": state.local_session_id,
            "user_id": state.user_id,
            "email": state.email,
            "token": state.token,
            "updated_at": state.updated_at or time.time(),
        }
        self.state_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def clear_state(self):
        self.save_state(AuthState())

    def is_signed_in(self) -> bool:
        state = self.load_state()
        return bool(state.signed_in and state.local_session_id)

    def current_user(self) -> Dict[str, Any]:
        state = self.load_state()
        return {
            "signed_in": state.signed_in,
            "user_id": state.user_id,
            "email": state.email,
            "updated_at": state.updated_at,
        }

    def verify_clerk_token(self, token: str) -> Dict[str, Any]:
        if not token:
            raise ValueError("missing Clerk session token")
        domain = clerk_domain_from_publishable_key(self.publishable_key)
        jwks_url = f"https://{domain}/.well-known/jwks.json"
        key = jwt.PyJWKClient(jwks_url).get_signing_key_from_jwt(token)
        return jwt.decode(token, key.key, algorithms=["RS256"], options={"verify_aud": False})

    def complete_login(self, token: str, email: str = "") -> AuthState:
        claims = self.verify_clerk_token(token)
        state = AuthState(
            signed_in=True,
            local_session_id=claims.get("sid") or claims.get("sub") or f"local-{int(time.time())}",
            user_id=str(claims.get("sub", "")),
            email=email or str(claims.get("email", "")),
            token=token,
            updated_at=time.time(),
        )
        self.save_state(state)
        return state

    def validate_cookie(self, cookie_header: str) -> bool:
        if not cookie_header:
            return False
        cookie = SimpleCookie()
        try:
            cookie.load(cookie_header)
        except Exception:
            return False
        session = cookie.get("connect_session")
        if not session:
            return False
        state = self.load_state()
        return bool(state.signed_in and state.local_session_id and session.value == state.local_session_id)

    def validate_bearer(self, auth_header: str) -> bool:
        if not auth_header:
            return False
        value = str(auth_header).strip()
        if value.lower().startswith("bearer "):
            value = value.split(" ", 1)[1].strip()
        state = self.load_state()
        if state.token and value == state.token:
            return True
        if self.webhook_bearer_token and value == self.webhook_bearer_token:
            return True
        return False

    def request_authenticated(self, headers: Dict[str, Any]) -> bool:
        return self.validate_cookie(headers.get("Cookie", "")) or self.validate_bearer(headers.get("Authorization", ""))

    def render_signin_html(self, post_path: str, next_path: str = "/") -> str:
        if not self.publishable_key:
            return "<html><body><h1>Clerk is not configured</h1></body></html>"
        domain = clerk_domain_from_publishable_key(self.publishable_key)
        return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>CONNECT Sign In</title>
  <style>
    body {{
      margin: 0; min-height: 100vh; display: grid; place-items: center;
      font-family: "Segoe UI", "IBM Plex Sans", sans-serif;
      background: radial-gradient(circle at top left, rgba(72,199,255,0.16), transparent 30%), linear-gradient(180deg, #091018, #0d1117);
      color: #eef6ff;
    }}
    .card {{ width: min(540px, 92vw); padding: 24px; border-radius: 18px; background: rgba(17,24,39,0.94); border: 1px solid #263244; }}
  </style>
</head>
<body>
  <div class="card">
    <h1>Sign in to CONNECT</h1>
    <div id="app"></div>
  </div>
  <script type="module">
    import {{ Clerk }} from "https://cdn.jsdelivr.net/npm/@clerk/clerk-js@latest/dist/clerk.browser.js";
    const publishableKey = {json.dumps(self.publishable_key)};
    const clerkDomain = atob(publishableKey.split("_")[2]).slice(0, -1);
    await new Promise((resolve, reject) => {{
      const script = document.createElement("script");
      script.src = `https://${{clerkDomain}}/npm/@clerk/ui@1/dist/ui.browser.js`;
      script.async = true;
      script.crossOrigin = "anonymous";
      script.onload = resolve;
      script.onerror = () => reject(new Error("Failed to load @clerk/ui bundle"));
      document.head.appendChild(script);
    }});
    const clerk = new Clerk(publishableKey);
    await clerk.load({{ ui: {{ ClerkUI: window.__internal_ClerkUICtor }} }});
    async function finish() {{
      const token = await clerk.session.getToken();
      const payload = {{
        token,
        email: clerk.user?.primaryEmailAddress?.emailAddress || "",
        next_path: {json.dumps(next_path)},
      }};
      const res = await fetch({json.dumps(post_path)}, {{
        method: "POST",
        headers: {{ "Content-Type": "application/json" }},
        body: JSON.stringify(payload),
      }});
      const data = await res.json();
      if (!res.ok || !data.ok) {{
        document.getElementById("app").innerHTML = `<pre>${{JSON.stringify(data, null, 2)}}</pre>`;
        return;
      }}
      window.location.href = data.next_path || "/";
    }}
    if (clerk.isSignedIn) {{
      await finish();
    }} else {{
      document.getElementById("app").innerHTML = '<div id="sign-in"></div>';
      clerk.mountSignIn(document.getElementById("sign-in"));
      clerk.addListener(async (evt) => {{
        if (evt.user) {{
          await finish();
        }}
      }});
    }}
  </script>
</body>
</html>"""

    def build_cli_signin_url(self, callback_url: str) -> str:
        query = urlencode(
            {
                "callback": callback_url,
                "origin": "cli",
            }
        )
        return f"{CLI_SIGNIN_ORIGIN}{CLI_SIGNIN_PATH}?{query}"

    def start_cli_login(self, timeout_seconds: int = 300) -> Tuple[bool, str]:
        if not self.is_configured():
            return False, "Clerk publishable key is not configured."
        completed = threading.Event()
        outcome: Dict[str, Any] = {"ok": False, "message": "login did not complete"}
        manager = self

        class Handler(BaseHTTPRequestHandler):
            def _cors_headers(self):
                origin = self.headers.get("Origin", "")
                if origin == CLI_SIGNIN_ORIGIN:
                    self.send_header("Access-Control-Allow-Origin", origin)
                    self.send_header("Vary", "Origin")
                self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
                self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")

            def _send_html(self, html: str, status: int = 200):
                raw = html.encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            def _send_json(self, payload: Dict[str, Any], status: int = 200, set_cookie: str = ""):
                raw = json.dumps(payload).encode("utf-8")
                self.send_response(status)
                self._cors_headers()
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(raw)))
                if set_cookie:
                    self.send_header("Set-Cookie", set_cookie)
                self.end_headers()
                self.wfile.write(raw)

            def log_message(self, format: str, *args):
                return

            def do_OPTIONS(self):
                self.send_response(204)
                self._cors_headers()
                self.end_headers()

            def do_GET(self):
                if self.path == "/" or self.path.startswith("/?"):
                    self._send_html(manager.render_signin_html("/callback", "/done"))
                    return
                if self.path.startswith("/done"):
                    self._send_html("<html><body><h1>Signed in successfully</h1><p>You can return to CONNECT.</p></body></html>")
                    return
                self._send_html("<html><body>Not found</body></html>", status=404)

            def do_POST(self):
                if self.path != "/callback":
                    self._send_json({"ok": False, "error": "not found"}, status=404)
                    return
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                    payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
                    state = manager.complete_login(str(payload.get("token", "")), str(payload.get("email", "")))
                    outcome["ok"] = True
                    outcome["message"] = f"Signed in successfully as {state.email or state.user_id}"
                    completed.set()
                    self._send_json(
                        {"ok": True, "next_path": "/done"},
                        set_cookie=f"connect_session={state.local_session_id}; Path=/; HttpOnly; SameSite=Lax",
                    )
                except Exception as exc:
                    outcome["ok"] = False
                    outcome["message"] = str(exc)
                    completed.set()
                    self._send_json({"ok": False, "error": str(exc)}, status=500)

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        port = int(server.server_address[1])
        thread = threading.Thread(target=server.serve_forever, name="clerk-cli-login", daemon=True)
        thread.start()
        try:
            webbrowser.open(manager.build_cli_signin_url(f"http://127.0.0.1:{port}/callback"))
            completed.wait(timeout_seconds)
        finally:
            server.shutdown()
            server.server_close()
        return bool(outcome.get("ok")), str(outcome.get("message", "login failed"))
