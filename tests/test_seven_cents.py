"""7-cent order: refund one seat-second, then finish via overlapping requests,
closing and reopening the database in the middle."""

import os
import tempfile
import unittest

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from licenseforge import LicenseForge


class TestSevenCents(unittest.TestCase):
    def test_gradual_overlapping_refund_with_reopen(self):
        path = os.path.join(tempfile.mkdtemp(), "seven.db")

        lf = LicenseForge(path)
        lf.create_order("ord-7", "PO-777", seats=3, duration=10, paid_cents=7)

        # Step 1: a single seat-second -> floor(7 * 1 / 30) = 0 cents.
        self.assertEqual(lf.refund("ord-7", [(0, 1, 0, 1)]), 0)
        # Step 2: same cell again -> still 0, and recorded as a zero record.
        self.assertEqual(lf.refund("ord-7", [(0, 1, 0, 1)]), 0)
        lf.close()

        # Reopen: history must survive.
        lf = LicenseForge(path)
        recon = lf.reconcile("ord-7")
        self.assertEqual(recon["refunded_cents"], 0)
        self.assertEqual(len(recon["refunds"]), 2)

        # Step 3: overlapping growth. Cover seat 0 fully plus the old cell
        # of seat 1: union area = 10 + 1 = 11 -> floor(7*11/30) = 2.
        self.assertEqual(lf.refund("ord-7", [(0, 2, 0, 1), (0, 1, 0, 10)]), 2)
        # Step 4: redundant request inside covered area -> 0.
        self.assertEqual(lf.refund("ord-7", [(0, 1, 3, 6)]), 0)
        lf.close()

        lf = LicenseForge(path)
        # Step 5: finish the whole order with one overlapping rectangle.
        # Union becomes 30 -> floor(7*30/30) = 7; this call credits 7 - 2 = 5.
        self.assertEqual(lf.refund("ord-7", [(0, 3, 0, 10)]), 5)
        # Step 6: everything already covered -> 0.
        self.assertEqual(lf.refund("ord-7", [(1, 2, 2, 8)]), 0)
        lf.close()

        # Final reconciliation from a fresh connection.
        lf = LicenseForge(path)
        recon = lf.reconcile("ord-7")
        lf.close()

        self.assertEqual(recon["paid_cents"], 7)
        self.assertEqual(recon["refunded_cents"], 7)
        self.assertEqual(recon["outstanding_cents"], 0)

        amounts = [r["amount_cents"] for r in recon["refunds"]]
        self.assertEqual(amounts, [0, 0, 2, 0, 5, 0])
        cumul = [r["cumulative_cents"] for r in recon["refunds"]]
        self.assertEqual(cumul, [0, 0, 2, 2, 7, 7])
        # zero-amount records exist and every record links the purchase order
        self.assertTrue(any(a == 0 for a in amounts))
        self.assertTrue(
            all(r["purchase_order"] == "PO-777" for r in recon["refunds"])
        )
        self.assertEqual([r["seq"] for r in recon["refunds"]], [1, 2, 3, 4, 5, 6])


if __name__ == "__main__":
    unittest.main()
