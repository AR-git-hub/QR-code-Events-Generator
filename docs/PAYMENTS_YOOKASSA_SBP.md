# Подключение YooKassa и СБП

В проекте уже есть интеграция YooKassa для оплаты через СБП.

Сценарий такой:

1. Пользователь выбирает тариф в Telegram.
2. Бот создает платеж в YooKassa.
3. Пользователь переходит по кнопке оплаты и оплачивает через СБП.
4. YooKassa отправляет webhook об успешной оплате.
5. Бот перепроверяет платеж через API YooKassa.
6. Только после этого бот выдает QR-код билета.

## Что нужно владельцу проекта

1. Telegram bot token из BotFather.
2. Магазин YooKassa с включенным СБП.
3. `YOOKASSA_SHOP_ID`.
4. `YOOKASSA_SECRET_KEY`.
5. Публичный HTTPS-домен, который ведет на сервер с ботом.

## Настройки `.env`

Создайте `.env` из `.env.example` и заполните:

```env
BOT_TOKEN=...
PAYMENT_PROVIDER=yookassa
PUBLIC_BASE_URL=https://tickets.example.ru
RETURN_URL=https://tickets.example.ru/return
WEBHOOK_SECRET=long-random-string
YOOKASSA_SHOP_ID=...
YOOKASSA_SECRET_KEY=...
```

Webhook URL будет таким:

```text
https://tickets.example.ru/payments/yookassa/long-random-string
```

Добавьте этот URL в настройках webhook-уведомлений YooKassa для событий:

- `payment.succeeded`
- `payment.canceled`

## Как бот защищается от ложной выдачи QR

Бот не выдает QR по нажатию кнопки оплаты. QR выдается только если:

- YooKassa прислала событие `payment.succeeded`;
- повторная проверка платежа через API вернула успешный статус;
- сумма платежа совпала с выбранным тарифом.

## Локальный тест

Для теста без денег используйте:

```env
PAYMENT_PROVIDER=fake
```

В этом режиме кнопка `Демо: подтвердить оплату` имитирует успешную оплату.

## Официальные ссылки

- СБП в YooKassa: https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/sbp
- Создание платежа API: https://yookassa.ru/developers/api#create_payment
- Webhook-уведомления: https://yookassa.ru/developers/using-api/webhooks
