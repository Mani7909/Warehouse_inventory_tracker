# Warehouse Stock & Profit Tracker (Streamlit)

Log purchases (same item at different prices = separate batches), log sales by date and price,
and see profit and remaining stock. Costing is **FIFO**: the oldest stock is sold first.

## Run

```bash
pip install -r requirements.txt
streamlit run app.py
```

Data is stored in `warehouse.db` (SQLite) next to `app.py`. Back up that one file to back up everything.
Set the `WAREHOUSE_DB` environment variable to keep the database somewhere else.

## Pages (sidebar)

**Warehouse** (one page, scroll top to bottom)

| Section | What it does |
|---|---|
| Overview | Stock value, profit this month / all time, low-stock alerts, monthly profit chart |
| Log a purchase / Log a sale | Side by side. The sale form previews the FIFO batches used, cost and profit |
| Stock on hand | Qty and value per item, open batches, Excel download |
| Profit report | Date and item filters, profit by day/week/month and by item, Excel download |
| History | All purchases and sales, with delete for mistakes |

**Add items**: create products, edit their unit, category and reorder level, or remove an item (only if it has no purchases or sales).

## Pre-filled choices

- Unit and category are dropdowns with common values already loaded. Choose "➕ Add new…" to type your own.
- Supplier and customer are dropdowns of the names you have used before (or "➕ Add new…").
- Cost and supplier are pre-filled from your last purchase of that item; selling price from your last sale of it.

## Rules built in

- You cannot sell more than you hold, and you cannot sell stock bought after the sale date.
- FIFO follows the **purchase date**, not the order you typed entries in.
- Each sale stores the exact cost of the batches it used, so later price changes never alter past profit.
- To correct a mistake, delete the sale (stock goes back to the exact batches) or delete an unused purchase.
  A purchase that a sale already used cannot be deleted until that sale is deleted.
- "Your name" in the sidebar is saved with each entry. It is not a login.

## Tests

```bash
python -m unittest discover -s tests -v
```
