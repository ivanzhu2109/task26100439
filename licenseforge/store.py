"""SQLite 持久化层：订单、历史退款矩形、逐次退款对账记录。"""

from __future__ import annotations

import sqlite3
from typing import List, Tuple

from .geometry import Rect

_SCHEMA = """
CREATE TABLE IF NOT EXISTS orders (
    order_id       TEXT PRIMARY KEY,
    purchase_order TEXT NOT NULL,
    seats          INTEGER NOT NULL,
    duration       INTEGER NOT NULL,
    paid_cents     INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS refund_rects (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id   TEXT NOT NULL,
    refund_seq INTEGER NOT NULL,
    s0 INTEGER NOT NULL, s1 INTEGER NOT NULL,
    t0 INTEGER NOT NULL, t1 INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_rects_order ON refund_rects(order_id);
CREATE TABLE IF NOT EXISTS refunds (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id       TEXT NOT NULL,
    seq            INTEGER NOT NULL,
    purchase_order TEXT NOT NULL,
    amount_cents   INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_refunds_order ON refunds(order_id);
"""


class Store:
    """单个 SQLite 数据库文件的持久化访问。调用方保证串行访问。"""

    def __init__(self, db_path: str) -> None:
        self._conn = sqlite3.connect(db_path)
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def close(self) -> None:
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
                "INSERT INTO orders (order_id, purchase_order, seats, duration, paid_cents)"
                " VALUES (?, ?, ?, ?, ?)",
                (order_id, purchase_order, seats, duration, paid_cents),
            )

    def get_order(self, order_id: str) -> Tuple[str, int, int, int]:
        """返回 (purchase_order, seats, duration, paid_cents)。"""
        row = self._conn.execute(
            "SELECT purchase_order, seats, duration, paid_cents"
            " FROM orders WHERE order_id = ?",
            (order_id,),
        ).fetchone()
        if row is None:
            raise KeyError(f"unknown order_id: {order_id!r}")
        return row[0], int(row[1]), int(row[2]), int(row[3])

    def list_rects(self, order_id: str) -> List[Rect]:
        rows = self._conn.execute(
            "SELECT s0, s1, t0, t1 FROM refund_rects WHERE order_id = ? ORDER BY id",
            (order_id,),
        ).fetchall()
        return [(int(r[0]), int(r[1]), int(r[2]), int(r[3])) for r in rows]

    def add_refund(
        self,
        order_id: str,
        purchase_order: str,
        amount_cents: int,
        rects: List[Rect],
    ) -> None:
        """原子地写入一条退款对账记录及其对应矩形。"""
        with self._conn:
            row = self._conn.execute(
                "SELECT COALESCE(MAX(seq), 0) FROM refunds WHERE order_id = ?",
                (order_id,),
            ).fetchone()
            seq = int(row[0]) + 1
            self._conn.execute(
                "INSERT INTO refunds (order_id, seq, purchase_order, amount_cents)"
                " VALUES (?, ?, ?, ?)",
                (order_id, seq, purchase_order, amount_cents),
            )
            self._conn.executemany(
                "INSERT INTO refund_rects (order_id, refund_seq, s0, s1, t0, t1)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                [(order_id, seq, r[0], r[1], r[2], r[3]) for r in rects],
            )

    def list_refunds(self, order_id: str) -> List[Tuple[int, str, int]]:
        """返回 [(seq, purchase_order, amount_cents), ...] 按时间升序。"""
        rows = self._conn.execute(
            "SELECT seq, purchase_order, amount_cents FROM refunds"
            " WHERE order_id = ? ORDER BY seq",
            (order_id,),
        ).fetchall()
        return [(int(r[0]), r[1], int(r[2])) for r in rows]
