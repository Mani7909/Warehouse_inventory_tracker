"""SQLite storage for the warehouse app."""
import os
import sqlite3
from contextlib import contextmanager

DB_PATH = os.environ.get(
    "WAREHOUSE_DB", os.path.join(os.path.dirname(os.path.abspath(__file__)), "warehouse.db")
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS items (
    item_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    name           TEXT NOT NULL UNIQUE COLLATE NOCASE,
    unit           TEXT NOT NULL DEFAULT 'pcs',
    category       TEXT NOT NULL DEFAULT '',
    reorder_level  REAL NOT NULL DEFAULT 0,
    created_at     TEXT NOT NULL DEFAULT (datetime('now'))
);

-- One row per purchase batch. qty_remaining drops as FIFO sales consume it.
CREATE TABLE IF NOT EXISTS purchases (
    purchase_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id        INTEGER NOT NULL REFERENCES items(item_id),
    date           TEXT NOT NULL,              -- ISO yyyy-mm-dd
    qty            REAL NOT NULL CHECK (qty > 0),
    unit_cost      REAL NOT NULL CHECK (unit_cost >= 0),
    qty_remaining  REAL NOT NULL CHECK (qty_remaining >= 0),
    supplier       TEXT NOT NULL DEFAULT '',
    invoice_no     TEXT NOT NULL DEFAULT '',
    entered_by     TEXT NOT NULL DEFAULT '',
    created_at     TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS sales (
    sale_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id        INTEGER NOT NULL REFERENCES items(item_id),
    date           TEXT NOT NULL,
    qty            REAL NOT NULL CHECK (qty > 0),
    sale_price     REAL NOT NULL CHECK (sale_price >= 0),   -- per unit
    customer       TEXT NOT NULL DEFAULT '',
    entered_by     TEXT NOT NULL DEFAULT '',
    created_at     TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Which purchase batches each sale consumed, and at what cost (frozen at sale time).
CREATE TABLE IF NOT EXISTS sale_allocations (
    alloc_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    sale_id        INTEGER NOT NULL REFERENCES sales(sale_id) ON DELETE CASCADE,
    purchase_id    INTEGER NOT NULL REFERENCES purchases(purchase_id),
    qty_taken      REAL NOT NULL CHECK (qty_taken > 0),
    unit_cost      REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_purchases_item ON purchases(item_id, date, purchase_id);
CREATE INDEX IF NOT EXISTS idx_sales_item_date ON sales(item_id, date);
CREATE INDEX IF NOT EXISTS idx_alloc_sale ON sale_allocations(sale_id);
CREATE INDEX IF NOT EXISTS idx_alloc_purchase ON sale_allocations(purchase_id);
"""


def get_conn(path=None):
    conn = sqlite3.connect(path or DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def transaction(path=None):
    """Open a connection, commit on success, roll back on any error."""
    conn = get_conn(path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(path=None):
    with transaction(path) as conn:
        conn.executescript(SCHEMA)
