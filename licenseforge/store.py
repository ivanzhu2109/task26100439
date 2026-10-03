"""SQLite persistence layer.

Schema:
  orders     - immutable original orders
  rectangles - every rectangle ever submitted, tagged with its refund seq
  refunds    - one reconciliation row per refund() call
"""

import sqlite3
from typing import List, Tuple

from .geom import Rect

_SCHEMA = """
CREATE TABLE IF NOT EXISTS orders (
    order_id      TEXT PRIMARY KEY,
    purchase_order TEXT NOT NULL,
    seats         INTEGER NOT NULL,
    duration      INTEGER NOT NULL,
    paid_cents    INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS rectangles (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id TEXT NOT NULL REFERENCES orders(order_id),
    refund_seq INTEGER NOT NULL,
    s0 INTEGER NOT NULL, s1 INTEGER NOT NULL,
    t0 INTEGER NOT NULL, t1 INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_rectangles_order ON rectangles(order_id);
CREATE TABLE IF NOT EXISTS refunds (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id    TEXT NOT NULL REFERENCES orders(order_id),
    seq         INTEGER NOT NULL,
    purchase_order TEXT NOT NULL,
    amount_cents INTEGER NOT NULL,
    cumulative_cents INTEGER NOT NULL,
    UNIQUE(order_id, seq)
);
"""


class Store:
    """Owns the SQLite connection and schema for orders, rectangles, refunds."""

    def __init__(self, path: str) -> None:
        self._conn = sqlite3.connect(path)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        self._conn.commit()
        self._conn.close()

    def create_order(
        self,
        order_id: str,
        purchase_order: str,
        seats: int,
        duration: int,
        paid_cents: int,
    ) -> None:
        with self._conn:
            self._conn.execute(
                "INSERT INTO orders(order_id, purchase_order, seats, duration, paid_cents)"
                " VALUES (?, ?, ?, ?, ?)",
                (order_id, purchase_order, seats, duration, paid_cents),
            )

    def get_order(self, order_id: str) -> Tuple[str, int, int, int]:
        """Return (purchase_order, seats, duration, paid_cents)."""
        row = self._conn.execute(
            "SELECT purchase_order, seats, duration, paid_cents FROM orders WHERE order_id = ?",
            (order_id,),
        ).fetchone()
        if row is None:
            raise KeyError(f"unknown order_id: {order_id!r}")
        return row[0], int(row[1]), int(row[2]), int(row[3])

    def next_refund_seq(self, order_id: str) -> int:
        row = self._conn.execute(
            "SELECT COALESCE(MAX(seq), 0) FROM refunds WHERE order_id = ?", (order_id,)
        ).fetchone()
        return int(row[0]) + 1

    def add_rectangles(self, order_id: str, refund_seq: int, rects: List[Rect]) -> None:
        with self._conn:
            self._conn.executemany(
                "INSERT INTO rectangles(order_id, refund_seq, s0, s1, t0, t1)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                [(order_id, refund_seq, s0, s1, t0, t1) for s0, s1, t0, t1 in rects],
            )

    def all_rectangles(self, order_id: str) -> List[Rect]:
        rows = self._conn.execute(
            "SELECT s0, s1, t0, t1 FROM rectangles WHERE order_id = ? ORDER BY id",
            (order_id,),
        ).fetchall()
        return [(int(r[0]), int(r[1]), int(r[2]), int(r[3])) for r in rows]

    def add_refund(
        self,
        order_id: str,
        seq: int,
        purchase_order: str,
        amount_cents: int,
        cumulative_cents: int,
    ) -> None:
        with self._conn:
            self._conn.execute(
                "INSERT INTO refunds(order_id, seq, purchase_order, amount_cents, cumulative_cents)"
                " VALUES (?, ?, ?, ?, ?)",
                (order_id, seq, purchase_order, amount_cents, cumulative_cents),
            )

    def refunds(self, order_id: str) -> List[Tuple[int, str, int, int]]:
        """Return [(seq, purchase_order, amount_cents, cumulative_cents), ...]."""
        rows = self._conn.execute(
            "SELECT seq, purchase_order, amount_cents, cumulative_cents"
            " FROM refunds WHERE order_id = ? ORDER BY seq",
            (order_id,),
        ).fetchall()
        return [(int(r[0]), r[1], int(r[2]), int(r[3])) for r in rows]
