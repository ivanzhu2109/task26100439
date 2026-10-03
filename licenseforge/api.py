"""公开 API：create_order / refund / reconcile。

核算规则：
- 订单金额均匀分摊到每个席位的每一使用秒。
- 设历史所有退款矩形的并集面积为 A，则累计应退
  C = floor(paid_cents * A / (seats * duration))，全程整数运算。
- 每次 refund 的入账金额 = 新 C - 旧 C；不足一美分的零头通过
  累计公式保留后续影响，绝不对单个矩形单独取整累加。
"""

from __future__ import annotations

from typing import Dict, List, Tuple

from .geometry import Rect, union_area
from .store import Store


class LicenseForge:
    """席时退款核算入口。调用方保证串行访问。"""

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
        """保存不可修改的原订单。"""
        self._store.create_order(order_id, purchase_order, seats, duration, paid_cents)

    def refund(self, order_id: str, rectangles: List[Tuple[int, int, int, int]]) -> int:
        """申请一批矩形退款，返回本次入账金额（美分，可为零）。"""
        purchase_order, seats, duration, paid_cents = self._store.get_order(order_id)
        rects: List[Rect] = [(int(r[0]), int(r[1]), int(r[2]), int(r[3])) for r in rectangles]

        old_rects = self._store.list_rects(order_id)
        denom = seats * duration
        old_c = paid_cents * union_area(old_rects) // denom
        new_c = paid_cents * union_area(old_rects + rects) // denom
        amount = new_c - old_c

        self._store.add_refund(order_id, purchase_order, amount, rects)
        return amount

    def reconcile(self, order_id: str) -> Dict[str, object]:
        """返回实付、累计退款、未退金额及逐次退款记录。"""
        purchase_order, _, _, paid_cents = self._store.get_order(order_id)
        records = self._store.list_refunds(order_id)
        refunded = sum(amount for _, _, amount in records)
        return {
            "order_id": order_id,
            "purchase_order": purchase_order,
            "paid_cents": paid_cents,
            "refunded_cents": refunded,
            "outstanding_cents": paid_cents - refunded,
            "refunds": [
                {"seq": seq, "purchase_order": po, "amount_cents": amount}
                for seq, po, amount in records
            ],
        }
