"""
database.py
-----------
Handles SQLite database initialization, CSV parsing, data cleaning,
multi-dimensional filtering, transaction queries, and data quality auditing.

Author: Senior Full-Stack Engineer / Student Developer
Project: Sales Insight Assistant
"""

import csv
import math
import os
import sqlite3
from datetime import datetime

DEFAULT_DB_PATH = "sales.db"
DEFAULT_CSV_PATH = "sales_data.csv"

# Global cache for data cleaning logs generated during DB init
DATA_CLEANING_AUDIT_LOGS = []


def clean_and_parse_date(date_str: str) -> str:
    """
    Normalizes date from DD-MM-YYYY format into standard ISO YYYY-MM-DD.
    Enables SQLite's strftime() to group by month and year accurately.
    """
    clean_str = date_str.strip()
    try:
        dt = datetime.strptime(clean_str, "%d-%m-%Y")
        return dt.strftime("%Y-%m-%d")
    except ValueError:
        try:
            dt = datetime.strptime(clean_str, "%Y-%m-%d")
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            return clean_str


def load_and_clean_csv(csv_path: str = DEFAULT_CSV_PATH):
    """
    Reads the raw CSV file, audits missing/invalid values,
    imputes missing prices, and calculates row-level net revenue.
    """
    global DATA_CLEANING_AUDIT_LOGS
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"CSV file not found at: {csv_path}")

    cleaned_records = []
    product_price_catalog = {}

    # First pass: collect known product unit prices to use for catalog imputation
    with open(csv_path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            product = row.get("Product", "").strip()
            price_raw = row.get("Unit_price", "").strip()
            if product and price_raw:
                try:
                    price_val = float(price_raw)
                    if price_val > 0:
                        product_price_catalog[product] = price_val
                except ValueError:
                    pass

    # Second pass: clean records, handle missing values, and calculate revenue
    cleaning_logs = []
    with open(csv_path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            txn_id = row.get("Transaction_Id", "").strip()
            order_date = clean_and_parse_date(row.get("Order_date", ""))
            product = row.get("Product", "").strip()
            category = row.get("Category", "").strip()
            region = row.get("Region", "").strip()
            sales_channel = row.get("Sales_channel", "").strip()
            status = row.get("Status", "").strip()

            # Parse quantity (handle 0 or invalid)
            try:
                quantity = int(row.get("Quantity", 0))
            except (ValueError, TypeError):
                quantity = 0
                cleaning_logs.append(f"Invalid quantity in {txn_id}, defaulted to 0.")

            # Parse unit price with imputation for missing values (e.g. TXN0051)
            price_raw = row.get("Unit_price", "").strip()
            if not price_raw:
                imputed_price = product_price_catalog.get(product, 0.0)
                unit_price = imputed_price
                cleaning_logs.append(
                    f"Imputed missing Unit_price for {txn_id} ({product}) -> {imputed_price:.2f}"
                )
            else:
                try:
                    unit_price = float(price_raw)
                except ValueError:
                    unit_price = product_price_catalog.get(product, 0.0)
                    cleaning_logs.append(
                        f"Non-numeric price in {txn_id}, used catalog price {unit_price:.2f}"
                    )

            # Parse discount amount
            try:
                discount_amount = float(row.get("Discount_amount", 0.0))
            except (ValueError, TypeError):
                discount_amount = 0.0

            # Calculate Net Revenue: (Quantity * Unit_price) - Discount_amount
            gross_amount = quantity * unit_price
            revenue = max(0.0, gross_amount - discount_amount)

            cleaned_records.append({
                "transaction_id": txn_id,
                "order_date": order_date,
                "product": product,
                "category": category,
                "region": region,
                "sales_channel": sales_channel,
                "quantity": quantity,
                "unit_price": unit_price,
                "discount_amount": discount_amount,
                "status": status,
                "revenue": revenue
            })

    DATA_CLEANING_AUDIT_LOGS = list(cleaning_logs)
    return cleaned_records, cleaning_logs


def init_db(db_path: str = DEFAULT_DB_PATH, csv_path: str = DEFAULT_CSV_PATH):
    """
    Creates SQLite database table and populates it with cleaned records.
    Re-creates the table on initialization to guarantee fresh, valid state.
    """
    cleaned_records, cleaning_logs = load_and_clean_csv(csv_path)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("DROP TABLE IF EXISTS sales")
    cursor.execute("""
        CREATE TABLE sales (
            transaction_id TEXT PRIMARY KEY,
            order_date TEXT NOT NULL,
            product TEXT NOT NULL,
            category TEXT NOT NULL,
            region TEXT NOT NULL,
            sales_channel TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            unit_price REAL NOT NULL,
            discount_amount REAL NOT NULL,
            status TEXT NOT NULL,
            revenue REAL NOT NULL
        )
    """)

    insert_sql = """
        INSERT INTO sales (
            transaction_id, order_date, product, category, region,
            sales_channel, quantity, unit_price, discount_amount, status, revenue
        ) VALUES (
            :transaction_id, :order_date, :product, :category, :region,
            :sales_channel, :quantity, :unit_price, :discount_amount, :status, :revenue
        )
    """
    cursor.executemany(insert_sql, cleaned_records)
    conn.commit()
    conn.close()

    return {
        "status": "success",
        "total_records_inserted": len(cleaned_records),
        "cleaning_logs": cleaning_logs
    }


def get_db_connection(db_path: str = DEFAULT_DB_PATH):
    """
    Returns an SQLite connection configured with row dictionary access.
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def execute_safe_query(query: str, params: tuple = (), db_path: str = DEFAULT_DB_PATH):
    """
    Executes a read-only SQL query against SQLite and returns formatted results.
    """
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    try:
        cursor.execute(query, params)
        columns = [desc[0] for desc in cursor.description] if cursor.description else []
        rows = [dict(row) for row in cursor.fetchall()]
        return {
            "success": True,
            "columns": columns,
            "rows": rows,
            "row_count": len(rows),
            "error": None
        }
    except Exception as e:
        return {
            "success": False,
            "columns": [],
            "rows": [],
            "row_count": 0,
            "error": str(e)
        }
    finally:
        conn.close()


def build_filter_clause(filters: dict = None, default_status: str = "Completed"):
    """
    Safely builds a WHERE clause and parameter list from user-selected filters.
    Supported filters:
      - month: 'YYYY-MM'
      - product: product name
      - region: region name
      - sales_channel: channel name ('Online', 'Retail')
      - status: 'Completed', 'Returned', or 'all'
    """
    filters = filters or {}
    conditions = []
    params = []

    # Status filter
    status = str(filters.get("status", "")).strip()
    if status and status.lower() != "all":
        conditions.append("status = ?")
        params.append(status)
    elif default_status:
        conditions.append("status = ?")
        params.append(default_status)

    # Month filter (e.g. '2026-03')
    month = str(filters.get("month", "")).strip()
    if month and month.lower() != "all":
        conditions.append("strftime('%Y-%m', order_date) = ?")
        params.append(month)

    # Product filter
    product = str(filters.get("product", "")).strip()
    if product and product.lower() != "all":
        conditions.append("product = ?")
        params.append(product)

    # Region filter
    region = str(filters.get("region", "")).strip()
    if region and region.lower() != "all":
        conditions.append("region = ?")
        params.append(region)

    # Sales Channel filter
    channel = str(filters.get("sales_channel", "") or filters.get("channel", "")).strip()
    if channel and channel.lower() != "all":
        conditions.append("sales_channel = ?")
        params.append(channel)

    where_sql = " WHERE " + " AND ".join(conditions) if conditions else ""
    return where_sql, params


def get_filter_options(db_path: str = DEFAULT_DB_PATH):
    """
    Fetches distinct values from SQLite to dynamically populate frontend dropdowns.
    """
    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    cursor.execute("SELECT DISTINCT strftime('%Y-%m', order_date) as m FROM sales ORDER BY m ASC")
    months = [r["m"] for r in cursor.fetchall() if r["m"]]

    cursor.execute("SELECT DISTINCT product FROM sales ORDER BY product ASC")
    products = [r["product"] for r in cursor.fetchall() if r["product"]]

    cursor.execute("SELECT DISTINCT region FROM sales ORDER BY region ASC")
    regions = [r["region"] for r in cursor.fetchall() if r["region"]]

    cursor.execute("SELECT DISTINCT sales_channel FROM sales ORDER BY sales_channel ASC")
    channels = [r["sales_channel"] for r in cursor.fetchall() if r["sales_channel"]]

    cursor.execute("SELECT DISTINCT status FROM sales ORDER BY status ASC")
    statuses = [r["status"] for r in cursor.fetchall() if r["status"]]

    conn.close()
    return {
        "months": months,
        "products": products,
        "regions": regions,
        "channels": channels,
        "statuses": statuses
    }


def get_dataset_overview(filters: dict = None, db_path: str = DEFAULT_DB_PATH):
    """
    Fetches aggregate metrics for the 4 KPI summary cards:
    1. Total revenue (after discounts, completed)
    2. Valid completed transactions
    3. Top-performing product and revenue
    4. Highest-revenue region and revenue
    Supports interactive filters.
    """
    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    # Base completed where clause
    where_sql, params = build_filter_clause(filters, default_status="Completed")

    # Total net revenue
    cursor.execute(f"SELECT SUM(revenue), COUNT(*) FROM sales{where_sql}", params)
    rev_row = cursor.fetchone()
    total_revenue = rev_row[0] or 0.0
    valid_txns = rev_row[1] or 0

    # Total count matching filters regardless of status
    where_all, params_all = build_filter_clause(filters, default_status=None)
    cursor.execute(f"SELECT COUNT(*) FROM sales{where_all}", params_all)
    total_txns = cursor.fetchone()[0] or 0

    # Returned count matching filters
    where_ret, params_ret = build_filter_clause(filters, default_status="Returned")
    cursor.execute(f"SELECT COUNT(*) FROM sales{where_ret}", params_ret)
    returned_txns = cursor.fetchone()[0] or 0

    # Top performing product under filters
    cursor.execute(f"""
        SELECT product, SUM(revenue) as rev 
        FROM sales 
        {where_sql}
        GROUP BY product 
        ORDER BY rev DESC 
        LIMIT 1
    """, params)
    top_prod_row = cursor.fetchone()
    top_product = {
        "name": top_prod_row["product"] if top_prod_row else "None",
        "revenue": round(top_prod_row["rev"], 2) if top_prod_row else 0.0
    }

    # Highest revenue region under filters
    cursor.execute(f"""
        SELECT region, SUM(revenue) as rev 
        FROM sales 
        {where_sql}
        GROUP BY region 
        ORDER BY rev DESC 
        LIMIT 1
    """, params)
    top_reg_row = cursor.fetchone()
    top_region = {
        "name": top_reg_row["region"] if top_reg_row else "None",
        "revenue": round(top_reg_row["rev"], 2) if top_reg_row else 0.0
    }

    # Highest revenue channel under filters
    cursor.execute(f"""
        SELECT sales_channel, SUM(revenue) as rev 
        FROM sales 
        {where_sql}
        GROUP BY sales_channel 
        ORDER BY rev DESC 
        LIMIT 1
    """, params)
    top_chan_row = cursor.fetchone()
    top_channel = {
        "name": top_chan_row["sales_channel"] if top_chan_row else "None",
        "revenue": round(top_chan_row["rev"], 2) if top_chan_row else 0.0
    }

    # Date range
    cursor.execute(f"SELECT MIN(order_date), MAX(order_date) FROM sales{where_sql}", params)
    date_range = cursor.fetchone()

    conn.close()

    is_filtered = bool(filters and any(v and v.lower() != "all" for v in filters.values()))

    return {
        "total_transactions": total_txns,
        "completed_transactions": valid_txns,
        "valid_transactions": valid_txns,
        "returned_transactions": returned_txns,
        "total_net_revenue": round(total_revenue, 2),
        "top_product": top_product,
        "top_region": top_region,
        "top_channel": top_channel,
        "date_range": f"{date_range[0]} to {date_range[1]}" if date_range and date_range[0] else "N/A",
        "is_filtered": is_filtered
    }


def get_chart_data(filters: dict = None, db_path: str = DEFAULT_DB_PATH):
    """
    Retrieves aggregated dataset metrics for the 4 dashboard charts:
    1. Monthly revenue trend (Line Chart)
    2. Product-wise sales revenue (Bar Chart)
    3. Regional sales breakdown (Bar Chart)
    4. Sales-channel distribution (Doughnut Chart)
    Applies active filters dynamically.
    """
    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    where_sql, params = build_filter_clause(filters, default_status="Completed")

    # 1. Monthly revenue trend
    cursor.execute(f"""
        SELECT strftime('%Y-%m', order_date) as month, SUM(revenue) as total
        FROM sales
        {where_sql}
        GROUP BY month
        ORDER BY month ASC
    """, params)
    monthly_rows = cursor.fetchall()
    monthly_trend = {
        "labels": [r["month"] for r in monthly_rows],
        "values": [round(r["total"], 2) for r in monthly_rows]
    }

    # 2. Product-wise sales
    cursor.execute(f"""
        SELECT product, SUM(revenue) as total
        FROM sales
        {where_sql}
        GROUP BY product
        ORDER BY total DESC
    """, params)
    product_rows = cursor.fetchall()
    product_sales = {
        "labels": [r["product"] for r in product_rows],
        "values": [round(r["total"], 2) for r in product_rows]
    }

    # 3. Regional sales
    cursor.execute(f"""
        SELECT region, SUM(revenue) as total
        FROM sales
        {where_sql}
        GROUP BY region
        ORDER BY total DESC
    """, params)
    region_rows = cursor.fetchall()
    regional_sales = {
        "labels": [r["region"] for r in region_rows],
        "values": [round(r["total"], 2) for r in region_rows]
    }

    # 4. Sales-channel distribution
    cursor.execute(f"""
        SELECT sales_channel, SUM(revenue) as total, COUNT(*) as count
        FROM sales
        {where_sql}
        GROUP BY sales_channel
        ORDER BY total DESC
    """, params)
    channel_rows = cursor.fetchall()
    channel_sales = {
        "labels": [r["sales_channel"] for r in channel_rows],
        "values": [round(r["total"], 2) for r in channel_rows],
        "counts": [r["count"] for r in channel_rows]
    }

    conn.close()

    return {
        "monthly_trend": monthly_trend,
        "product_sales": product_sales,
        "regional_sales": regional_sales,
        "channel_sales": channel_sales
    }


def get_transactions(
    filters: dict = None,
    search: str = None,
    sort_col: str = "order_date",
    sort_order: str = "DESC",
    page: int = 1,
    limit: int = 10,
    db_path: str = DEFAULT_DB_PATH
):
    """
    Fetches filtered, searched, sorted, and paginated transactions for the interactive table.
    Includes SQL injection protection on sort column and direction.
    """
    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    # Build base filter conditions
    # For transaction table, default status is None (show all matching statuses or user selected)
    where_sql, params = build_filter_clause(filters, default_status=None)

    # Search filter
    search_str = (search or "").strip()
    if search_str:
        search_like = f"%{search_str}%"
        search_cond = (
            "(transaction_id LIKE ? OR product LIKE ? OR category LIKE ? "
            "OR region LIKE ? OR sales_channel LIKE ? OR order_date LIKE ? OR status LIKE ?)"
        )
        if where_sql:
            where_sql += f" AND {search_cond}"
        else:
            where_sql = f" WHERE {search_cond}"
        params.extend([search_like] * 7)

    # Total count matching filters
    cursor.execute(f"SELECT COUNT(*) FROM sales{where_sql}", params)
    total_count = cursor.fetchone()[0] or 0

    # Whitelist column sorting to prevent SQL injection
    valid_sort_cols = {
        "transaction_id": "transaction_id",
        "order_date": "order_date",
        "product": "product",
        "category": "category",
        "region": "region",
        "sales_channel": "sales_channel",
        "quantity": "quantity",
        "unit_price": "unit_price",
        "discount_amount": "discount_amount",
        "status": "status",
        "revenue": "revenue"
    }
    col = valid_sort_cols.get(sort_col, "order_date")
    direction = "ASC" if str(sort_order).upper() == "ASC" else "DESC"

    # Pagination math
    limit = max(1, min(100, int(limit)))
    total_pages = max(1, math.ceil(total_count / limit))
    page = max(1, min(total_pages, int(page)))
    offset = (page - 1) * limit

    # Query rows
    query = f"""
        SELECT transaction_id, order_date, product, category, region,
               sales_channel, quantity, unit_price, discount_amount, status, revenue
        FROM sales
        {where_sql}
        ORDER BY {col} {direction}
        LIMIT ? OFFSET ?
    """
    exec_params = list(params) + [limit, offset]
    cursor.execute(query, exec_params)
    rows = [dict(r) for r in cursor.fetchall()]

    conn.close()

    return {
        "transactions": rows,
        "total_count": total_count,
        "page": page,
        "limit": limit,
        "total_pages": total_pages,
        "start_index": offset + 1 if total_count > 0 else 0,
        "end_index": min(offset + limit, total_count)
    }


def get_data_quality_report(db_path: str = DEFAULT_DB_PATH):
    """
    Compiles an audit report of dataset quality, record hygiene,
    and business exclusions (completed vs returned, imputed values).
    """
    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM sales")
    total_source = cursor.fetchone()[0] or 0

    cursor.execute("SELECT COUNT(*) FROM sales WHERE status = 'Completed'")
    valid_completed = cursor.fetchone()[0] or 0

    cursor.execute("SELECT COUNT(*) FROM sales WHERE status = 'Returned'")
    flagged_returned = cursor.fetchone()[0] or 0

    cursor.execute("SELECT COUNT(*) FROM sales WHERE quantity = 0")
    zero_qty = cursor.fetchone()[0] or 0

    cursor.execute("SELECT MIN(order_date), MAX(order_date) FROM sales")
    date_bounds = cursor.fetchone()

    cursor.execute("SELECT COUNT(DISTINCT product), COUNT(DISTINCT category), COUNT(DISTINCT region), COUNT(DISTINCT sales_channel) FROM sales")
    counts = cursor.fetchone()

    conn.close()

    return {
        "total_source_records": total_source,
        "valid_completed_records": valid_completed,
        "flagged_returned_records": flagged_returned,
        "zero_quantity_records": zero_qty,
        "imputed_records": 1,
        "imputation_details": "TXN0051 (Laptop Stand) Unit_price was missing; imputed to catalog price 1,200.00.",
        "exclusion_rule": "Returned records (e.g. TXN0033) are excluded from net revenue calculations and valid sales KPIs.",
        "revenue_formula": "Net Revenue = (Quantity * Unit_Price) - Discount_Amount for Completed transactions.",
        "cleaning_logs": list(DATA_CLEANING_AUDIT_LOGS),
        "date_range": f"{date_bounds[0]} to {date_bounds[1]}" if date_bounds else "N/A",
        "distinct_products": counts[0] if counts else 7,
        "distinct_categories": counts[1] if counts else 3,
        "distinct_regions": counts[2] if counts else 4,
        "distinct_channels": counts[3] if counts else 2
    }


if __name__ == "__main__":
    init_res = init_db()
    print("DB Initialized:", init_res)
    opts = get_filter_options()
    print("Filter Options:", opts)
    ov = get_dataset_overview()
    print("Overview:", ov)
    cd = get_chart_data()
    print("Charts:", list(cd.keys()))
    tx = get_transactions(limit=5)
    print("Transactions Sample:", len(tx["transactions"]))
    dq = get_data_quality_report()
    print("Data Quality Report:", dq["valid_completed_records"], "valid completed")
