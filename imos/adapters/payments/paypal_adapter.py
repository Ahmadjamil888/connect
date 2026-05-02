from __future__ import annotations

import base64
from typing import Any

import aiohttp

from imos.adapters.payments.common import BasePaymentAdapter


class PaypalAdapter(BasePaymentAdapter):
    def __init__(self, name: str = "paypal", config: dict[str, Any] | None = None) -> None:
        super().__init__(name=name, config=config, capabilities=["orders", "payments", "payouts", "subscriptions"])
        self.client_id = (config or {}).get("PAYPAL_CLIENT_ID", "")
        self.client_secret = (config or {}).get("PAYPAL_CLIENT_SECRET", "")
        self.mode = (config or {}).get("PAYPAL_MODE", "sandbox")
        self.base_url = "https://api-m.sandbox.paypal.com" if self.mode == "sandbox" else "https://api-m.paypal.com"
        self.token = ""

    async def connect(self) -> bool:
        self.token = await self._token()
        self.status = "connected" if self.token else "error"
        return bool(self.token)

    async def health_check(self) -> bool:
        return bool(self.token or await self.connect())

    async def create_order(self, confirm: bool = False, **kwargs) -> Any:
        self.require_confirmation(confirm)
        return await self._request("POST", f"{self.base_url}/v2/checkout/orders", kwargs)

    async def capture_order(self, order_id: str, confirm: bool = False) -> Any:
        self.require_confirmation(confirm)
        return await self._request("POST", f"{self.base_url}/v2/checkout/orders/{order_id}/capture", {})

    async def authorize_order(self, order_id: str, confirm: bool = False) -> Any:
        self.require_confirmation(confirm)
        return await self._request("POST", f"{self.base_url}/v2/checkout/orders/{order_id}/authorize", {})

    async def create_payout(self, confirm: bool = False, **kwargs) -> Any:
        self.require_confirmation(confirm)
        return await self._request("POST", f"{self.base_url}/v1/payments/payouts", kwargs)

    async def get_payout_status(self, payout_batch_id: str) -> Any:
        return await self._request("GET", f"{self.base_url}/v1/payments/payouts/{payout_batch_id}")

    async def _token(self) -> str:
        basic = base64.b64encode(f"{self.client_id}:{self.client_secret}".encode()).decode()
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        async with self.session.post(
            f"{self.base_url}/v1/oauth2/token",
            data={"grant_type": "client_credentials"},
            headers={"Authorization": f"Basic {basic}"},
        ) as response:
            response.raise_for_status()
            payload = await response.json()
            return payload.get("access_token", "")

    async def _request(self, method: str, url: str, payload: dict[str, Any] | None = None) -> Any:
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        async with self.session.request(method, url, json=payload, headers={"Authorization": f"Bearer {self.token}"}) as response:
            response.raise_for_status()
            return await response.json()
