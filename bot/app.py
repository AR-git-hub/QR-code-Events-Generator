from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import Awaitable, Callable

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    CallbackQuery,
    FSInputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from aiohttp import ClientSession, web

from bot.admin_tools import build_validator_export, create_free_tickets
from bot.config import Settings, load_settings
from bot.database import Database, Order
from bot.payments import PaymentProvider, PaymentStatus, build_payment_provider
from bot.qr_tickets import TicketIssuer
from bot.tariffs import TARIFFS, get_tariff

logger = logging.getLogger(__name__)


class EnvAwareAiohttpSession(AiohttpSession):
    async def create_session(self) -> ClientSession:
        if self._should_reset_connector:
            await self.close()

        if self._session is None or self._session.closed:
            self._session = ClientSession(
                connector=self._connector_type(**self._connector_init),
                headers={"User-Agent": "aiogram"},
                trust_env=True,
            )
            self._should_reset_connector = False

        return self._session


def tariff_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"{tariff.title} - {tariff.amount_rub} руб.",
                    callback_data=f"tariff:{tariff.key}",
                )
            ]
            for tariff in TARIFFS.values()
        ]
    )


def payment_keyboard(
    *,
    order: Order,
    confirmation_url: str,
    fake_mode: bool,
) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="Оплатить через СБП", url=confirmation_url)],
        [InlineKeyboardButton(text="Проверить оплату", callback_data=f"status:{order.id}")],
    ]
    if fake_mode:
        rows.append(
            [
                InlineKeyboardButton(
                    text="Демо: подтвердить оплату",
                    callback_data=f"demo_paid:{order.id}",
                )
            ]
        )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def is_admin(settings: Settings, user_id: int) -> bool:
    return user_id in settings.admin_user_ids


def admin_help_text() -> str:
    return (
        "Админ-команды:\n\n"
        "/export - выгрузить базу билетов для приложения проверяющего\n"
        "/free light 10 - создать 10 бесплатных QR для тарифа light\n"
        "/free basic 5 - создать 5 бесплатных QR для тарифа basic\n"
        "/free luxury 3 - создать 3 бесплатных QR для тарифа luxury\n\n"
        "После /free обязательно снова сделайте /export, чтобы бесплатные QR попали в базу для телефона."
    )


