"""Inventory operations: purchases, FIFO sales, corrections, stock queries.

All functions take an open sqlite3 connection. Writing functions do NOT commit;
wrap calls in db.transaction() so a failed sale never leaves half-written rows.
"""
from datetime import date as _date

import pandas as pd

EPS = 1e-9


class InventoryError(Exception):
    """A user-correctable problem (bad input, not enough stock, ...)."""


class InsufficientStock(InventoryError):
    def __init__(self, item_name, requested, available, as_of):
        self.requested, self.available = requested, available
        super().__init__(
            f"Not enough stock of '{item_name}' on {as_of}: "
            f"requested {requested:g}, available {available:g}."
        )


def _iso(d):
    if isinstance(d, _date):
        return d.isoformat()
    return str(d)


def _clean(x):
    return round(float(x), 6)


# ---------- items ----------

def add_item(conn, name, unit="pcs", category="", reorder_level=0):
    name = (name or "").strip()
    if not name:
        raise InventoryError("Item name is required.")
    exists = conn.execute("SELECT 1 FROM items WHERE name = ?", (name,)).fetchone()
    if exists:
        raise InventoryError(f"Item '{name}' already exists.")
    cur = conn.execute(
        "INSERT INTO items(name, unit, category, reorder_level) VALUES (?,?,?,?)",
        (name, (unit or "pcs").strip(), (category or "").strip(), float(reorder_level or 0)),
    )
    return cur.lastrowid


def update_item(conn, item_id, unit, category, reorder_level):
    conn.execute(
        "UPDATE items SET unit=?, category=?, reorder_level=? WHERE item_id=?",
        ((unit or "pcs").strip(), (category or "").strip(), float(reorder_level or 0), item_id),
    )


def list_items(conn):
    return pd.read_sql_query("SELECT * FROM items ORDER BY name COLLATE NOCASE", conn)


def get_item(conn, item_id):
    row = conn.execute("SELECT * FROM items WHERE item_id = ?", (item_id,)).fetchone()
    if row is None:
        raise InventoryError("Item not found.")
    return row


# ---------- purchases ----------

def add_purchase(conn, item_id, date, qty, unit_cost, supplier="", invoice_no="", entered_by=""):
    get_item(conn, item_id)
    qty, unit_cost = _clean(qty), _clean(unit_cost)
    if qty <= 0:
        raise InventoryError("Purchase quantity must be greater than zero.")
    if unit_cost < 0:
        raise InventoryError("Unit cost cannot be negative.")
    cur = conn.execute(
        """INSERT INTO purchases(item_id, date, qty, unit_cost, qty_remaining,
                                 supplier, invoice_no, entered_by)
           VALUES (?,?,?,?,?,?,?,?)""",
        (item_id, _iso(date), qty, unit_cost, qty,
         (supplier or "").strip(), (invoice_no or "").strip(), (entered_by or "").strip()),
    )
    return cur.lastrowid


def delete_purchase(conn, purchase_id):
    """Only allowed if no sale has consumed stock from this batch."""
    used = conn.execute(
        "SELECT COUNT(*) FROM sale_allocations WHERE purchase_id = ?", (purchase_id,)
    ).fetchone()[0]
    if used:
        raise InventoryError(
            "This batch has already been used by one or more sales. "
            "Delete those sales first (or leave it as is)."
        )
    conn.execute("DELETE FROM purchases WHERE purchase_id = ?", (purchase_id,))


def batches(conn, item_id=None, only_open=False):
    sql = """SELECT p.purchase_id, i.name AS item, p.date, p.qty, p.qty_remaining,
                    p.unit_cost, p.qty_remaining * p.unit_cost AS value_remaining,
                    p.supplier, p.invoice_no, p.entered_by
             FROM purchases p JOIN items i USING(item_id)
             WHERE 1=1"""
    args = []
    if item_id is not None:
        sql += " AND p.item_id = ?"
        args.append(item_id)
    if only_open:
        sql += f" AND p.qty_remaining > {EPS}"
    sql += " ORDER BY p.date, p.purchase_id"
    return pd.read_sql_query(sql, conn, params=args)


# ---------- stock ----------

def stock_available(conn, item_id, as_of=None):
    """Units that can be sold on `as_of` = open stock in batches bought on/before that date."""
    sql = "SELECT COALESCE(SUM(qty_remaining),0) FROM purchases WHERE item_id = ?"
    args = [item_id]
    if as_of is not None:
        sql += " AND date <= ?"
        args.append(_iso(as_of))
    return _clean(conn.execute(sql, args).fetchone()[0])


def stock_on_hand(conn):
    df = pd.read_sql_query(
        """SELECT i.item_id, i.name AS item, i.category, i.unit, i.reorder_level,
                  COALESCE(SUM(p.qty_remaining),0) AS qty_on_hand,
                  COALESCE(SUM(p.qty_remaining * p.unit_cost),0) AS stock_value
           FROM items i LEFT JOIN purchases p ON p.item_id = i.item_id
           GROUP BY i.item_id ORDER BY i.name COLLATE NOCASE""",
        conn,
    )
    df["qty_on_hand"] = df["qty_on_hand"].round(6)
    df["avg_cost"] = (df["stock_value"] / df["qty_on_hand"].where(df["qty_on_hand"] > EPS)).round(2)
    df["low_stock"] = (df["reorder_level"] > 0) & (df["qty_on_hand"] <= df["reorder_level"])
    return df


