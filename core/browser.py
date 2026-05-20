import asyncio
from pathlib import Path

from playwright.async_api import Browser as PWBrowser
from playwright.async_api import Page, async_playwright


class Browser:
    def __init__(self) -> None:
        self._playwright = None
        self._browser: PWBrowser | None = None
        self._page: Page | None = None
        self._loop = asyncio.new_event_loop()

    def _run(self, coro):
        return self._loop.run_until_complete(coro)

    async def _ensure_ready(self) -> None:
        if self._page is not None:
            return
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(headless=False)
        context = await self._browser.new_context()
        self._page = await context.new_page()

    def navigate(self, url: str) -> None:
        async def _inner():
            await self._ensure_ready()
            await self._page.goto(url)
        self._run(_inner())

    def click(self, selector: str) -> None:
        async def _inner():
            await self._ensure_ready()
            await self._page.click(selector)
        self._run(_inner())

    def type_text(self, selector: str, text: str) -> None:
        async def _inner():
            await self._ensure_ready()
            await self._page.fill(selector, text)
        self._run(_inner())

    def get_text(self, selector: str) -> str:
        async def _inner():
            await self._ensure_ready()
            return await self._page.text_content(selector) or ""
        return self._run(_inner())

    def screenshot(self, path: str = "screenshot.png") -> None:
        async def _inner():
            await self._ensure_ready()
            destination = Path(path).resolve()
            destination.parent.mkdir(parents=True, exist_ok=True)
            await self._page.screenshot(path=str(destination), full_page=True)
        self._run(_inner())

    def close(self) -> None:
        async def _inner():
            if self._browser is not None:
                await self._browser.close()
                self._browser = None
            if self._playwright is not None:
                await self._playwright.stop()
                self._playwright = None
            self._page = None
        self._run(_inner())
