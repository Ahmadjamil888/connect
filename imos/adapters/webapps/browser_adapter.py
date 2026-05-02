from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from imos.adapters.webapps.common import BaseWebAdapter


class BrowserAdapter(BaseWebAdapter):
    def __init__(self, name: str = "browser", config: dict[str, Any] | None = None) -> None:
        super().__init__(
            name=name,
            config=config,
            capabilities=[
                "navigate",
                "click",
                "fill",
                "submit",
                "screenshot",
                "extract_text",
                "extract_links",
                "wait_for_element",
                "scroll",
                "execute_javascript",
                "download_file",
                "upload_file",
                "cookies",
                "record_actions",
                "replay_actions",
            ],
        )
        self.browser_type = (config or {}).get("BROWSER_TYPE", "chromium")
        self.headless = str((config or {}).get("HEADLESS", "true")).lower() == "true"
        self.storage_path = Path((config or {}).get("session_storage", Path.home() / ".imos" / "browser_state.json"))
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self.recorded_actions: list[dict[str, Any]] = []

    async def connect(self) -> bool:
        from playwright.async_api import async_playwright

        self.playwright = await async_playwright().start()
        launcher = getattr(self.playwright, self.browser_type)
        self.browser = await launcher.launch(headless=self.headless)
        context_args = {"storage_state": str(self.storage_path)} if self.storage_path.exists() else {}
        self.context = await self.browser.new_context(**context_args)
        self.page = await self.context.new_page()
        self.status = "connected"
        return True

    async def disconnect(self) -> None:
        if self.context:
            await self.context.storage_state(path=str(self.storage_path))
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
        self.status = "disconnected"

    async def health_check(self) -> bool:
        return self.page is not None

    async def navigate(self, url: str) -> Any:
        await self.page.goto(url)
        self.recorded_actions.append({"action": "navigate", "url": url})
        return {"url": self.page.url, "title": await self.page.title()}

    async def click(self, selector: str | None = None, text: str | None = None, role: str | None = None) -> Any:
        if selector:
            await self.page.click(selector)
        elif text:
            await self.page.get_by_text(text).click()
        elif role:
            await self.page.get_by_role(role).click()
        self.recorded_actions.append({"action": "click", "selector": selector, "text": text, "role": role})
        return {"status": "clicked"}

    async def fill(self, selector: str, value: str) -> Any:
        await self.page.fill(selector, value)
        self.recorded_actions.append({"action": "fill", "selector": selector, "value": value})
        return {"status": "filled"}

    async def submit(self, selector: str) -> Any:
        await self.page.press(selector, "Enter")
        self.recorded_actions.append({"action": "submit", "selector": selector})
        return {"status": "submitted"}

    async def screenshot(self, path: str) -> Any:
        await self.page.screenshot(path=path, full_page=True)
        return {"path": path}

    async def extract_text(self, selector: str = "body") -> Any:
        return await self.page.inner_text(selector)

    async def extract_links(self) -> Any:
        return await self.page.eval_on_selector_all("a", "els => els.map(el => ({text: el.innerText, href: el.href}))")

    async def wait_for_element(self, selector: str, timeout: int = 30000) -> Any:
        await self.page.wait_for_selector(selector, timeout=timeout)
        return {"selector": selector, "status": "ready"}

    async def scroll(self, amount: int = 800) -> Any:
        await self.page.mouse.wheel(0, amount)
        return {"scrolled": amount}

    async def execute_javascript(self, script: str) -> Any:
        return await self.page.evaluate(script)

    async def download_file(self, trigger_selector: str, path: str) -> Any:
        async with self.page.expect_download() as download_info:
            await self.page.click(trigger_selector)
        download = await download_info.value
        await download.save_as(path)
        return {"path": path}

    async def upload_file(self, selector: str, path: str) -> Any:
        await self.page.set_input_files(selector, path)
        return {"uploaded": path}

    async def cookies(self) -> Any:
        return await self.context.cookies()

    async def record_actions(self) -> Any:
        return list(self.recorded_actions)

    async def replay_actions(self, actions: list[dict[str, Any]] | None = None) -> Any:
        for action in actions or self.recorded_actions:
            name = action["action"]
            if name == "navigate":
                await self.navigate(action["url"])
            elif name == "click":
                await self.click(selector=action.get("selector"), text=action.get("text"), role=action.get("role"))
            elif name == "fill":
                await self.fill(action["selector"], action["value"])
        return {"replayed": len(actions or self.recorded_actions)}
