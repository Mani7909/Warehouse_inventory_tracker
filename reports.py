"""Read-only reporting queries (return pandas DataFrames)."""
import pandas as pd


def sales_detail(conn, start=None, end=None, item_id=None):
    """One row per sale with FIFO cost and profit."""
    sql = """
        SELECT s.sale_id, s.date, i.name AS item, i.unit, s.qty, s.sale_price,
               s.qty * s.sale_price AS revenue,
               COALESCE(SUM(a.qty_taken * a.unit_cost), 0) AS cost,
               s.customer, s.entered_by
        FROM sales s
        JOIN items i USING(item_id)
        LEFT JOIN sale_allocations a ON a.sale_id = s.sale_id
        WHERE 1=1"""
    args = []
    if start:
        sql += " AND s.date >= ?"
        args.append(str(start))
    if end:
        sql += " AND s.date <= ?"
        args.append(str(end))
    if item_id is not None:
        sql += " AND s.item_id = ?"
        args.append(item_id)
    sql += " GROUP BY s.sale_id ORDER BY s.date DESC, s.sale_id DESC"
    df = pd.read_sql_query(sql, conn, params=args)
    df["profit"] = df["revenue"] - df["cost"]
    df["margin_pct"] = (df["profit"] / df["revenue"].where(df["revenue"] > 0) * 100).round(1)
    return df


def sale_allocations(conn, sale_id):
    return pd.read_sql_query(
        """SELECT a.purchase_id, p.date AS batch_date, a.qty_taken, a.unit_cost,
                  a.qty_taken * a.unit_cost AS cost
           FROM sale_allocations a JOIN purchases p USING(purchase_id)
           WHERE a.sale_id = ? ORDER BY p.date, a.purchase_id""",
        conn, params=[sale_id],
    )


def summary(df):
    revenue, cost = float(df["revenue"].sum()), float(df["cost"].sum())
    profit = revenue - cost
    return {
        "sales_count": int(len(df)),
        "revenue": revenue,
        "cost": cost,
        "profit": profit,
        "margin_pct": (profit / revenue * 100) if revenue > 0 else 0.0,
    }


def profit_by_item(df):
    if df.empty:
        return pd.DataFrame(columns=["item", "qty_sold", "revenue", "cost", "profit", "margin_pct"])
    g = df.groupby("item", as_index=False).agg(
        qty_sold=("qty", "sum"), revenue=("revenue", "sum"),
        cost=("cost", "sum"), profit=("profit", "sum"),
    )
    g["margin_pct"] = (g["profit"] / g["revenue"].where(g["revenue"] > 0) * 100).round(1)
    return g.sort_values("profit", ascending=False).reset_index(drop=True)


def profit_by_period(df, freq="M"):
    """freq: 'D' day, 'W' week, 'M' month."""
    if df.empty:
        return pd.DataFrame(columns=["period", "revenue", "cost", "profit"])
    d = df.copy()
    d["date"] = pd.to_datetime(d["date"])
    if freq == "D":
        d["period"] = d["date"].dt.strftime("%Y-%m-%d")
    elif freq == "W":
        d["period"] = d["date"].dt.to_period("W-SUN").apply(lambda p: p.start_time.strftime("%Y-%m-%d"))
    else:
        d["period"] = d["date"].dt.strftime("%Y-%m")
    g = d.groupby("period", as_index=False)[["revenue", "cost", "profit"]].sum()
    return g.sort_values("period").reset_index(drop=True)
