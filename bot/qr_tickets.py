from __future__ import annotations

from pathlib import Path
import json
import uuid

import qrcode

from bot.database import Database, Order


class TicketIssuer:
    def __init__(
        self,
        *,
        database: Database,
        output_dir: Path,
        pool_path: Path,
        allow_dynamic_qr: bool,
    ) -> None:
        self.database = database
        self.output_dir = output_dir
        self.pool_path = pool_path
        self.allow_dynamic_qr = allow_dynamic_qr
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._load_pool()

    def issue_for_order(self, order: Order) -> tuple[str, Path]:
        if order.ticket_code and order.qr_image_path:
            return order.ticket_code, Path(order.qr_image_path)

        code = self.database.reserve_ticket_code(
            tariff_key=order.tariff_key,
            order_id=order.id,
        )
        if code is None:
            if not self.allow_dynamic_qr:
                raise RuntimeError(f"No QR codes left for tariff '{order.tariff_key}'")
            code = self._dynamic_ticket_code(order)

        image_path = self._render_qr(order=order, code=code)
        self.database.mark_paid(
            order_id=order.id,
            ticket_code=code,
            qr_image_path=str(image_path),
        )
        return code, image_path

    def _load_pool(self) -> None:
        if not self.pool_path.exists():
            return

        with self.pool_path.open("r", encoding="utf-8") as file:
            raw_pool = json.load(file)

        if not isinstance(raw_pool, dict):
            raise RuntimeError("QR_POOL_PATH must contain a JSON object")

        for tariff_key, codes in raw_pool.items():
            if not isinstance(codes, list):
                raise RuntimeError(f"QR pool for '{tariff_key}' must be a list")
            cleaned_codes = [str(code).strip() for code in codes if str(code).strip()]
            self.database.upsert_pool_codes(str(tariff_key), cleaned_codes)

    def _dynamic_ticket_code(self, order: Order) -> str:
        return f"TICKET:{order.tariff_key}:{order.id}:{uuid.uuid4().hex}"

    def _render_qr(self, *, order: Order, code: str) -> Path:
        path = self.output_dir / f"{order.id}.png"
        image = qrcode.make(code)
        image.save(path)
        return path
