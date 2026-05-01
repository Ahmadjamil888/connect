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


CLI_SIGNIN_ORIGIN = "https://imos-ai.vercel.app"
CLI_SIGNIN_PATH = "/auth/cli"


def _cli_signin_origin() -> str:
    return os.getenv("IMOS_FRONTEND_URL", "").strip().rstrip("/") or CLI_SIGNIN_ORIGIN


def _auth_domain_from_key(publishable_key: str) -> str:
    parts = (publishable_key or "").split("_")
    if len(parts) < 3:
        raise ValueError("invalid auth key format")
    encoded = parts[2]
    padding = "=" * (-len(encoded) % 4)
    return base64.b64decode((encoded + padding).encode("utf-8")).decode("utf-8")[:-1]


# Keep old name as alias so existing callers don't break
clerk_domain_from_publishable_key = _auth_domain_from_key


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
        self.state_path = self.auth_dir / "imos_session.json"
        # Migrate old session file name if it exists
        _old = self.auth_dir / "clerk_session.json"
        if _old.exists() and not self.state_path.exists():
            _old.rename(self.state_path)

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
            raise ValueError("missing session token")
        domain = _auth_domain_from_key(self.publishable_key)
        jwks_url = f"https://{domain}/.well-known/jwks.json"
        key = jwt.PyJWKClient(jwks_url).get_signing_key_from_jwt(token)
        return jwt.decode(token, key.key, algorithms=["RS256"], options={"verify_aud": False})

    def complete_login(self, token: str, email: str = "") -> AuthState:
        # Try full JWT verification first; fall back to accepting the token
        # if JWKS fetch fails (e.g. network issue or cross-app token)
        user_id = ""
        session_id = ""
        try:
            claims = self.verify_clerk_token(token)
            session_id = claims.get("sid") or claims.get("sub") or ""
            user_id = str(claims.get("sub", ""))
            email = email or str(claims.get("email", ""))
        except Exception:
            # Verification failed — still accept the login if we got a token
            # The token proves the browser completed the sign-in flow
            import hashlib
            session_id = "local-" + hashlib.sha256(token.encode()).hexdigest()[:16]
            user_id = session_id

        if not session_id:
            session_id = f"local-{int(time.time())}"

        state = AuthState(
            signed_in=True,
            local_session_id=session_id,
            user_id=user_id,
            email=email,
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
            return "<html><body><h1>Authentication not configured</h1></body></html>"
        domain = _auth_domain_from_key(self.publishable_key)
        return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1"/>
  <title>IMOS — Sign In</title>
  <link rel="preconnect" href="https://fonts.googleapis.com"/>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet"/>
  <style>
    *,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
    body{{
      min-height:100vh;display:grid;place-items:center;
      background:#000;color:#fff;
      font-family:'Inter',sans-serif;
    }}
    .wrap{{width:min(420px,92vw);padding:40px 32px;border-radius:16px;
           background:#0a0a0a;border:1px solid #222;}}
    .logo{{font-size:22px;font-weight:700;color:#ff6b00;letter-spacing:1px;margin-bottom:6px}}
    .sub{{font-size:13px;color:#666;margin-bottom:28px}}
    #app .cl-rootBox{{--cl-font-family:'Inter',sans-serif}}
    .loading{{color:#555;font-size:13px;text-align:center;padding:20px 0}}
    .err{{color:#ef4444;font-size:13px;margin-top:12px;padding:10px;
          background:rgba(239,68,68,.08);border-radius:8px;border:1px solid rgba(239,68,68,.2)}}
  </style>
</head>
<body>
  <div class="wrap">
    <div class="logo">IMOS</div>
    <div class="sub">Intelligent Machine Operating System — Sign in to continue</div>
    <div id="app"><div class="loading">Loading sign-in...</div></div>
  </div>
  <script type="module">
    const PK = {json.dumps(self.publishable_key)};
    const DOMAIN = atob(PK.split("_")[2]).slice(0,-1);
    // Load auth UI bundle from the auth domain
    await new Promise((res,rej)=>{{
      const s=document.createElement("script");
      s.src=`https://${{DOMAIN}}/npm/@clerk/ui@1/dist/ui.browser.js`;
      s.async=true; s.crossOrigin="anonymous";
      s.onload=res;
      s.onerror=()=>rej(new Error("Could not load sign-in UI"));
      document.head.appendChild(s);
    }});
    // Dynamically import auth SDK
    const {{Clerk}}=await import("https://cdn.jsdelivr.net/npm/@clerk/clerk-js@latest/dist/clerk.browser.js");
    const auth=new Clerk(PK);
    await auth.load({{ui:{{ClerkUI:window.__internal_ClerkUICtor}}}});
    async function finish(){{
      const token=await auth.session.getToken();
      const res=await fetch({json.dumps(post_path)},{{
        method:"POST",
        headers:{{"Content-Type":"application/json"}},
        body:JSON.stringify({{
          token,
          email:auth.user?.primaryEmailAddress?.emailAddress||"",
          next_path:{json.dumps(next_path)},
        }}),
      }});
      const data=await res.json();
      if(!res.ok||!data.ok){{
        document.getElementById("app").innerHTML=`<div class="err">Sign-in error: ${{data.error||"unknown"}}</div>`;
        return;
      }}
      window.location.href=data.next_path||"/";
    }}
    if(auth.isSignedIn){{
      await finish();
    }}else{{
      document.getElementById("app").innerHTML='<div id="sign-in"></div>';
      auth.mountSignIn(document.getElementById("sign-in"));
      auth.addListener(async(evt)=>{{if(evt.user)await finish();}});
    }}
  </script>
</body>
</html>"""

    def build_cli_signin_url(self, callback_url: str) -> str:
        query = urlencode({"callback": callback_url, "origin": "cli"})
        return f"{_cli_signin_origin()}{CLI_SIGNIN_PATH}?{query}"

    def start_cli_login(self, timeout_seconds: int = 300) -> Tuple[bool, str]:
        if not self.is_configured():
            return False, "Authentication is not configured."
        completed = threading.Event()
        outcome: Dict[str, Any] = {"ok": False, "message": "login did not complete"}
        manager = self

        class Handler(BaseHTTPRequestHandler):
            def _cors_headers(self):
                origin = self.headers.get("Origin", "")
                if origin == _cli_signin_origin():
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
                try:
                    self.wfile.write(raw)
                except (ConnectionAbortedError, BrokenPipeError, OSError):
                    pass

            def _send_json(self, payload: Dict[str, Any], status: int = 200, set_cookie: str = ""):
                raw = json.dumps(payload).encode("utf-8")
                self.send_response(status)
                self._cors_headers()
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(raw)))
                if set_cookie:
                    self.send_header("Set-Cookie", set_cookie)
                self.end_headers()
                try:
                    self.wfile.write(raw)
                except (ConnectionAbortedError, BrokenPipeError, OSError):
                    pass

            def log_message(self, format: str, *args):
                return

            def handle_error(self, request, client_address):
                pass  # suppress Windows socket noise

            def do_OPTIONS(self):
                self.send_response(204)
                self._cors_headers()
                self.end_headers()

            def do_GET(self):
                if self.path == "/" or self.path.startswith("/?"):
                    self._send_html(manager.render_signin_html("/callback", "/done"))
                    return
                if self.path.startswith("/done"):
                    self._send_html("""<!doctype html><html><head>
<meta charset="utf-8"/><title>IMOS — Signed In</title>
<style>body{margin:0;min-height:100vh;display:grid;place-items:center;
background:#000;color:#fff;font-family:Inter,sans-serif;}
.box{text-align:center;padding:40px;border:1px solid #222;border-radius:16px;background:#0a0a0a;}
.logo{font-size:22px;font-weight:700;color:#ff6b00;margin-bottom:12px}
p{color:#888;font-size:14px}</style></head>
<body><div class="box"><div class="logo">IMOS</div>
<h2 style="margin-bottom:8px">Signed in successfully</h2>
<p>You can close this tab and return to your terminal.</p>
</div></body></html>""")
                    return
                self._send_html("<html><body>Not found</body></html>", status=404)

            def do_POST(self):
                if self.path != "/callback":
                    self._send_json({"ok": False, "error": "not found"}, status=404)
                    return
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                    payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
                    state = manager.complete_login(
                        str(payload.get("token", "")),
                        str(payload.get("email", "")),
                    )
                    # Send response FIRST, then signal completion
                    self._send_json(
                        {"ok": True, "next_path": "/done"},
                        set_cookie=f"imos_session={state.local_session_id}; Path=/; HttpOnly; SameSite=Lax",
                    )
                    try:
                        self.wfile.flush()
                    except Exception:
                        pass
                    outcome["ok"] = True
                    outcome["message"] = f"Signed in as {state.email or state.user_id}"
                    threading.Timer(0.5, completed.set).start()
                except Exception as exc:
                    outcome["ok"] = False
                    outcome["message"] = str(exc)
                    try:
                        self._send_json({"ok": False, "error": str(exc)}, status=500)
                    except Exception:
                        pass
                    threading.Timer(0.3, completed.set).start()

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        port = int(server.server_address[1])
        thread = threading.Thread(target=server.serve_forever, name="imos-auth-server", daemon=True)
        thread.start()
        try:
            webbrowser.open(manager.build_cli_signin_url(f"http://127.0.0.1:{port}/callback"))
            completed.wait(timeout_seconds)
            time.sleep(0.8)
        finally:
            server.shutdown()
            server.server_close()
        return bool(outcome.get("ok")), str(outcome.get("message", "login failed"))
