"""规模测试：大坐标、2 万个横纵条带形成大量交叉。

- seats = duration = 1e9，paid_cents = 1e12（约束上限）。
- 1 万条竖条带（1 席宽、贯穿整个使用期）与 1 万条横条带
  （1 秒高、贯穿全部席位）互相交叉，绝非互不相交。
- 预期并集面积用独立公式计算：Wv*D + S*Wh - Wv*Wh。
- 记录耗时与峰值内存（tracemalloc）。
"""

import sys
import time
import tracemalloc
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from licenseforge import LicenseForge

SEATS = 10**9
DURATION = 10**9
PAID = 10**12
N_STRIPS = 10_000  # 横、竖各 1 万条，共 2 万个矩形
STRIDE = 1000  # 条带间隔，保证同向条带互不相交


def build_rects():
    rects = []
    for i in range(N_STRIPS):
        s0 = i * STRIDE
        rects.append((s0, s0 + 1, 0, DURATION))  # 竖条带
    for i in range(N_STRIPS):
        t0 = i * STRIDE
        rects.append((0, SEATS, t0, t0 + 1))  # 横条带
    return rects


def expected_union_area():
    wv = N_STRIPS * 1  # 竖条带总宽（席）
    wh = N_STRIPS * 1  # 横条带总高（秒）
    return wv * DURATION + SEATS * wh - wv * wh


def test_twenty_thousand_crossing_strips(tmp_path):
    rects = build_rects()
    assert len(rects) == 2 * N_STRIPS

    lf = LicenseForge(str(tmp_path / "scale.db"))
    lf.create_order("big", "PO-BIG", SEATS, DURATION, PAID)

    tracemalloc.start()
    start = time.perf_counter()
    amount = lf.refund("big", rects)
    elapsed = time.perf_counter() - start
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    expected_area = expected_union_area()
    expected_cents = PAID * expected_area // (SEATS * DURATION)
    assert amount == expected_cents

    result = lf.reconcile("big")
    assert result["refunded_cents"] == expected_cents
    lf.close()

    print(
        f"\n2 万交叉条带：并集面积={expected_area} 席秒，"
        f"退款={expected_cents} 美分，"
        f"耗时={elapsed:.2f}s，峰值内存={peak / 1024 / 1024:.1f}MiB"
    )
    # 宽松的健康检查：确认没有退化成逐格/网格级别。
    assert elapsed < 60
    assert peak < 1024**3  # 1 GiB
