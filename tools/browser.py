import base64

from playwright.sync_api import Page, sync_playwright


_browser = None
_page = None
_pw = None


def _get_page() -> Page:
    global _browser, _page, _pw
    if _page is None or _browser is None:
        try:
            _pw = sync_playwright().start()
            _browser = _pw.chromium.launch(headless=False)
            _page = _browser.new_page()
        except Exception as exc:
            raise RuntimeError(f"browser unavailable: {exc}") from exc
    return _page


def navigate(url: str) -> str:
    page = _get_page()
    page.goto(url, timeout=30000)
    page.wait_for_load_state("domcontentloaded")
    return f"Navigated to {url} title: {page.title()}"


def click_element(selector: str = None, text: str = None, x: int = None, y: int = None) -> str:
    page = _get_page()
    if text:
        page.get_by_text(text).first.click()
        return f"Clicked element with text: {text}"
    if selector:
        page.click(selector)
        return f"Clicked selector: {selector}"
    if x is not None and y is not None:
        page.mouse.click(x, y)
        return f"Clicked coordinates: ({x}, {y})"
    return "Error: provide selector, text, or coordinates"


def type_into(selector: str = None, text_label: str = None, value: str = "") -> str:
    page = _get_page()
    if text_label:
        page.get_by_label(text_label).fill(value)
        return "Typed into field"
    if selector:
        page.fill(selector, value)
        return "Typed into field"
    return "Error: provide selector or text_label"


def get_page_text() -> str:
    page = _get_page()
    return page.inner_text("body")[:5000]


def get_page_screenshot_b64() -> str:
    page = _get_page()
    return base64.b64encode(page.screenshot()).decode()


def wait_for_element(selector: str, timeout: int = 10000) -> str:
    page = _get_page()
    page.wait_for_selector(selector, timeout=timeout)
    return f"Element found: {selector}"


def scroll(direction: str = "down", amount: int = 500) -> str:
    page = _get_page()
    delta = amount if direction == "down" else -amount
    page.mouse.wheel(0, delta)
    return f"Scrolled {direction}"


def close_browser() -> str:
    global _browser, _page, _pw
    if _browser:
        _browser.close()
    if _pw:
        _pw.stop()
    _browser = None
    _page = None
    _pw = None
    return "Browser closed"

