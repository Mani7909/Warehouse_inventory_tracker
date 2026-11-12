import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import db  # noqa: E402
import inventory as inv  # noqa: E402
from choices import merge_choices  # noqa: E402


class LookupTests(unittest.TestCase):
    def setUp(self):
        t = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        t.close()
        self.path = t.name
        db.init_db(self.path)

    def tearDown(self):
        os.unlink(self.path)

    def test_lookups(self):
        with db.transaction(self.path) as c:
            a = inv.add_item(c, "A", "pcs", "Hardware")
            inv.add_item(c, "B", "kg", "")
            inv.add_purchase(c, a, "2026-01-01", 10, 50, supplier="Acme")
            inv.add_purchase(c, a, "2026-02-01", 10, 60, supplier="Zed")
            inv.add_purchase(c, a, "2026-01-15", 10, 55, supplier="acme")
            inv.record_sale(c, a, "2026-03-01", 5, 90, customer="Ravi")
            inv.record_sale(c, a, "2026-03-05", 2, 95, customer="Sita")
        with db.transaction(self.path) as c:
            self.assertEqual(inv.categories(c), ["Hardware"])
            self.assertEqual(inv.suppliers(c), ["Acme", "acme", "Zed"])
            self.assertEqual(inv.customers(c), ["Ravi", "Sita"])
            lp = inv.last_purchase(c, a)
            self.assertEqual((lp["unit_cost"], lp["supplier"]), (60, "Zed"))   # latest by date
            ls = inv.last_sale(c, a)
            self.assertEqual((ls["sale_price"], ls["customer"]), (95, "Sita"))
            self.assertIsNone(inv.last_purchase(c, 2))
            self.assertIsNone(inv.last_sale(c, 2))

    def test_delete_item(self):
        with db.transaction(self.path) as c:
            used = inv.add_item(c, "Used")
            unused = inv.add_item(c, "Unused")
            inv.add_purchase(c, used, "2026-01-01", 5, 10)
        with self.assertRaises(inv.InventoryError):
            with db.transaction(self.path) as c:
                inv.delete_item(c, used)
        with db.transaction(self.path) as c:
            self.assertEqual(inv.item_history_counts(c, used), (1, 0))
            inv.delete_item(c, unused)
            names = list(inv.list_items(c)["name"])
        self.assertEqual(names, ["Used"])
        with self.assertRaises(inv.InventoryError):
            with db.transaction(self.path) as c:
                inv.delete_item(c, unused)    # already gone

    def test_merge_choices(self):
        self.assertEqual(merge_choices(["pcs", "kg"], ["KG", " ", "bag", "pcs"]), ["pcs", "kg", "bag"])


if __name__ == "__main__":
    unittest.main()
