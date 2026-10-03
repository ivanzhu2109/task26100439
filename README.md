# LicenseForge 席时退款核算库

用 Python + SQLite 实现的部分退款核算库：对已付款许可证订单按
"席位 × 使用秒"矩形区域做部分退款与采购单对账。

## 用法

```python
from licenseforge import LicenseForge

lf = LicenseForge("refunds.db")          # SQLite 文件路径
lf.create_order("ord-1", "PO-001", seats=3, duration=10, paid_cents=7)

amount = lf.refund("ord-1", [(0, 1, 0, 1)])   # 矩形为 (s0, s1, t0, t1)，含起点不含终点
report = lf.reconcile("ord-1")
# report: paid_cents / refunded_cents / outstanding_cents / refunds（逐次记录，含采购单号）
lf.close()                                # 也支持 with 语句
```

## 核算规则

- 订单金额均匀分摊到每个席位的每一使用秒。
- 设历史所有退款矩形的并集面积为 `A`，累计应退
  `C = floor(paid_cents * A / (seats * duration))`，全程整数运算。
- 每次 `refund` 的入账金额 = 新 `C` − 旧 `C`；不足一美分的零头通过
  累计公式保留后续影响，从不对单个矩形单独取整累加。
- 同一席位的同一秒无论被多少次申请覆盖只计一次；完整覆盖订单时
  `A = seats × duration`，恰好退回全部实付金额。
- 完整退单用覆盖整个订单的矩形表达，没有绕过覆盖核算的路径。

## 实现与复杂度

`licenseforge/geometry.py` 用扫描线求矩形并集面积：按席位坐标排序
2m 个事件，用覆盖计数线段树维护使用秒方向上的被覆盖总长度。线段树
建在压缩后的坐标上，节点数 O(m)，因此：

- 单次 `refund` 时间复杂度 O(m log m)（m 为历史及本次矩形总数），
  额外内存 O(m)；每次调用基于 SQLite 中的历史矩形全量重算，
  不依赖跨调用增量状态，天然满足持久化一致性。
- 不逐席位、逐秒展开，也不构造所有横纵边界的笛卡尔积网格；
  seats、duration 可达 1e9，paid_cents 可达 1e12，全部使用整数。

SQLite 中保存：不可修改的原订单、每次退款的全部矩形、逐次退款对账
记录（含采购单号与金额，允许零金额）。关闭并重开数据库后历史覆盖
范围、累计金额与对账记录完全一致。

## 运行测试

```bash
python3 -m pytest tests/ -q -s
```

- `tests/test_reference.py`：小坐标空间逐格枚举的独立参考实现，
  验证交叉、嵌套、三重重叠、重复申请，并对同一组矩形随机拆分、
  合批、重排，检查累计金额与每次增量。
- `tests/test_seven_cents.py`：7 美分 / 3 席 / 10 秒订单，先退一席
  一秒（零金额记录），再用重叠区域逐步退完；中途关闭并重开数据库，
  核对零金额记录、最终 7 美分及采购单关联。
- `tests/test_scale.py`：1e9 × 1e9 坐标下 2 万个横纵交叉条带，
  用独立公式核对并集面积与金额，并打印耗时与峰值内存
  （本机约 0.5s / 8MiB）。
