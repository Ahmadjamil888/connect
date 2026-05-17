import base64
from typing import Any


_browser = None
_page = None
_pw = None


def _get_page() -> Any:
    global _browser, _page, _pw
    if _page is None or _browser is None:
        try:
            from playwright.sync_api import sync_playwright

            _pw = sync_playwright().start()
            _browser = _pw.chromium.launch(headless=False)
            _page = _browser.new_page()
        except ModuleNotFoundError as exc:
            raise RuntimeError("browser unavailable: missing dependency 'playwright'") from exc
        except Exception as exc:
            raise RuntimeError(f"browser unavailable: {exc}") from exc
    return _page


def navigate(url: str) -> dict[str, Any]:
    page = _get_page()
    page.goto(url, timeout=30000)
    page.wait_for_load_state("domcontentloaded")
    return {
        "ok": True,
        "requested_url": url,
        "current_url": page.url,
        "title": page.title(),
    }


def click_element(selector: str = None, text: str = None, x: int = None, y: int = None) -> dict[str, Any]:
    page = _get_page()
    if text:
        page.get_by_text(text).first.click()
        return {"ok": True, "clicked_text": text, "current_url": page.url, "title": page.title()}
    if selector:
        page.click(selector)
        return {"ok": True, "clicked_selector": selector, "current_url": page.url, "title": page.title()}
    if x is not None and y is not None:
        page.mouse.click(x, y)
        return {"ok": True, "clicked_coordinates": {"x": x, "y": y}, "current_url": page.url, "title": page.title()}
    return {"ok": False, "error": "provide selector, text, or coordinates"}


def type_into(selector: str = None, text_label: str = None, value: str = "") -> dict[str, Any]:
    page = _get_page()
    if text_label:
        page.get_by_label(text_label).fill(value)
        return {"ok": True, "text_label": text_label, "value_length": len(value), "current_url": page.url, "title": page.title()}
    if selector:
        page.fill(selector, value)
        return {"ok": True, "selector": selector, "value_length": len(value), "current_url": page.url, "title": page.title()}
    return {"ok": False, "error": "provide selector or text_label"}


def get_page_text() -> dict[str, Any]:
    page = _get_page()
    return {
        "ok": True,
        "current_url": page.url,
        "title": page.title(),
        "content": page.inner_text("body")[:5000],
    }


def get_page_screenshot_b64() -> dict[str, Any]:
    page = _get_page()
    return {
        "ok": True,
        "current_url": page.url,
        "title": page.title(),
        "image_b64": base64.b64encode(page.screenshot()).decode(),
    }


def wait_for_element(selector: str, timeout: int = 10000) -> dict[str, Any]:
    page = _get_page()
    page.wait_for_selector(selector, timeout=timeout)
    return {"ok": True, "selector": selector, "current_url": page.url, "title": page.title()}


def scroll(direction: str = "down", amount: int = 500) -> dict[str, Any]:
    page = _get_page()
    delta = amount if direction == "down" else -amount
    page.mouse.wheel(0, delta)
    return {"ok": True, "direction": direction, "amount": amount, "current_url": page.url, "title": page.title()}


def close_browser() -> dict[str, Any]:
    global _browser, _page, _pw
    if _browser:
        _browser.close()
    if _pw:
        _pw.stop()
    _browser = None
    _page = None
    _pw = None
    return {"ok": True, "closed": True}