async def run() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    settings = load_settings()
    database = Database(settings.database_path)
    ticket_issuer = TicketIssuer(
        database=database,
        output_dir=settings.qr_output_dir,
        pool_path=settings.qr_pool_path,
        allow_dynamic_qr=settings.allow_dynamic_qr,
    )
    payment_provider = build_payment_provider(settings)

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        session=EnvAwareAiohttpSession(),
    )
    dispatcher = Dispatcher()
    router = Router()

    _order_locks: dict[str, asyncio.Lock] = {}

    def _get_order_lock(order_id: str) -> asyncio.Lock:
        return _order_locks.setdefault(order_id, asyncio.Lock())

    async def send_ticket(order: Order) -> None:
        ticket_code, image_path = ticket_issuer.issue_for_order(order)
        tariff = get_tariff(order.tariff_key)
        await bot.send_photo(
            chat_id=order.user_id,
            photo=FSInputFile(image_path),
            caption=(
                f"Оплата подтверждена.\n\n"
                f"Тариф: <b>{tariff.title}</b>\n"
                f"Ваш билетный QR-код: <code>{ticket_code}</code>"
            ),
        )

    async def fulfill_paid_order(
        *,
        order: Order,
        payment_status: PaymentStatus,
        query: CallbackQuery | None = None,
    ) -> None:
        async with _get_order_lock(order.id):
            # Re-fetch to get the definitive status after acquiring the lock,
            # so two concurrent webhook/button calls can't both issue a ticket.
            fresh = database.get_order(order.id)
            if fresh is None:
                return
            if fresh.status == "paid":
                if fresh.qr_image_path:
                    await bot.send_photo(
                        chat_id=fresh.user_id,
                        photo=FSInputFile(fresh.qr_image_path),
                        caption="Этот заказ уже оплачен. Отправляю QR-код повторно.",
                    )
                if query:
                    await query.answer("QR-код уже был выдан")
                return

            if not payment_status.paid:
                if query:
                    await query.answer("Оплата пока не найдена", show_alert=True)
                return

            if payment_status.amount_kopecks != fresh.amount_kopecks:
                logger.warning(
                    "Payment amount mismatch: order=%s expected=%s got=%s",
                    fresh.id,
                    fresh.amount_kopecks,
                    payment_status.amount_kopecks,
                )
                if query:
                    await query.answer("Сумма оплаты не совпала с заказом", show_alert=True)
                return

            await send_ticket(fresh)
            if query:
                await query.answer("Оплата подтверждена")

    @router.message(CommandStart())
    async def start(message: Message) -> None:
        await message.answer(
            "Выберите тариф билета:",
            reply_markup=tariff_keyboard(),
        )

    @router.message(Command("admin"))
    async def admin(message: Message) -> None:
        if not is_admin(settings, message.from_user.id):
            await message.answer("У вас нет доступа к админ-командам.")
            return
        await message.answer(admin_help_text())

    @router.message(Command("id"))
    async def user_id(message: Message) -> None:
        await message.answer(f"Ваш Telegram user ID: <code>{message.from_user.id}</code>")

    @router.message(Command("export"))
    async def export_tickets(message: Message) -> None:
        if not is_admin(settings, message.from_user.id):
            await message.answer("У вас нет доступа к экспорту.")
            return

        export_path = build_validator_export(database, settings.export_dir)
        await message.answer_document(
            FSInputFile(export_path),
            caption=(
                "Экспорт готов. Импортируйте этот JSON в приложение проверяющего.\n\n"
                "Важно: каждый новый экспорт заменяет базу на телефоне. Делайте экспорт после завершения продаж."
            ),
        )

    @router.message(Command("free"))
    async def free_tickets(message: Message) -> None:
        if not is_admin(settings, message.from_user.id):
            await message.answer("У вас нет доступа к бесплатным QR.")
            return

        parts = (message.text or "").split(maxsplit=3)
        if len(parts) < 3:
            await message.answer("Формат: /free light 10\nТарифы: light, basic, luxury")
            return

        tariff_key = parts[1].strip().lower()
        try:
            count = int(parts[2])
            comment = parts[3].strip() if len(parts) > 3 else None
            tickets, zip_path = create_free_tickets(
                database=database,
                output_dir=settings.free_qr_output_dir,
                tariff_key=tariff_key,
                count=count,
                created_by_user_id=message.from_user.id,
                comment=comment,
            )
        except Exception as exc:
            await message.answer(f"Не удалось создать бесплатные QR: {exc}")
            return

        await message.answer_document(
            FSInputFile(zip_path),
            caption=(
                f"Создано бесплатных QR: {len(tickets)}\n"
                "Файл содержит PNG-коды и manifest.json.\n\n"
                "Теперь выполните /export и импортируйте свежую базу в приложение проверяющего."
            ),
        )

    @router.callback_query(F.data.startswith("tariff:"))
    async def choose_tariff(query: CallbackQuery) -> None:
        assert query.data is not None
        tariff_key = query.data.split(":", 1)[1]
        tariff = get_tariff(tariff_key)
        order = database.create_order(
            order_id=uuid.uuid4().hex,
            user_id=query.from_user.id,
            tariff_key=tariff.key,
            amount_kopecks=tariff.amount_kopecks,
        )

        try:
            payment = await payment_provider.create_payment(order)
        except Exception:
            logger.exception("Payment creation failed for order %s", order.id)
            await query.answer("Не удалось создать платеж", show_alert=True)
            return

        database.attach_payment(
            order_id=order.id,
            payment_id=payment.payment_id,
            confirmation_url=payment.confirmation_url,
        )
        order = database.get_order(order.id)
        assert order is not None

        await query.message.answer(
            (
                f"Тариф: <b>{tariff.title}</b>\n"
                f"Стоимость: <b>{tariff.amount_rub} руб.</b>\n\n"
                "После подтверждения оплаты бот автоматически пришлет QR-код."
            ),
            reply_markup=payment_keyboard(
                order=order,
                confirmation_url=payment.confirmation_url,
                fake_mode=settings.payment_provider == "fake",
            ),
        )
        await query.answer()

    @router.callback_query(F.data.startswith("status:"))
    async def check_status(query: CallbackQuery) -> None:
        assert query.data is not None
        order_id = query.data.split(":", 1)[1]
        order = database.get_order(order_id)
        if order is None or order.user_id != query.from_user.id:
            await query.answer("Заказ не найден", show_alert=True)
            return
        if not order.payment_id:
            await query.answer("Платеж еще не создан", show_alert=True)
            return

        payment_status = await payment_provider.get_payment(order.payment_id)
        await fulfill_paid_order(
            order=order,
            payment_status=payment_status,
            query=query,
        )

    @router.callback_query(F.data.startswith("demo_paid:"))
    async def demo_paid(query: CallbackQuery) -> None:
        if settings.payment_provider != "fake":
            await query.answer("Демо-оплата отключена", show_alert=True)
            return
        assert query.data is not None
        order_id = query.data.split(":", 1)[1]
        order = database.get_order(order_id)
        if order is None or order.user_id != query.from_user.id or not order.payment_id:
            await query.answer("Заказ не найден", show_alert=True)
            return

        payment_status = await payment_provider.get_payment(order.payment_id)
        await fulfill_paid_order(
            order=order,
            payment_status=payment_status,
            query=query,
        )

    dispatcher.include_router(router)

    web_app = build_web_app(
        bot=bot,
        database=database,
        payment_provider=payment_provider,
        settings=settings,
        fulfill_paid_order=fulfill_paid_order,
    )
    runner = web.AppRunner(web_app)
    await runner.setup()
    site = web.TCPSite(runner, settings.webhook_host, settings.webhook_port)
    await site.start()
    logger.info("Webhook server started on %s:%s", settings.webhook_host, settings.webhook_port)
    logger.info("YooKassa webhook URL: %s", settings.yookassa_webhook_url)

    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dispatcher.start_polling(bot)
    finally:
        await runner.cleanup()
        await payment_provider.close()
        await bot.session.close()


