from __future__ import annotations

import asyncio
from typing import Any

from imos.adapters.payments.common import BasePaymentAdapter


class StripeAdapter(BasePaymentAdapter):
    def __init__(self, name: str = "stripe", config: dict[str, Any] | None = None) -> None:
        super().__init__(
            name=name,
            config=config,
            capabilities=["customers", "payment_intents", "charges", "subscriptions", "products", "invoices", "payouts", "webhooks"],
        )
        self.secret_key = (config or {}).get("STRIPE_SECRET_KEY", "")
        self.webhook_secret = (config or {}).get("STRIPE_WEBHOOK_SECRET", "")
        self.stripe = None

    async def connect(self) -> bool:
        try:
            import stripe
        except ModuleNotFoundError:
            self.status = "error"
            return False
        stripe.api_key = self.secret_key
        self.stripe = stripe
        self.status = "connected"
        return True

    async def health_check(self) -> bool:
        return bool(self.secret_key)

    async def create_customer(self, confirm: bool = False, **kwargs) -> Any:
        self.require_confirmation(confirm)
        return await asyncio.to_thread(self.stripe.Customer.create, **kwargs)

    async def retrieve_customer(self, customer_id: str) -> Any:
        return await asyncio.to_thread(self.stripe.Customer.retrieve, customer_id)

    async def update_customer(self, customer_id: str, confirm: bool = False, **kwargs) -> Any:
        self.require_confirmation(confirm)
        return await asyncio.to_thread(self.stripe.Customer.modify, customer_id, **kwargs)

    async def list_customers(self, **kwargs) -> Any:
        return await asyncio.to_thread(self.stripe.Customer.list, **kwargs)

    async def delete_customer(self, customer_id: str, confirm: bool = False) -> Any:
        self.require_confirmation(confirm)
        return await asyncio.to_thread(self.stripe.Customer.delete, customer_id)

    async def create_payment_intent(self, confirm: bool = False, **kwargs) -> Any:
        self.require_confirmation(confirm)
        return await asyncio.to_thread(self.stripe.PaymentIntent.create, **kwargs)

    async def confirm_payment_intent(self, payment_intent_id: str, confirm: bool = False) -> Any:
        self.require_confirmation(confirm)
        return await asyncio.to_thread(self.stripe.PaymentIntent.confirm, payment_intent_id)

    async def capture_payment_intent(self, payment_intent_id: str, confirm: bool = False) -> Any:
        self.require_confirmation(confirm)
        return await asyncio.to_thread(self.stripe.PaymentIntent.capture, payment_intent_id)

    async def cancel_payment_intent(self, payment_intent_id: str, confirm: bool = False) -> Any:
        self.require_confirmation(confirm)
        return await asyncio.to_thread(self.stripe.PaymentIntent.cancel, payment_intent_id)

    async def create_charge(self, confirm: bool = False, **kwargs) -> Any:
        self.require_confirmation(confirm)
        return await asyncio.to_thread(self.stripe.Charge.create, **kwargs)

    async def retrieve_charge(self, charge_id: str) -> Any:
        return await asyncio.to_thread(self.stripe.Charge.retrieve, charge_id)

    async def list_charges(self, **kwargs) -> Any:
        return await asyncio.to_thread(self.stripe.Charge.list, **kwargs)

    async def refund_charge(self, charge_id: str, confirm: bool = False, **kwargs) -> Any:
        self.require_confirmation(confirm)
        return await asyncio.to_thread(self.stripe.Refund.create, charge=charge_id, **kwargs)

    async def create_subscription(self, confirm: bool = False, **kwargs) -> Any:
        self.require_confirmation(confirm)
        return await asyncio.to_thread(self.stripe.Subscription.create, **kwargs)

    async def update_subscription(self, subscription_id: str, confirm: bool = False, **kwargs) -> Any:
        self.require_confirmation(confirm)
        return await asyncio.to_thread(self.stripe.Subscription.modify, subscription_id, **kwargs)

    async def cancel_subscription(self, subscription_id: str, confirm: bool = False) -> Any:
        self.require_confirmation(confirm)
        return await asyncio.to_thread(self.stripe.Subscription.cancel, subscription_id)

    async def list_subscriptions(self, **kwargs) -> Any:
        return await asyncio.to_thread(self.stripe.Subscription.list, **kwargs)

    async def create_product(self, confirm: bool = False, **kwargs) -> Any:
        self.require_confirmation(confirm)
        return await asyncio.to_thread(self.stripe.Product.create, **kwargs)

    async def update_product(self, product_id: str, confirm: bool = False, **kwargs) -> Any:
        self.require_confirmation(confirm)
        return await asyncio.to_thread(self.stripe.Product.modify, product_id, **kwargs)

    async def archive_product(self, product_id: str, confirm: bool = False) -> Any:
        self.require_confirmation(confirm)
        return await asyncio.to_thread(self.stripe.Product.modify, product_id, active=False)

    async def create_invoice(self, confirm: bool = False, **kwargs) -> Any:
        self.require_confirmation(confirm)
        return await asyncio.to_thread(self.stripe.Invoice.create, **kwargs)

    async def send_invoice(self, invoice_id: str, confirm: bool = False) -> Any:
        self.require_confirmation(confirm)
        return await asyncio.to_thread(self.stripe.Invoice.send_invoice, invoice_id)

    async def retrieve_invoice(self, invoice_id: str) -> Any:
        return await asyncio.to_thread(self.stripe.Invoice.retrieve, invoice_id)

    async def pay_invoice(self, invoice_id: str, confirm: bool = False) -> Any:
        self.require_confirmation(confirm)
        return await asyncio.to_thread(self.stripe.Invoice.pay, invoice_id)

    async def void_invoice(self, invoice_id: str, confirm: bool = False) -> Any:
        self.require_confirmation(confirm)
        return await asyncio.to_thread(self.stripe.Invoice.void_invoice, invoice_id)

    async def create_payout(self, confirm: bool = False, **kwargs) -> Any:
        self.require_confirmation(confirm)
        return await asyncio.to_thread(self.stripe.Payout.create, **kwargs)

    async def retrieve_payout(self, payout_id: str) -> Any:
        return await asyncio.to_thread(self.stripe.Payout.retrieve, payout_id)

    async def list_payouts(self, **kwargs) -> Any:
        return await asyncio.to_thread(self.stripe.Payout.list, **kwargs)

    async def receive_webhook(self, payload: bytes, signature: str) -> Any:
        return await asyncio.to_thread(self.stripe.Webhook.construct_event, payload, signature, self.webhook_secret)
