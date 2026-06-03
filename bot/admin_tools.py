from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import json
import uuid
import zipfile

import qrcode

from bot.database import Database, FreeTicket
from bot.tariffs import get_tariff


def build_validator_export(database: Database, export_dir: Path) -> Path:
    export_dir.mkdir(parents=True, exist_ok=True)
    created_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    payload = {
        "format": "qr-ticket-validator-export",
        "version": 1,
        "created_at": created_at,
        "tickets": database.export_tickets(),
    }
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = export_dir / f"validator_export_{timestamp}.json"
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path


def create_free_tickets(
    *,
    database: Database,
    output_dir: Path,
    tariff_key: str,
    count: int,
    created_by_user_id: int,
    comment: str | None = None,
) -> tuple[list[FreeTicket], Path]:
    get_tariff(tariff_key)
    if count < 1 or count > 200:
        raise ValueError("Count must be between 1 and 200")

    output_dir.mkdir(parents=True, exist_ok=True)
    batch_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    batch_dir = output_dir / f"free_{tariff_key}_{batch_id}"
    batch_dir.mkdir(parents=True, exist_ok=True)
    tickets: list[FreeTicket] = []

    for index in range(1, count + 1):
        ticket_id = uuid.uuid4().hex
        code = f"FREE:{tariff_key}:{ticket_id}:{uuid.uuid4().hex}"
        image_path = batch_dir / f"{index:03d}_{tariff_key}.png"
        qrcode.make(code).save(image_path)
        ticket = database.create_free_ticket(
            ticket_id=ticket_id,
            code=code,
            tariff_key=tariff_key,
            comment=comment,
            qr_image_path=str(image_path),
            created_by_user_id=created_by_user_id,
        )
        tickets.append(ticket)

    manifest_path = batch_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "format": "qr-ticket-free-batch",
                "version": 1,
                "tariff": tariff_key,
                "count": count,
                "tickets": [
                    {
                        "id": ticket.id,
                        "code": ticket.code,
                        "tariff": ticket.tariff_key,
                        "image": Path(ticket.qr_image_path).name,
                    }
                    for ticket in tickets
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    zip_path = output_dir / f"free_{tariff_key}_{batch_id}.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for file_path in batch_dir.iterdir():
            archive.write(file_path, arcname=file_path.name)

    return tickets, zip_path