def build_web_app(
    *,
    bot: Bot,
    database: Database,
    payment_provider: PaymentProvider,
    settings: Settings,
    fulfill_paid_order: Callable[..., Awaitable[None]],
) -> web.Application:
    app = web.Application()

    async def health(_: web.Request) -> web.Response:
        return web.json_response({"ok": True})

    async def payment_return(_: web.Request) -> web.Response:
        return web.Response(
            text="Платеж обрабатывается. Вернитесь в Telegram, бот пришлет QR-код после подтверждения.",
            content_type="text/plain",
        )

    async def yookassa_webhook(request: web.Request) -> web.Response:
        payload = await request.json()
        event = payload.get("event")
        payment = payload.get("object") or {}
        payment_id = payment.get("id")
        if not payment_id:
            return web.json_response({"ok": True})

        order = database.get_order_by_payment_id(str(payment_id))
        if order is None:
            logger.warning("Webhook for unknown payment %s", payment_id)
            return web.json_response({"ok": True})

        if event == "payment.canceled":
            database.mark_canceled(order.id)
            await bot.send_message(order.user_id, "Платеж отменен. Можно выбрать тариф заново: /start")
            return web.json_response({"ok": True})

        if event != "payment.succeeded":
            return web.json_response({"ok": True})

        payment_status = await payment_provider.get_payment(str(payment_id))
        await fulfill_paid_order(order=order, payment_status=payment_status)
        return web.json_response({"ok": True})

    app.router.add_get("/health", health)
    app.router.add_get("/return", payment_return)
    app.router.add_post(settings.yookassa_webhook_path, yookassa_webhook)
    return app


def main() -> None:
    asyncio.run(run())
