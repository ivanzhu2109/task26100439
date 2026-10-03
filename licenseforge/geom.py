"""Exact rectangle union-area via sweep line + segment tree.

Coordinates are integers up to 1e9; up to ~20k rectangles per order.
Runs in O(m log m) time and O(m) extra memory. No floats anywhere.
"""

from typing import List, Tuple

# A rectangle is (s0, s1, t0, t1): seat range [s0, s1), time range [t0, t1).
Rect = Tuple[int, int, int, int]


class _SegTree:
    """Segment tree over compressed y coordinates tracking covered length."""

    __slots__ = ("ys", "count", "covered")

    def __init__(self, ys: List[int]) -> None:
        self.ys = ys  # sorted unique y boundaries, len n >= 2
        n = len(ys) - 1  # number of elementary intervals
        self.count = [0] * (4 * n)
        self.covered = [0] * (4 * n)

    def _pull(self, node: int, lo: int, hi: int) -> None:
        if self.count[node] > 0:
            self.covered[node] = self.ys[hi + 1] - self.ys[lo]
        elif lo == hi:
            self.covered[node] = 0
        else:
            self.covered[node] = self.covered[2 * node] + self.covered[2 * node + 1]

    def update(self, ql: int, qr: int, delta: int) -> None:
        # Operates on elementary interval indices [ql, qr].
        self._update(1, 0, len(self.ys) - 2, ql, qr, delta)

    def _update(self, node: int, lo: int, hi: int, ql: int, qr: int, delta: int) -> None:
        if qr < lo or ql > hi:
            return
        if ql <= lo and hi <= qr:
            self.count[node] += delta
            self._pull(node, lo, hi)
            return
        mid = (lo + hi) // 2
        self._update(2 * node, lo, mid, ql, qr, delta)
        self._update(2 * node + 1, mid + 1, hi, ql, qr, delta)
        self._pull(node, lo, hi)

    @property
    def total_covered(self) -> int:
        return self.covered[1] if len(self.ys) >= 2 else 0


def union_area(rects: List[Rect]) -> int:
    """Return the exact integer area of the union of axis-aligned rectangles."""
    if not rects:
        return 0
    events = []  # (x, delta, y0, y1)
    ys = set()
    for s0, s1, t0, t1 in rects:
        events.append((s0, 1, t0, t1))
        events.append((s1, -1, t0, t1))
        ys.add(t0)
        ys.add(t1)
    events.sort()
    ylist = sorted(ys)
    yindex = {y: i for i, y in enumerate(ylist)}
    tree = _SegTree(ylist)

    area = 0
    prev_x = events[0][0]
    i = 0
    n = len(events)
    while i < n:
        x = events[i][0]
        area += tree.total_covered * (x - prev_x)
        prev_x = x
        while i < n and events[i][0] == x:
            _, delta, t0, t1 = events[i]
            tree.update(yindex[t0], yindex[t1] - 1, delta)
            i += 1
    return area
