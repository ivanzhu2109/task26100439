"""小坐标空间下，用逐格枚举的独立参考实现交叉验证。

覆盖：交叉、嵌套、三重重叠、完全重复申请；并对同一组矩形随机
拆分、合批、重排，验证累计金额不变且每次增量与参考一致。
"""

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from licenseforge import LicenseForge


class Reference:
    """逐格枚举的参考实现：直接维护被覆盖的 (seat, second) 单元集合。"""

    def __init__(self, seats, duration, paid_cents):
        self.denom = seats * duration
        self.paid = paid_cents
        self.covered = set()
        self.cum = 0

    def refund(self, rects):
        for s0, s1, t0, t1 in rects:
            for s in range(s0, s1):
                for t in range(t0, t1):
                    self.covered.add((s, t))
        new_cum = self.paid * len(self.covered) // self.denom
        delta = new_cum - self.cum
        self.cum = new_cum
        return delta


def run_sequence(db_path, order_id, purchase_order, seats, duration, paid, batches):
    lf = LicenseForge(str(db_path))
    lf.create_order(order_id, purchase_order, seats, duration, paid)
    amounts = [lf.refund(order_id, batch) for batch in batches]
    result = lf.reconcile(order_id)
    lf.close()
    return amounts, result


def check_batches(tmp_path, name, seats, duration, paid, batches):
    """库的结果必须与逐格参考一致（每次增量与累计）。"""
    ref = Reference(seats, duration, paid)
    expected = [ref.refund(batch) for batch in batches]
    amounts, result = run_sequence(
        tmp_path / f"{name}.db", "o", "PO-X", seats, duration, paid, batches
    )
    assert amounts == expected, f"{name}: {amounts} != {expected}"
    assert result["refunded_cents"] == ref.cum
    assert result["paid_cents"] == paid
    assert result["outstanding_cents"] == paid - ref.cum
    assert len(result["refunds"]) == len(batches)
    return result


def test_cross_nested_triple_duplicate(tmp_path):
    seats, duration, paid = 6, 6, 3600
    cases = [
        # 交叉
        [[(0, 4, 0, 2), (2, 6, 1, 3)], [(1, 5, 0, 6)]],
        # 嵌套：先大后小（小矩形完全被覆盖）
        [[(0, 6, 0, 6)], [(1, 3, 1, 3)], [(2, 4, 2, 4)]],
        # 三重重叠
        [[(0, 4, 0, 4)], [(2, 6, 2, 6)], [(1, 5, 1, 5)], [(0, 6, 0, 6)]],
        # 完全重复申请
        [[(1, 4, 1, 4)], [(1, 4, 1, 4)], [(1, 4, 1, 4)]],
        # 逐格退完整个订单
        [[(s, s + 1, t, t + 1)] for s in range(seats) for t in range(duration)],
    ]
    for i, batches in enumerate(cases):
        result = check_batches(tmp_path, f"case{i}", seats, duration, paid, batches)
    # 逐格退完必须恰好退回全部实付
    assert result["refunded_cents"] == paid


def test_random_split_merge_reorder(tmp_path):
    rng = random.Random(20261003)
    seats, duration, paid = 8, 9, 99991  # 质数金额，放大取整差异

    for trial in range(30):
        # 随机生成一组矩形（保证合法）
        rects = []
        for _ in range(rng.randint(1, 12)):
            s0 = rng.randrange(seats)
            s1 = rng.randrange(s0 + 1, seats + 1)
            t0 = rng.randrange(duration)
            t1 = rng.randrange(t0 + 1, duration + 1)
            rects.append((s0, s1, t0, t1))

        # 变体 1：全部合并为一次申请
        # 变体 2：每个矩形单独一次申请
        # 变体 3/4：随机重排 + 随机分批
        variants = [[rects], [[r] for r in rects]]
        for _ in range(2):
            shuffled = rects[:]
            rng.shuffle(shuffled)
            batches = []
            i = 0
            while i < len(shuffled):
                k = rng.randint(1, len(shuffled) - i)
                batches.append(shuffled[i : i + k])
                i += k
            variants.append(batches)

        results = [
            check_batches(tmp_path, f"t{trial}v{v}", seats, duration, paid, batches)
            for v, batches in enumerate(variants)
        ]
        # 相同覆盖集合，无论拆分/合批/顺序，累计退款必须相同
        refunded = {r["refunded_cents"] for r in results}
        assert len(refunded) == 1, f"trial {trial}: {refunded}"
