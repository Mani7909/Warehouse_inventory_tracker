import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import db  # noqa: E402
import inventory as inv  # noqa: E402
import reports  # noqa: E402


class FifoTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        self.path = self.tmp.name
        db.init_db(self.path)
        with db.transaction(self.path) as c:
            self.a = inv.add_item(c, "Item A", "pcs", "x", 10)
            self.b = inv.add_item(c, "Item B", "kg")

    def tearDown(self):
        os.unlink(self.path)

    def _buy(self, item, date, qty, cost):
        with db.transaction(self.path) as c:
            return inv.add_purchase(c, item, date, qty, cost)

    def _sell(self, item, date, qty, price):
        with db.transaction(self.path) as c:
            return inv.record_sale(c, item, date, qty, price)

    def test_example_from_analysis(self):
        # 100 @50, 100 @60, sell 120 @80 -> cost 6200, profit 3400
        self._buy(self.a, "2026-01-01", 100, 50)
        self._buy(self.a, "2026-02-01", 100, 60)
        r = self._sell(self.a, "2026-03-01", 120, 80)
        self.assertAlmostEqual(r["cost"], 6200)
        self.assertAlmostEqual(r["revenue"], 9600)
        self.assertAlmostEqual(r["profit"], 3400)
        with db.transaction(self.path) as c:
            b = inv.batches(c, self.a)
            self.assertEqual(list(b["qty_remaining"]), [0, 80])
            self.assertAlmostEqual(inv.stock_on_hand(c).set_index("item").loc["Item A", "stock_value"], 4800)

    def test_fifo_follows_purchase_date_not_entry_order(self):
        self._buy(self.a, "2026-02-01", 10, 60)   # entered first, bought later
        self._buy(self.a, "2026-01-01", 10, 50)   # entered second, bought earlier
        r = self._sell(self.a, "2026-03-01", 10, 100)
        self.assertAlmostEqual(r["cost"], 500)

    def test_oversell_blocked_and_nothing_written(self):
        self._buy(self.a, "2026-01-01", 5, 10)
        with self.assertRaises(inv.InsufficientStock):
            self._sell(self.a, "2026-01-02", 6, 20)
        with db.transaction(self.path) as c:
            self.assertEqual(c.execute("SELECT COUNT(*) FROM sales").fetchone()[0], 0)
            self.assertEqual(inv.stock_available(c, self.a), 5)

    def test_cannot_sell_stock_bought_after_sale_date(self):
        self._buy(self.a, "2026-05-01", 5, 10)
        with self.assertRaises(inv.InsufficientStock):
            self._sell(self.a, "2026-04-01", 1, 20)

    def test_delete_sale_restores_exact_batches(self):
        self._buy(self.a, "2026-01-01", 10, 50)
        self._buy(self.a, "2026-02-01", 10, 60)
        r = self._sell(self.a, "2026-03-01", 15, 80)
        with db.transaction(self.path) as c:
            inv.delete_sale(c, r["sale_id"])
        with db.transaction(self.path) as c:
            self.assertEqual(list(inv.batches(c, self.a)["qty_remaining"]), [10, 10])
            self.assertEqual(c.execute("SELECT COUNT(*) FROM sale_allocations").fetchone()[0], 0)

    def test_cannot_delete_used_purchase(self):
        pid = self._buy(self.a, "2026-01-01", 10, 50)
        self._sell(self.a, "2026-01-02", 1, 80)
        with self.assertRaises(inv.InventoryError):
            with db.transaction(self.path) as c:
                inv.delete_purchase(c, pid)
        unused = self._buy(self.a, "2026-01-03", 5, 55)
        with db.transaction(self.path) as c:
            inv.delete_purchase(c, unused)

    def test_cost_frozen_after_sale(self):
        self._buy(self.a, "2026-01-01", 10, 50)
        r = self._sell(self.a, "2026-01-02", 4, 80)
        self._buy(self.a, "2026-01-03", 10, 999)  # later price change must not affect old profit
        with db.transaction(self.path) as c:
            df = reports.sales_detail(c)
        self.assertAlmostEqual(df.loc[df.sale_id == r["sale_id"], "profit"].iloc[0], 4 * 30)

    def test_fractional_quantities(self):
        self._buy(self.b, "2026-01-01", 2.5, 100)
        r = self._sell(self.b, "2026-01-02", 1.25, 150)
        self.assertAlmostEqual(r["profit"], 1.25 * 50)
        with db.transaction(self.path) as c:
            self.assertAlmostEqual(inv.stock_available(c, self.b), 1.25)

    def test_duplicate_item_name_rejected_case_insensitive(self):
        with self.assertRaises(inv.InventoryError):
            with db.transaction(self.path) as c:
                inv.add_item(c, "item a")

    def test_reports_and_low_stock(self):
        self._buy(self.a, "2026-01-01", 20, 10)
        self._buy(self.b, "2026-01-01", 10, 20)
        self._sell(self.a, "2026-01-10", 15, 15)   # leaves 5 <= reorder 10 -> low
        self._sell(self.b, "2026-02-10", 4, 30)
        with db.transaction(self.path) as c:
            soh = inv.stock_on_hand(c).set_index("item")
            self.assertTrue(bool(soh.loc["Item A", "low_stock"]))
            self.assertFalse(bool(soh.loc["Item B", "low_stock"]))
            df = reports.sales_detail(c)
            s = reports.summary(df)
            self.assertAlmostEqual(s["revenue"], 15 * 15 + 4 * 30)
            self.assertAlmostEqual(s["cost"], 15 * 10 + 4 * 20)
            self.assertAlmostEqual(s["profit"], 75 + 40)
            by_item = reports.profit_by_item(df).set_index("item")
            self.assertAlmostEqual(by_item.loc["Item A", "profit"], 75)
            months = reports.profit_by_period(df, "M")
            self.assertEqual(list(months["period"]), ["2026-01", "2026-02"])
            self.assertEqual(len(reports.profit_by_period(df, "W")), 2)
            filtered = reports.sales_detail(c, start="2026-02-01", end="2026-02-28")
            self.assertEqual(len(filtered), 1)

    def test_empty_reports(self):
        with db.transaction(self.path) as c:
            df = reports.sales_detail(c)
            self.assertEqual(reports.summary(df)["profit"], 0)
            self.assertTrue(reports.profit_by_item(df).empty)
            self.assertTrue(reports.profit_by_period(df).empty)


if __name__ == "__main__":
    unittest.main()
