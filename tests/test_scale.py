"""Scale test: 20k crossing strips over 1e9 x 1e9 coordinates.

10,000 vertical seat strips [2i, 2i+1) x [0, T) and 10,000 horizontal
time strips [0, S) x [2j, 2j+1) cross in 1e8 intersection cells. The
expected union area has a closed form, so no brute force is needed.
"""

import os
import sys
import tempfile
import time
import tracemalloc
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from licenseforge import LicenseForge

SEATS = 10**9
DURATION = 10**9
N_STRIPS = 10_000  # per orientation, 20k rectangles total
PAID = 10**12


def expected_union_area():
    covered_seats = N_STRIPS  # strips [2i, 2i+1)
    covered_time = N_STRIPS
    return SEATS * DURATION - (SEATS - covered_seats) * (DURATION - covered_time)


class TestScale(unittest.TestCase):
    def test_20k_crossing_strips(self):
        path = os.path.join(tempfile.mkdtemp(), "scale.db")
        lf = LicenseForge(path)
        lf.create_order("big", "PO-BIG", SEATS, DURATION, PAID)

        rects = []
        for i in range(N_STRIPS):
            rects.append((2 * i, 2 * i + 1, 0, DURATION))  # vertical
        for j in range(N_STRIPS):
            rects.append((0, SEATS, 2 * j, 2 * j + 1))  # horizontal
        self.assertEqual(len(rects), 20_000)

        tracemalloc.start()
        t0 = time.perf_counter()
        amount = lf.refund("big", rects)
        elapsed = time.perf_counter() - t0
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        expected = PAID * expected_union_area() // (SEATS * DURATION)
        self.assertEqual(amount, expected)
        print(
            f"\n[scale] 20k strips: {elapsed:.2f}s, "
            f"peak mem {peak / 1e6:.1f} MiB, amount={amount}"
        )
        self.assertLess(elapsed, 30.0, "refund must stay near O(m log m)")

        # A follow-up full-cover rectangle must refund exactly the remainder.
        t0 = time.perf_counter()
        rest = lf.refund("big", [(0, SEATS, 0, DURATION)])
        elapsed2 = time.perf_counter() - t0
        print(f"[scale] full-cover follow-up: {elapsed2:.2f}s, amount={rest}")
        self.assertEqual(amount + rest, PAID)
        self.assertLess(elapsed2, 30.0)

        recon = lf.reconcile("big")
        self.assertEqual(recon["refunded_cents"], PAID)
        self.assertEqual(recon["outstanding_cents"], 0)
        lf.close()


if __name__ == "__main__":
    unittest.main()