# ---------- sales (FIFO) ----------

def _plan_fifo(conn, item_id, date, qty):
    item = get_item(conn, item_id)
    qty = _clean(qty)
    if qty <= 0:
        raise InventoryError("Sale quantity must be greater than zero.")
    rows = conn.execute(
        """SELECT purchase_id, date, qty_remaining, unit_cost FROM purchases
           WHERE item_id = ? AND date <= ? AND qty_remaining > ?
           ORDER BY date, purchase_id""",
        (item_id, _iso(date), EPS),
    ).fetchall()
    available = _clean(sum(r["qty_remaining"] for r in rows))
    if qty > available + EPS:
        raise InsufficientStock(item["name"], qty, available, _iso(date))
    plan, need = [], qty
    for r in rows:
        if need <= EPS:
            break
        take = min(need, r["qty_remaining"])
        plan.append({
            "purchase_id": r["purchase_id"], "batch_date": r["date"],
            "qty_taken": _clean(take), "unit_cost": r["unit_cost"],
        })
        need = _clean(need - take)
    return plan


def preview_sale(conn, item_id, date, qty, sale_price):
    """Return the FIFO plan plus cost/revenue/profit, without writing anything."""
    plan = _plan_fifo(conn, item_id, date, qty)
    cost = sum(p["qty_taken"] * p["unit_cost"] for p in plan)
    revenue = _clean(qty) * float(sale_price)
    return {"plan": plan, "cost": cost, "revenue": revenue, "profit": revenue - cost}


def record_sale(conn, item_id, date, qty, sale_price, customer="", entered_by=""):
    sale_price = float(sale_price)
    if sale_price < 0:
        raise InventoryError("Sale price cannot be negative.")
    info = preview_sale(conn, item_id, date, qty, sale_price)
    cur = conn.execute(
        """INSERT INTO sales(item_id, date, qty, sale_price, customer, entered_by)
           VALUES (?,?,?,?,?,?)""",
        (item_id, _iso(date), _clean(qty), sale_price,
         (customer or "").strip(), (entered_by or "").strip()),
    )
    sale_id = cur.lastrowid
    for p in info["plan"]:
        conn.execute(
            "INSERT INTO sale_allocations(sale_id, purchase_id, qty_taken, unit_cost) VALUES (?,?,?,?)",
            (sale_id, p["purchase_id"], p["qty_taken"], p["unit_cost"]),
        )
        conn.execute(
            "UPDATE purchases SET qty_remaining = ROUND(qty_remaining - ?, 6) WHERE purchase_id = ?",
            (p["qty_taken"], p["purchase_id"]),
        )
    return {"sale_id": sale_id, **info}


def delete_sale(conn, sale_id):
    """Undo a sale: return its quantities to the exact batches they came from."""
    allocs = conn.execute(
        "SELECT purchase_id, qty_taken FROM sale_allocations WHERE sale_id = ?", (sale_id,)
    ).fetchall()
    if not conn.execute("SELECT 1 FROM sales WHERE sale_id = ?", (sale_id,)).fetchone():
        raise InventoryError("Sale not found.")
    for a in allocs:
        conn.execute(
            "UPDATE purchases SET qty_remaining = ROUND(qty_remaining + ?, 6) WHERE purchase_id = ?",
            (a["qty_taken"], a["purchase_id"]),
        )
    conn.execute("DELETE FROM sale_allocations WHERE sale_id = ?", (sale_id,))
    conn.execute("DELETE FROM sales WHERE sale_id = ?", (sale_id,))


# ---------- lookups used to pre-fill the forms ----------

def _distinct(conn, sql):
    return [r[0] for r in conn.execute(sql).fetchall()]


def suppliers(conn):
    return _distinct(conn, "SELECT DISTINCT supplier FROM purchases WHERE supplier <> '' "
                           "ORDER BY supplier COLLATE NOCASE")


def customers(conn):
    return _distinct(conn, "SELECT DISTINCT customer FROM sales WHERE customer <> '' "
                           "ORDER BY customer COLLATE NOCASE")


def categories(conn):
    return _distinct(conn, "SELECT DISTINCT category FROM items WHERE category <> '' "
                           "ORDER BY category COLLATE NOCASE")


def last_purchase(conn, item_id):
    """Most recent purchase of an item (by date) as a Row with unit_cost, supplier; or None."""
    return conn.execute(
        "SELECT unit_cost, supplier FROM purchases WHERE item_id = ? "
        "ORDER BY date DESC, purchase_id DESC LIMIT 1", (item_id,)).fetchone()


def last_sale(conn, item_id):
    """Most recent sale of an item (by date) as a Row with sale_price, customer; or None."""
    return conn.execute(
        "SELECT sale_price, customer FROM sales WHERE item_id = ? "
        "ORDER BY date DESC, sale_id DESC LIMIT 1", (item_id,)).fetchone()
