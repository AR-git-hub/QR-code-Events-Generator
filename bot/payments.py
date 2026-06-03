from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
import uuid

from aiohttp import BasicAuth, ClientSession

from bot.config import Settings
from bot.database import Order
from bot.tariffs import get_tariff


@dataclass(frozen=True)
class PaymentInit:
    payment_id: str
    confirmation_url: str


@dataclass(frozen=True)
class PaymentStatus:
    payment_id: str
    status: str
    paid: bool
    amount_kopecks: int


class PaymentProvider:
    async def create_payment(self, order: Order) -> PaymentInit:
        raise NotImplementedError

    async def get_payment(self, payment_id: str) -> PaymentStatus:
        raise NotImplementedError

    async def close(self) -> None:
        return None


class FakePaymentProvider(PaymentProvider):
    def __init__(self) -> None:
        self._payments: dict[str, int] = {}

    async def create_payment(self, order: Order) -> PaymentInit:
        payment_id = f"fake-{order.id}"
        self._payments[payment_id] = order.amount_kopecks
        return PaymentInit(
            payment_id=payment_id,
            confirmation_url=f"https://example.test/pay/{order.id}",
        )

    async def get_payment(self, payment_id: str) -> PaymentStatus:
        return PaymentStatus(
            payment_id=payment_id,
            status="succeeded",
            paid=True,
            amount_kopecks=self._payments.get(payment_id, 0),
        )


class YooKassaPaymentProvider(PaymentProvider):
    API_URL = "https://api.yookassa.ru/v3"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.session = ClientSession(
            auth=BasicAuth(settings.yookassa_shop_id, settings.yookassa_secret_key),
            trust_env=True,
        )

    async def create_payment(self, order: Order) -> PaymentInit:
        amount = Decimal(order.amount_kopecks) / Decimal(100)
        payload = {
            "amount": {
                "value": f"{amount:.2f}",
                "currency": "RUB",
            },
            "capture": True,
            "confirmation": {
                "type": "redirect",
                "return_url": self.settings.return_url,
            },
            "description": f"Билет: {get_tariff(order.tariff_key).title}",
            "metadata": {
                "order_id": order.id,
                "user_id": str(order.user_id),
                "tariff": order.tariff_key,
            },
            "payment_method_data": {
                "type": "sbp",
            },
        }

        headers = {"Idempotence-Key": str(uuid.uuid4())}
        async with self.session.post(
            f"{self.API_URL}/payments",
            json=payload,
            headers=headers,
        ) as response:
            data = await response.json()
            if response.status >= 400:
                raise RuntimeError(f"YooKassa create payment failed: {data}")

        confirmation = data.get("confirmation") or {}
        confirmation_url = confirmation.get("confirmation_url")
        payment_id = data.get("id")
        if not payment_id or not confirmation_url:
            raise RuntimeError(f"YooKassa response has no confirmation URL: {data}")

        return PaymentInit(payment_id=payment_id, confirmation_url=confirmation_url)

    async def get_payment(self, payment_id: str) -> PaymentStatus:
        async with self.session.get(f"{self.API_URL}/payments/{payment_id}") as response:
            data = await response.json()
            if response.status >= 400:
                raise RuntimeError(f"YooKassa get payment failed: {data}")
        return _parse_yookassa_payment(data)

    async def close(self) -> None:
        await self.session.close()


def build_payment_provider(settings: Settings) -> PaymentProvider:
    if settings.payment_provider == "yookassa":
        return YooKassaPaymentProvider(settings)
    return FakePaymentProvider()


def _parse_yookassa_payment(data: dict) -> PaymentStatus:
    amount = data.get("amount") or {}
    value = Decimal(str(amount.get("value", "0")))
    return PaymentStatus(
        payment_id=str(data["id"]),
        status=str(data.get("status", "")),
        paid=bool(data.get("paid")) and data.get("status") == "succeeded",
        amount_kopecks=int(value * 100),
    )
