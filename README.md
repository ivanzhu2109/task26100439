# LicenseForge 席时退款核算库

Python + SQLite 实现的已付款许可证订单部分退款核算库。订单金额均匀分摊到
每个席位的每一使用秒；退款以「席位区间 × 时间区间」的矩形描述，同一
席位同一秒只参与一次退款计算。

## 使用

```python
from licenseforge import LicenseForge

lf = LicenseForge("refunds.db")
lf.create_order("ord-1", purchase_order="PO-100", seats=3, duration=10, paid_cents=7)
amount = lf.refund("ord-1", [(0, 1, 0, 1)])   # [(s0, s1, t0, t1)], 含起点不含终点
report = lf.reconcile("ord-1")                # paid / refunded / outstanding / 逐次记录
lf.close()                                    # 重新打开后历史覆盖与金额保持一致
```

- `refund` 返回本次入账金额（可为 0），并保存带采购单号的对账记录。
- 累计应退 `C = floor(paid_cents * A / (seats * duration))`，其中 `A` 是历次
  所有矩形的并集面积；本次入账恰为 `C_new - C_old`。全程整数运算，不足一
  美分的部分通过累计公式保留后续影响，因此拆分、合批、顺序均不影响结果；
  完整覆盖时恰好退回全部实付。
- 完整退单用覆盖整个订单的矩形 `(0, seats, 0, duration)` 表达。

## 实现与复杂度

- 持久化（`licenseforge/store.py`）：SQLite 三张表 —— 不可变订单、历史
  矩形（含所属退款批次）、逐次退款对账记录。关闭重开后状态完整恢复。
- 并集面积（`licenseforge/geom.py`）：扫描线 + 线段树（坐标压缩），
  统计所有历史矩形的精确并集面积，不逐格展开、不构造边界笛卡尔积网格。
- 核算（`licenseforge/core.py`）：每次 `refund` 将新矩形入库后，对全部
  m 个历史矩形重算并集面积（不要求跨调用增量），再按累计公式取差。
  排序与扫描为 O(m log m)，线段树与事件数组为 O(m) 额外内存；
  m = 2 万时实测约 0.6s、峰值内存约 14 MiB。

## 测试

```bash
python3 -m unittest discover -s tests -v
```

- `tests/test_reference.py`：小坐标空间逐格枚举参考实现，覆盖交叉、嵌套、
  三重重叠、完全重复申请，并随机拆分/合批/重排同一覆盖集合核对每次增量。
- `tests/test_seven_cents.py`：7 美分 / 3 席位 / 10 秒订单，先退一席一秒
  （0 美分入账并留痕），再经重叠区域逐步退完；中途关闭并重开数据库，
  核对零金额记录、最终 7 美分与采购单关联。
- `tests/test_scale.py`：1e9×1e9 坐标下 2 万个横纵条带交叉（1 亿个交叉格），
  用闭式并集面积公式核对金额，并打印耗时与峰值内存。
