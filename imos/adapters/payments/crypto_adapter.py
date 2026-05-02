from __future__ import annotations

from typing import Any

import aiohttp

from imos.adapters.payments.common import BasePaymentAdapter


class CryptoAdapter(BasePaymentAdapter):
    def __init__(self, name: str = "crypto", config: dict[str, Any] | None = None) -> None:
        super().__init__(name=name, config=config, capabilities=["create_payment_link", "check_payment_status"])
        self.provider = (config or {}).get("CRYPTO_PROVIDER", "nowpayments")
        self.api_key = (config or {}).get("CRYPTO_API_KEY", "")
        self.base_url = "https://api.nowpayments.io/v1" if self.provider == "nowpayments" else "https://api.coingate.com/v2"

    async def health_check(self) -> bool:
        return bool(self.api_key)

    async def create_payment_link(self, price_amount: float, price_currency: str, pay_currency: str, confirm: bool = False, **kwargs) -> Any:
        self.require_confirmation(confirm)
        payload = {"price_amount": price_amount, "price_currency": price_currency, "pay_currency": pay_currency, **kwargs}
        return await self._request("POST", f"{self.base_url}/payment", payload)

    async def check_payment_status(self, payment_id: str) -> Any:
        return await self._request("GET", f"{self.base_url}/payment/{payment_id}")

    async def _request(self, method: str, url: str, payload: dict[str, Any] | None = None) -> Any:
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        headers = {"x-api-key": self.api_key} if self.provider == "nowpayments" else {"Authorization": f"Token {self.api_key}"}
        async with self.session.request(method, url, json=payload, headers=headers) as response:
            response.raise_for_status()
            return await response.json()
