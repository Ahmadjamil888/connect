from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

class BrowserSession:
    def __init__(self) -> None:
        self._playwright = None
        self._browser = None
        self._context = None
        self._page = None

    async def ensure_page(self):
        if self._page is not None:
            return self._page
        if self._playwright is None:
            from playwright.async_api import async_playwright

            self._playwright = await async_playwright().start()
        if self._browser is None:
            self._browser = await self._playwright.chromium.launch(headless=False)
        if self._context is None:
            self._context = await self._browser.new_context()
        self._page = await self._context.new_page()
        return self._page

    async def new_tab(self, url: str | None = None):
        if self._playwright is None:
            from playwright.async_api import async_playwright

            self._playwright = await async_playwright().start()
        if self._browser is None:
            self._browser = await self._playwright.chromium.launch(headless=False)
        if self._context is None:
            self._context = await self._browser.new_context()
        self._page = await self._context.new_page()
        if url:
            await self._page.goto(url, wait_until="networkidle")
        return self._page


_SESSION = BrowserSession()


def _run(coro):
    return asyncio.run(coro)


def _success(**payload: Any) -> dict[str, Any]:
    return {"status": "success", **payload}


def _error(exc: Exception) -> dict[str, Any]:
    return {"status": "error", "error": str(exc)}


async def _navigate(url: str) -> dict[str, Any]:
    page = await _SESSION.ensure_page()
    response = await page.goto(url, wait_until="networkidle")
    return _success(
        requested_url=url,
        current_url=page.url,
        title=await page.title(),
        http_status=response.status if response is not None else None,
    )


def navigate(url: str) -> dict[str, Any]:
    try:
        return _run(_navigate(url))
    except Exception as exc:
        return _error(exc)


async def _click(selector: str | None = None, by_text: str | None = None) -> dict[str, Any]:
    page = await _SESSION.ensure_page()
    if by_text:
        locator = page.get_by_text(by_text).first
        await locator.wait_for(timeout=10000)
        await locator.click()
        return _success(clicked_text=by_text, current_url=page.url, title=await page.title())
    if selector:
        await page.locator(selector).first.wait_for(timeout=10000)
        await page.locator(selector).first.click()
        return _success(clicked_selector=selector, current_url=page.url, title=await page.title())
    raise ValueError("selector or by_text is required")


def click(selector: str | None = None, by_text: str | None = None) -> dict[str, Any]:
    try:
        return _run(_click(selector=selector, by_text=by_text))
    except Exception as exc:
        return _error(exc)


async def _type(selector: str, text: str) -> dict[str, Any]:
    page = await _SESSION.ensure_page()
    locator = page.locator(selector).first
    await locator.wait_for(timeout=10000)
    await locator.fill(text)
    return _success(selector=selector, value_length=len(text), current_url=page.url, title=await page.title())


def type(selector: str, text: str) -> dict[str, Any]:
    try:
        return _run(_type(selector, text))
    except Exception as exc:
        return _error(exc)


async def _get_text(selector: str = "body") -> dict[str, Any]:
    page = await _SESSION.ensure_page()
    locator = page.locator(selector).first
    await locator.wait_for(timeout=10000)
    content = await locator.inner_text()
    return _success(selector=selector, content=content, current_url=page.url, title=await page.title())


def get_text(selector: str = "body") -> dict[str, Any]:
    try:
        return _run(_get_text(selector))
    except Exception as exc:
        return _error(exc)


async def _wait_for_text(text: str, timeout_ms: int = 30000) -> dict[str, Any]:
    page = await _SESSION.ensure_page()
    locator = page.get_by_text(text).first
    await locator.wait_for(timeout=timeout_ms)
    return _success(found_text=text, current_url=page.url, title=await page.title())


def wait_for_text(text: str, timeout_ms: int = 30000) -> dict[str, Any]:
    try:
        return _run(_wait_for_text(text, timeout_ms=timeout_ms))
    except Exception as exc:
        return _error(exc)


async def _screenshot(path: str) -> dict[str, Any]:
    page = await _SESSION.ensure_page()
    target = Path(path).expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    await page.screenshot(path=str(target), full_page=True)
    return _success(path=str(target), current_url=page.url, title=await page.title(), bytes_written=target.stat().st_size)


def screenshot(path: str) -> dict[str, Any]:
    try:
        return _run(_screenshot(path))
    except Exception as exc:
        return _error(exc)


async def _get_url() -> dict[str, Any]:
    page = await _SESSION.ensure_page()
    return _success(current_url=page.url, title=await page.title())


def get_url() -> dict[str, Any]:
    try:
        return _run(_get_url())
    except Exception as exc:
        return _error(exc)


async def _execute_js(script: str) -> dict[str, Any]:
    page = await _SESSION.ensure_page()
    result = await page.evaluate(script)
    return _success(result=result, current_url=page.url, title=await page.title())


def execute_js(script: str) -> dict[str, Any]:
    try:
        return _run(_execute_js(script))
    except Exception as exc:
        return _error(exc)


async def _fill_form(fields: dict[str, str]) -> dict[str, Any]:
    page = await _SESSION.ensure_page()
    filled: list[str] = []
    for selector, value in fields.items():
        locator = page.locator(selector).first
        await locator.wait_for(timeout=10000)
        await locator.fill(value)
        filled.append(selector)
    return _success(filled_fields=filled, field_count=len(filled), current_url=page.url, title=await page.title())


def fill_form(fields: dict[str, str]) -> dict[str, Any]:
    try:
        return _run(_fill_form(fields))
    except Exception as exc:
        return _error(exc)


async def _new_tab(url: str | None = None) -> dict[str, Any]:
    page = await _SESSION.new_tab(url)
    return _success(current_url=page.url, title=await page.title())


def new_tab(url: str | None = None) -> dict[str, Any]:
    try:
        return _run(_new_tab(url))
    except Exception as exc:
        return _error(exc)
