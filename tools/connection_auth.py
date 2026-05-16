from __future__ import annotations

import time
from typing import Any

from core.browser_driver import browser
from core.events import event_bus


AUTH_PROVIDERS: dict[str, dict[str, Any]] = {
    "gmail": {
        "auth_url": "https://accounts.google.com/signin/v2/identifier",
        "console_url": "https://mail.google.com",
        "label": "Gmail",
        "post_login_hint": "After signing in, generate or paste an app password plus IMAP/SMTP details into the connection fields.",
    },
    "supabase": {
        "auth_url": "https://supabase.com/dashboard/sign-in",
        "console_url": "https://supabase.com/dashboard/projects",
        "label": "Supabase",
        "post_login_hint": "After signing in, copy the project URL and service role key into the connection fields.",
    },
    "firebase": {
        "auth_url": "https://console.firebase.google.com/",
        "console_url": "https://console.firebase.google.com/",
        "label": "Firebase",
        "post_login_hint": "After signing in, select the project and add the project ID and service account JSON path.",
    },
    "vercel": {
        "auth_url": "https://vercel.com/login",
        "console_url": "https://vercel.com/dashboard",
        "label": "Vercel",
        "post_login_hint": "After signing in, create or copy a Vercel token for CLI/API deploys.",
    },
    "netlify": {
        "auth_url": "https://app.netlify.com/login",
        "console_url": "https://app.netlify.com/",
        "label": "Netlify",
        "post_login_hint": "After signing in, create or copy a Netlify personal access token.",
    },
    "github": {
        "auth_url": "https://github.com/login",
        "console_url": "https://github.com/settings/tokens",
        "label": "GitHub",
        "post_login_hint": "After signing in, create a token if push or repo automation is required.",
    },
}


def auth_metadata(provider: str) -> dict[str, Any]:
    return dict(AUTH_PROVIDERS.get(str(provider or "").strip().lower(), {}))


def open_connection_signin(provider: str, *, open_console: bool = False) -> dict[str, Any]:
    key = str(provider or "").strip().lower()
    entry = AUTH_PROVIDERS.get(key)
    if not entry:
        return {"ok": False, "error": f"No browser auth helper configured for {provider}."}
    url = entry["console_url"] if open_console else entry["auth_url"]
    event_bus.publish("tool_progress", name="connection_auth", message=f"Opening {entry['label']} browser flow", provider=key, url=url)
    result = browser.open_url(url)
    if isinstance(result, dict) and not result.get("ok"):
        return result
    time.sleep(1)
    for label in ["sign in", "log in", "continue", "continue with google", "continue with github"]:
        clicked = browser.find_and_click(label)
        if isinstance(clicked, dict) and clicked.get("ok"):
            break
    return {
        "ok": True,
        "provider": key,
        "url": url,
        "label": entry["label"],
        "post_login_hint": entry["post_login_hint"],
    }
