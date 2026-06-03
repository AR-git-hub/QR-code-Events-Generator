# Чеклист передачи проекта

Используйте этот список перед отправкой проекта другому человеку.

## Перед сборкой zip

1. Остановить локальный бот через `STOP_BOT_WINDOWS.bat`.
2. Не отправлять `.env`, потому что там токены и ключи.
3. Не отправлять `.venv`, потому что скрипт запуска сам создаст окружение.
4. Не отправлять `data/bot.sqlite3`, `data/qr/`, `data/qr_pool.json`, `data/exports/`, `data/free_qr/`, `logs/`.
5. Запустить `CHECK_PROJECT_WINDOWS.bat`.
6. Если нужен APK сразу, запустить `BUILD_VALIDATOR_APK_WINDOWS.bat` на компьютере с Android Studio/SDK.
7. Запустить `MAKE_RELEASE_ZIP_WINDOWS.bat`.

Готовый архив:

```text
.release\qr-ticket-bot-release.zip
```

## Что отправлять

Отправляйте только `qr-ticket-bot-release.zip`.

Получатель должен:

1. Распаковать архив.
2. Запустить `START_DEMO_WINDOWS.bat`.
3. Вставить токен Telegram-бота.
4. Проверить `/start` в Telegram.

Для реальной оплаты через СБП получатель заполняет `.env` по `.env.example` и инструкции `docs/PAYMENTS_YOOKASSA_SBP.md`, затем запускает `START_PRODUCTION_WINDOWS.bat`.

Для приложения проверяющего получатель запускает `BUILD_VALIDATOR_APK_WINDOWS.bat` или открывает `validator_app` в Android Studio.
