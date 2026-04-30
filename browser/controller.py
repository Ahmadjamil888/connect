from __future__ import annotations

import base64
from pathlib import Path


_pw = None
_browser = None
_page = None
_console_errors = []


def _ensure_browser(headless: bool = False):
    global _pw, _browser, _page, _console_errors
    if _browser is not None and _page is not None:
        return
    from playwright.sync_api import sync_playwright

    _pw = sync_playwright().start()
    _browser = _pw.chromium.launch(headless=headless)
    _page = _browser.new_page()
    _console_errors = []
    _page.on("console", lambda msg: _console_errors.append(msg.text) if msg.type == "error" else None)


def run_browser(inputs) -> dict:
    global _pw, _browser, _page, _console_errors
    try:
        action = str(inputs["action"]).strip()
        if action == "close":
            if _browser is not None:
                _browser.close()
            if _pw is not None:
                _pw.stop()
            _pw = None
            _browser = None
            _page = None
            _console_errors = []
            return {"ok": True, "closed": True}

        _ensure_browser(bool(inputs.get("headless", False)))
        workspace = Path(inputs.get("workspace", "."))

        if action == "navigate":
            response = _page.goto(inputs["url"], wait_until="networkidle")
            return {"ok": True, "url": _page.url, "title": _page.title(), "status": response.status if response else None}
        if action == "click":
            _page.click(inputs["selector"])
            _page.wait_for_load_state("networkidle")
            return {"ok": True, "clicked": inputs["selector"], "url": _page.url}
        if action in {"type", "fill"}:
            _page.fill(inputs["selector"], inputs["text"])
            return {"ok": True, "filled": inputs["selector"], "chars": len(inputs["text"])}
        if action == "screenshot":
            data = _page.screenshot(full_page=bool(inputs.get("full_page", True)))
            path = workspace / "browser_screenshot.png"
            path.write_bytes(data)
            return {"ok": True, "path": str(path), "bytes": len(data), "base64": base64.b64encode(data).decode()}
        if action == "get_html":
            return {"ok": True, "html": _page.content()[:20000]}
        if action == "get_text":
            return {"ok": True, "text": _page.inner_text(inputs["selector"])}
        if action == "execute_js":
            return {"ok": True, "result": _page.evaluate(inputs["script"])}
        if action == "console_errors":
            return {"ok": True, "items": _console_errors[-50:]}
        if action == "page_info":
            return {"ok": True, "url": _page.url, "title": _page.title()}
        return {"ok": False, "error": f"Unknown action: {action}"}
    except Exception as e:
        return {"ok": False, "error": f"Browser error: {e}"}
