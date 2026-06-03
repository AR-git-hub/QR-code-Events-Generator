from dataclasses import dataclass
from pathlib import Path
import os

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    bot_token: str
    payment_provider: str
    public_base_url: str
    return_url: str
    webhook_host: str
    webhook_port: int
    webhook_secret: str
    yookassa_shop_id: str
    yookassa_secret_key: str
    database_path: Path
    qr_output_dir: Path
    qr_pool_path: Path
    export_dir: Path
    free_qr_output_dir: Path
    allow_dynamic_qr: bool
    admin_user_ids: set[int]

    @property
    def yookassa_webhook_path(self) -> str:
        return f"/payments/yookassa/{self.webhook_secret}"

    @property
    def yookassa_webhook_url(self) -> str:
        return f"{self.public_base_url.rstrip('/')}{self.yookassa_webhook_path}"


def _bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _int_set_env(name: str) -> set[int]:
    value = os.getenv(name, "").strip()
    if not value:
        return set()
    result: set[int] = set()
    for part in value.split(","):
        part = part.strip()
        if part:
            result.add(int(part))
    return result


def load_settings() -> Settings:
    load_dotenv()

    bot_token = os.getenv("BOT_TOKEN", "").strip()
    if not bot_token:
        raise RuntimeError("BOT_TOKEN is required")

    payment_provider = os.getenv("PAYMENT_PROVIDER", "fake").strip().lower()
    if payment_provider not in {"fake", "yookassa"}:
        raise RuntimeError("PAYMENT_PROVIDER must be either 'fake' or 'yookassa'")

    settings = Settings(
        bot_token=bot_token,
        payment_provider=payment_provider,
        public_base_url=os.getenv("PUBLIC_BASE_URL", "http://localhost:8080"),
        return_url=os.getenv("RETURN_URL", "http://localhost:8080/return"),
        webhook_host=os.getenv("WEBHOOK_HOST", "0.0.0.0"),
        webhook_port=int(os.getenv("WEBHOOK_PORT", "8080")),
        webhook_secret=os.getenv("WEBHOOK_SECRET", "dev-secret"),
        yookassa_shop_id=os.getenv("YOOKASSA_SHOP_ID", "").strip(),
        yookassa_secret_key=os.getenv("YOOKASSA_SECRET_KEY", "").strip(),
        database_path=Path(os.getenv("DATABASE_PATH", "data/bot.sqlite3")),
        qr_output_dir=Path(os.getenv("QR_OUTPUT_DIR", "data/qr")),
        qr_pool_path=Path(os.getenv("QR_POOL_PATH", "data/qr_pool.json")),
        export_dir=Path(os.getenv("EXPORT_DIR", "data/exports")),
        free_qr_output_dir=Path(os.getenv("FREE_QR_OUTPUT_DIR", "data/free_qr")),
        allow_dynamic_qr=_bool_env("ALLOW_DYNAMIC_QR", True),
        admin_user_ids=_int_set_env("ADMIN_USER_IDS"),
    )

    if payment_provider == "yookassa":
        missing = [
            name
            for name, value in {
                "YOOKASSA_SHOP_ID": settings.yookassa_shop_id,
                "YOOKASSA_SECRET_KEY": settings.yookassa_secret_key,
                "WEBHOOK_SECRET": settings.webhook_secret,
            }.items()
            if not value or value == "dev-secret"
        ]
        if missing:
            raise RuntimeError(f"Missing production settings: {', '.join(missing)}")

    return settings
