from pathlib import Path
import sys
from tempfile import TemporaryDirectory

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from bot.admin_tools import build_validator_export, create_free_tickets
from bot.database import Database
from bot.qr_tickets import TicketIssuer
from bot.tariffs import get_tariff


def main() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        db = Database(root / "test.sqlite3")
        tariff = get_tariff("basic")
        db.upsert_pool_codes("basic", ["BASIC-SMOKE-001"])
        order = db.create_order(
            order_id="smoke-order",
            user_id=1,
            tariff_key=tariff.key,
            amount_kopecks=tariff.amount_kopecks,
        )
        issuer = TicketIssuer(
            database=db,
            output_dir=root / "qr",
            pool_path=root / "missing.json",
            allow_dynamic_qr=False,
        )
        code, image_path = issuer.issue_for_order(order)
        assert code == "BASIC-SMOKE-001"
        assert image_path.exists()
        assert db.get_order("smoke-order").status == "paid"
        tickets, zip_path = create_free_tickets(
            database=db,
            output_dir=root / "free",
            tariff_key="light",
            count=2,
            created_by_user_id=123,
        )
        assert len(tickets) == 2
        assert zip_path.exists()
        export_path = build_validator_export(db, root / "exports")
        exported = export_path.read_text(encoding="utf-8")
        assert "BASIC-SMOKE-001" in exported
        assert "FREE:light:" in exported

    print("smoke ok")


if __name__ == "__main__":
    main()
