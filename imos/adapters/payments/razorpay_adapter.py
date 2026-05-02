from __future__ import annotations

import asyncio
from typing import Any

from imos.adapters.payments.common import BasePaymentAdapter


class RazorpayAdapter(BasePaymentAdapter):
    def __init__(self, name: str = "razorpay", config: dict[str, Any] | None = None) -> None:
        super().__init__(name=name, config=config, capabilities=["orders", "payments", "refunds", "settlements", "invoices"])
        self.key_id = (config or {}).get("RAZORPAY_KEY_ID", "")
        self.key_secret = (config or {}).get("RAZORPAY_KEY_SECRET", "")
        self.client = None

    async def connect(self) -> bool:
        try:
            import razorpay
        except ModuleNotFoundError:
            self.status = "error"
            return False
        self.client = razorpay.Client(auth=(self.key_id, self.key_secret))
        self.status = "connected"
        return True

    async def health_check(self) -> bool:
        return bool(self.key_id and self.key_secret)

    async def create_order(self, confirm: bool = False, **kwargs) -> Any:
        self.require_confirmation(confirm)
        return await asyncio.to_thread(self.client.order.create, kwargs)

    async def fetch_payment(self, payment_id: str) -> Any:
        return await asyncio.to_thread(self.client.payment.fetch, payment_id)

    async def refund_payment(self, payment_id: str, confirm: bool = False, **kwargs) -> Any:
        self.require_confirmation(confirm)
        return await asyncio.to_thread(self.client.payment.refund, payment_id, kwargs)
