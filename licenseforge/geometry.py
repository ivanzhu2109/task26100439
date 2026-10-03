"""矩形并集面积计算（扫描线 + 线段树，O(m log m) 时间、O(m) 额外内存）。

矩形为 (s0, s1, t0, t1)，含起点、不含终点；面积单位为"席·秒"。
坐标可以是任意非负整数（可达 1e9），全部使用整数运算，不做逐格展开，
也不构造所有横纵边界的笛卡尔积网格：线段树只建在压缩后的 t 坐标上，
节点数为 O(m)。
"""

from __future__ import annotations

from typing import List, Tuple

Rect = Tuple[int, int, int, int]  # (s0, s1, t0, t1)


def union_area(rects: List[Rect]) -> int:
    """返回矩形并集面积（席·秒）。"""
    if not rects:
        return 0

    # 压缩 t 坐标：基本区间为 [ts[i], ts[i+1])
    ts = sorted({t for r in rects for t in (r[2], r[3])})
    t_index = {t: i for i, t in enumerate(ts)}
    n = len(ts) - 1  # 基本区间个数

    # 线段树数组：cover[node] 为覆盖计数，covered[node] 为该节点被覆盖的 t 长度
    cover = [0] * (4 * n)
    covered = [0] * (4 * n)

    def update(node: int, lo: int, hi: int, ql: int, qr: int, delta: int) -> None:
        if ql <= lo and hi <= qr:
            cover[node] += delta
        else:
            mid = (lo + hi) // 2
            if ql < mid:
                update(node * 2, lo, mid, ql, qr, delta)
            if mid < qr:
                update(node * 2 + 1, mid, hi, ql, qr, delta)
        if cover[node] > 0:
            covered[node] = ts[hi] - ts[lo]
        elif hi - lo == 1:
            covered[node] = 0
        else:
            covered[node] = covered[node * 2] + covered[node * 2 + 1]

    # 扫描事件：到 s0 加入 t 区间，到 s1 移除
    events: List[Tuple[int, int, int, int]] = []
    for s0, s1, t0, t1 in rects:
        events.append((s0, 1, t_index[t0], t_index[t1]))
        events.append((s1, -1, t_index[t0], t_index[t1]))
    events.sort(key=lambda e: e[0])

    area = 0
    prev_s = events[0][0]
    i = 0
    while i < len(events):
        s = events[i][0]
        area += covered[1] * (s - prev_s)
        prev_s = s
        while i < len(events) and events[i][0] == s:
            _, delta, tl, tr = events[i]
            update(1, 0, n, tl, tr, delta)
            i += 1
    return area
