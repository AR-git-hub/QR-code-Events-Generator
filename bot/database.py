from __future__ import annotations

from dataclasses import dataclass
from contextlib import contextmanager
from pathlib import Path
import sqlite3
from collections.abc import Iterator
from typing import Any


@dataclass(frozen=True)
class Order:
    id: str
    user_id: int
    tariff_key: str
    amount_kopecks: int
    status: str
    payment_id: str | None
    confirmation_url: str | None
    ticket_code: str | None
    qr_image_path: str | None
    created_at: str
    paid_at: str | None


@dataclass(frozen=True)
class FreeTicket:
    id: str
    code: str
    tariff_key: str
    comment: str | None
    qr_image_path: str
    created_by_user_id: int
    created_at: str


class Database:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = self._connect()
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self._connection() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS orders (
                    id TEXT PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    tariff_key TEXT NOT NULL,
                    amount_kopecks INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    payment_id TEXT UNIQUE,
                    confirmation_url TEXT,
                    ticket_code TEXT,
                    qr_image_path TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    paid_at TEXT
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS ticket_pool (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tariff_key TEXT NOT NULL,
                    code TEXT NOT NULL UNIQUE,
                    issued_to_order_id TEXT UNIQUE,
                    issued_at TEXT,
                    FOREIGN KEY (issued_to_order_id) REFERENCES orders(id)
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_orders_payment_id ON orders(payment_id)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_ticket_pool_tariff ON ticket_pool(tariff_key)"
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS free_tickets (
                    id TEXT PRIMARY KEY,
                    code TEXT NOT NULL UNIQUE,
                    tariff_key TEXT NOT NULL,
                    comment TEXT,
                    qr_image_path TEXT NOT NULL,
                    created_by_user_id INTEGER NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_free_tickets_tariff ON free_tickets(tariff_key)"
            )

    def create_order(
        self,
        *,
        order_id: str,
        user_id: int,
        tariff_key: str,
        amount_kopecks: int,
    ) -> Order:
        with self._connection() as connection:
            connection.execute(
                """
                INSERT INTO orders (id, user_id, tariff_key, amount_kopecks, status)
                VALUES (?, ?, ?, ?, 'pending')
                """,
                (order_id, user_id, tariff_key, amount_kopecks),
            )
        order = self.get_order(order_id)
        assert order is not None
        return order

    def attach_payment(
        self,
        *,
        order_id: str,
        payment_id: str,
        confirmation_url: str,
    ) -> None:
        with self._connection() as connection:
            connection.execute(
                """
                UPDATE orders
                SET payment_id = ?, confirmation_url = ?
                WHERE id = ?
                """,
                (payment_id, confirmation_url, order_id),
            )

    def get_order(self, order_id: str) -> Order | None:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM orders WHERE id = ?",
                (order_id,),
            ).fetchone()
        return self._row_to_order(row)

    def get_order_by_payment_id(self, payment_id: str) -> Order | None:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM orders WHERE payment_id = ?",
                (payment_id,),
            ).fetchone()
        return self._row_to_order(row)

    def mark_paid(
        self,
        *,
        order_id: str,
        ticket_code: str,
        qr_image_path: str,
    ) -> None:
        with self._connection() as connection:
            connection.execute(
                """
                UPDATE orders
                SET status = 'paid',
                    ticket_code = ?,
                    qr_image_path = ?,
                    paid_at = CURRENT_TIMESTAMP
                WHERE id = ? AND status != 'paid'
                """,
                (ticket_code, qr_image_path, order_id),
            )

    def mark_canceled(self, order_id: str) -> None:
        with self._connection() as connection:
            connection.execute(
                "UPDATE orders SET status = 'canceled' WHERE id = ? AND status = 'pending'",
                (order_id,),
            )

    def create_free_ticket(
        self,
        *,
        ticket_id: str,
        code: str,
        tariff_key: str,
        comment: str | None,
        qr_image_path: str,
        created_by_user_id: int,
    ) -> FreeTicket:
        with self._connection() as connection:
            connection.execute(
                """
                INSERT INTO free_tickets (
                    id, code, tariff_key, comment, qr_image_path, created_by_user_id
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    ticket_id,
                    code,
                    tariff_key,
                    comment,
                    qr_image_path,
                    created_by_user_id,
                ),
            )
        ticket = self.get_free_ticket(ticket_id)
        assert ticket is not None
        return ticket

    def get_free_ticket(self, ticket_id: str) -> FreeTicket | None:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM free_tickets WHERE id = ?",
                (ticket_id,),
            ).fetchone()
        return self._row_to_free_ticket(row)

    def export_tickets(self) -> list[dict[str, Any]]:
        with self._connection() as connection:
            paid_rows = connection.execute(
                """
                SELECT id, ticket_code, tariff_key, amount_kopecks, user_id, paid_at, created_at
                FROM orders
                WHERE status = 'paid' AND ticket_code IS NOT NULL
                ORDER BY paid_at, created_at
                """
            ).fetchall()
            free_rows = connection.execute(
                """
                SELECT id, code, tariff_key, comment, created_by_user_id, created_at
                FROM free_tickets
                ORDER BY created_at
                """
            ).fetchall()

        tickets: list[dict[str, Any]] = []
        for row in paid_rows:
            tickets.append(
                {
                    "code": row["ticket_code"],
                    "ticket_id": row["id"],
                    "type": "paid",
                    "tariff": row["tariff_key"],
                    "amount_kopecks": row["amount_kopecks"],
                    "telegram_user_id": row["user_id"],
                    "paid_at": row["paid_at"],
                    "created_at": row["created_at"],
                }
            )

        for row in free_rows:
            tickets.append(
                {
                    "code": row["code"],
                    "ticket_id": row["id"],
                    "type": "free",
                    "tariff": row["tariff_key"],
                    "amount_kopecks": 0,
                    "telegram_user_id": None,
                    "comment": row["comment"],
                    "created_by_user_id": row["created_by_user_id"],
                    "created_at": row["created_at"],
                }
            )

        return tickets

    def upsert_pool_codes(self, tariff_key: str, codes: list[str]) -> int:
        inserted = 0
        with self._connection() as connection:
            for code in codes:
                cursor = connection.execute(
                    """
                    INSERT OR IGNORE INTO ticket_pool (tariff_key, code)
                    VALUES (?, ?)
                    """,
                    (tariff_key, code),
                )
                inserted += cursor.rowcount
        return inserted

    def reserve_ticket_code(self, *, tariff_key: str, order_id: str) -> str | None:
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                """
                SELECT code FROM ticket_pool
                WHERE tariff_key = ? AND issued_to_order_id IS NULL
                ORDER BY id
                LIMIT 1
                """,
                (tariff_key,),
            ).fetchone()

            if row is None:
                return None

            connection.execute(
                """
                UPDATE ticket_pool
                SET issued_to_order_id = ?, issued_at = CURRENT_TIMESTAMP
                WHERE code = ? AND issued_to_order_id IS NULL
                """,
                (order_id, row["code"]),
            )
            return str(row["code"])

    def _row_to_order(self, row: sqlite3.Row | None) -> Order | None:
        if row is None:
            return None
        data: dict[str, Any] = dict(row)
        return Order(**data)

    def _row_to_free_ticket(self, row: sqlite3.Row | None) -> FreeTicket | None:
        if row is None:
            return None
        data: dict[str, Any] = dict(row)
        return FreeTicket(**data)
