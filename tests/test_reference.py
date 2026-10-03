"""Brute-force reference tests in a small coordinate space."""

import os
import random
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from licenseforge import LicenseForge


def brute_increments(seats, duration, paid, batches):
    """Independent per-cell reference: returns per-request credited amounts."""
    cells = set()
    old_c = 0
    out = []
    for batch in batches:
        for s0, s1, t0, t1 in batch:
            for s in range(s0, s1):
                for t in range(t0, t1):
                    cells.add((s, t))
        new_c = paid * len(cells) // (seats * duration)
        out.append(new_c - old_c)
        old_c = new_c
    return out


def run_library(seats, duration, paid, batches):
    path = os.path.join(tempfile.mkdtemp(), "ref.db")
    lf = LicenseForge(path)
    try:
        lf.create_order("o", "PO-X", seats, duration, paid)
        amounts = [lf.refund("o", b) for b in batches]
        recon = lf.reconcile("o")
    finally:
        lf.close()
    return amounts, recon


def rand_rect(rng, seats, duration):
    s0 = rng.randrange(seats)
    s1 = rng.randrange(s0 + 1, seats + 1)
    t0 = rng.randrange(duration)
    t1 = rng.randrange(t0 + 1, duration + 1)
    return (s0, s1, t0, t1)


class TestStructuredCases(unittest.TestCase):
    def check(self, seats, duration, paid, batches):
        expected = brute_increments(seats, duration, paid, batches)
        amounts, recon = run_library(seats, duration, paid, batches)
        self.assertEqual(amounts, expected)
        self.assertEqual(recon["refunded_cents"], sum(expected))
        self.assertEqual(
            [r["amount_cents"] for r in recon["refunds"]], expected
        )

    def test_crossing(self):
        # two crossing strips
        self.check(6, 6, 360, [[(0, 6, 2, 4)], [(2, 4, 0, 6)]])

    def test_nested(self):
        self.check(8, 8, 640, [[(1, 7, 1, 7)], [(3, 5, 3, 5)], [(2, 6, 2, 6)]])

    def test_triple_overlap(self):
        self.check(
            9,
            9,
            810,
            [[(0, 6, 0, 6)], [(3, 9, 3, 9)], [(2, 8, 1, 8)], [(4, 5, 4, 5)]],
        )

    def test_exact_duplicates(self):
        rect = (1, 4, 2, 5)
        self.check(5, 6, 300, [[rect], [rect], [rect, rect], []])

    def test_fully_covered_request_adds_nothing(self):
        batches = [[(0, 4, 0, 4)], [(1, 3, 1, 3)], [(0, 4, 0, 2), (0, 4, 2, 4)]]
        amounts, _ = run_library(4, 4, 160, batches)
        self.assertEqual(amounts[1], 0)
        self.assertEqual(amounts[2], 0)

    def test_full_cover_refunds_everything(self):
        batches = [(0, 3, 0, 7)]  # single full rect, unbatched below
        amounts, recon = run_library(3, 7, 41, [batches])
        self.assertEqual(amounts, [41])
        self.assertEqual(recon["outstanding_cents"], 0)


class TestRandomizedSplitMergeReorder(unittest.TestCase):
    def test_same_coverage_any_decomposition(self):
        rng = random.Random(20261004)
        for trial in range(60):
            seats = rng.randint(1, 8)
            duration = rng.randint(1, 8)
            paid = rng.randint(0, 5000)
            base = [rand_rect(rng, seats, duration) for _ in range(rng.randint(1, 6))]

            # Build several decompositions of the same coverage:
            # split each rect into unit-width seat slices, shuffle, batch randomly.
            pieces = []
            for s0, s1, t0, t1 in base:
                for s in range(s0, s1):
                    pieces.append((s, s + 1, t0, t1))
            rng.shuffle(pieces)
            batches, cur = [], []
            for p in pieces:
                cur.append(p)
                if rng.random() < 0.4:
                    batches.append(cur)
                    cur = []
            if cur:
                batches.append(cur)
            # also throw the original rects in as extra (duplicate) requests
            batches.append(base)
            rng.shuffle(batches)

            expected = brute_increments(seats, duration, paid, batches)
            amounts, recon = run_library(seats, duration, paid, batches)
            self.assertEqual(amounts, expected, f"trial {trial}")
            # final cumulative depends only on the union coverage
            final_union = brute_increments(seats, duration, paid, [base])
            self.assertEqual(recon["refunded_cents"], sum(final_union))

    def test_random_batches_match_reference(self):
        rng = random.Random(7)
        for trial in range(80):
            seats = rng.randint(1, 7)
            duration = rng.randint(1, 7)
            paid = rng.randint(0, 3000)
            batches = [
                [rand_rect(rng, seats, duration) for _ in range(rng.randint(0, 4))]
                for _ in range(rng.randint(1, 6))
            ]
            expected = brute_increments(seats, duration, paid, batches)
            amounts, recon = run_library(seats, duration, paid, batches)
            self.assertEqual(amounts, expected, f"trial {trial}")
            self.assertEqual(recon["refunded_cents"], sum(expected))
            self.assertEqual(
                recon["outstanding_cents"], paid - sum(expected)
            )


if __name__ == "__main__":
    unittest.main()
