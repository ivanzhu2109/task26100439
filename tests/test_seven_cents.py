"""7 美分、3 席位、10 秒订单：先退一席一秒（零金额），再用重叠区域
逐步退完；中途关闭并重开数据库，核对零金额记录、最终 7 美分以及
所有记录与采购单的关联。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from licenseforge import LicenseForge


def test_seven_cents_gradual_refund_with_reopen(tmp_path):
    db = str(tmp_path / "seven.db")
    lf = LicenseForge(db)
    lf.create_order("ord-7", "PO-2026-0007", 3, 10, 7)

    # 第一步：只退一个席位的一秒。7*1/30 向下取整 = 0，仍须入账零金额记录。
    assert lf.refund("ord-7", [(0, 1, 0, 1)]) == 0
    # 完全重复申请：仍是零，但记录照存。
    assert lf.refund("ord-7", [(0, 1, 0, 1)]) == 0
    lf.close()

    # 中途关闭并重开数据库。
    lf = LicenseForge(db)
    # 与历史重叠的扩张区域：覆盖席位 0 的前 5 秒（含已退的第 0 秒）。
    # 累计覆盖 5 席秒：7*5/30 = 1（向下取整），本次入账 1。
    assert lf.refund("ord-7", [(0, 1, 0, 5)]) == 1
    lf.close()

    lf = LicenseForge(db)
    # 三重重叠地逐步铺满：每次都与旧区域部分重叠。
    # 覆盖席位 0 全部 10 秒 -> 累计 10 席秒，7*10/30 = 2，本次入账 1。
    assert lf.refund("ord-7", [(0, 1, 3, 10)]) == 1
    # 覆盖席位 0-2 的前 8 秒 -> 并集新增席位 1、2 的前 8 秒共 16 席秒，
    # 累计 26 席秒，7*26/30 = 6，本次入账 4。
    assert lf.refund("ord-7", [(0, 3, 0, 8)]) == 4
    # 完整覆盖整个订单 -> 恰好退回全部 7 美分，本次入账 1。
    assert lf.refund("ord-7", [(0, 3, 0, 10)]) == 1
    # 已全覆盖，后续任何申请都是零。
    assert lf.refund("ord-7", [(0, 3, 0, 10)]) == 0
    lf.close()

    # 再次重开，核对对账结果。
    lf = LicenseForge(db)
    result = lf.reconcile("ord-7")
    lf.close()

    assert result["order_id"] == "ord-7"
    assert result["purchase_order"] == "PO-2026-0007"
    assert result["paid_cents"] == 7
    assert result["refunded_cents"] == 7
    assert result["outstanding_cents"] == 0

    amounts = [r["amount_cents"] for r in result["refunds"]]
    assert amounts == [0, 0, 1, 1, 4, 1, 0]
    assert [r["seq"] for r in result["refunds"]] == [1, 2, 3, 4, 5, 6, 7]
    # 每条记录（包括零金额记录）都关联同一采购单号。
    assert all(r["purchase_order"] == "PO-2026-0007" for r in result["refunds"])
    # 零金额记录确实存在。
    assert 0 in amounts
