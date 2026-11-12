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

## Layout (single page, scroll top to bottom)

| Section (one page, top to bottom) | What it does |
|---|---|
| Dashboard | Stock value, profit this month / all time, low-stock alerts, monthly profit chart |
| Purchases | Log a purchase (date, qty, cost per unit, supplier, invoice). History + delete mistakes |
| Sales | Log a sale. Live preview shows which batches are used, cost and profit. History + delete |
| Stock on hand | Qty and value per item, open batches, Excel download |
| Profit report | Date and item filters, profit by day/week/month and by item, Excel download |
| Items | Add products, set unit, category and reorder level |

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
