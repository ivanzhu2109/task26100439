"""Public LicenseForge API.

Accounting rule: let A be the union area of every rectangle ever submitted
for an order. The cumulative refundable amount is

    C = floor(paid_cents * A / (seats * duration))

computed with exact integer arithmetic. Each refund() call credits exactly
C_new - C_old, so sub-cent fractions keep their effect on later calls and
the result is independent of how coverage is split, batched or ordered.
"""

from typing import Dict, List

from .geom import Rect, union_area
from .store import Store


class LicenseForge:
    """Seat-time partial refund accounting backed by SQLite."""

    def __init__(self, db_path: str) -> None:
        self._store = Store(db_path)

    def close(self) -> None:
        self._store.close()

    def __enter__(self) -> "LicenseForge":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def create_order(
        self,
        order_id: str,
        purchase_order: str,
        seats: int,
        duration: int,
        paid_cents: int,
    ) -> None:
        self._store.create_order(order_id, purchase_order, seats, duration, paid_cents)

    def refund(self, order_id: str, rectangles: List[Rect]) -> int:
        """Apply one refund request; return the amount credited this call."""
        purchase_order, seats, duration, paid_cents = self._store.get_order(order_id)
        rects = [tuple(map(int, r)) for r in rectangles]

        seq = self._store.next_refund_seq(order_id)
        if rects:
            self._store.add_rectangles(order_id, seq, rects)

        history = self._store.all_rectangles(order_id)
        area = union_area(history)
        cumulative = paid_cents * area // (seats * duration)

        prior = self._store.refunds(order_id)
        old_cumulative = prior[-1][3] if prior else 0
        amount = cumulative - old_cumulative

        self._store.add_refund(order_id, seq, purchase_order, amount, cumulative)
        return amount

    def reconcile(self, order_id: str) -> Dict[str, object]:
        """Return paid, refunded, outstanding and per-refund records."""
        _, _, _, paid_cents = self._store.get_order(order_id)
        records = [
            {
                "seq": seq,
                "purchase_order": po,
                "amount_cents": amount,
                "cumulative_cents": cumulative,
            }
            for seq, po, amount, cumulative in self._store.refunds(order_id)
        ]
        refunded = records[-1]["cumulative_cents"] if records else 0
        return {
            "order_id": order_id,
            "paid_cents": paid_cents,
            "refunded_cents": refunded,
            "outstanding_cents": paid_cents - refunded,
            "refunds": records,
        }
