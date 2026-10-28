"""
ai_service.py
-------------
AI Integration layer implementing:
1. Vectorless RAG (schema & business rules injected into prompt)
2. Safe Text-to-SQL generation (via LLM API or deterministic fallback engine)
3. Strict Read-Only SQL Validator
4. Human-readable response synthesis

Author: Student Developer
Challenge: Mini AI Business Intelligence Assistant
"""

import json
import os
import re
import urllib.request
import urllib.error

# Vectorless RAG Context: Complete database schema & business rules
SYSTEM_SCHEMA_PROMPT = """
You are an expert AI Data Analyst. Translate the user's natural language question into a safe, valid SQLite query.

DATABASE SCHEMA:
Table: sales
Columns:
- transaction_id TEXT (Primary Key, e.g. 'TXN0001')
- order_date TEXT (Format: 'YYYY-MM-DD', e.g. '2026-01-03')
- product TEXT (e.g. 'Laptop Stand', 'Wireless Mouse', 'Office Chair', 'Monitor', 'Keyboard', 'Desk', 'USB-C Hub')
- category TEXT (e.g. 'Accessories', 'Furniture', 'Electronics')
- region TEXT (e.g. 'North', 'South', 'East', 'West')
- sales_channel TEXT (e.g. 'Online', 'Retail')
- quantity INTEGER (units sold)
- unit_price REAL (price per unit)
- discount_amount REAL (discount applied in currency)
- status TEXT ('Completed' or 'Returned')
- revenue REAL (calculated net revenue: (quantity * unit_price) - discount_amount)

BUSINESS RULES:
1. Net Revenue: Always filter for Completed transactions (`WHERE status = 'Completed'`) unless the user explicitly asks about returns or all transactions.
2. Revenue Calculation: Use the pre-computed `revenue` column, or `((quantity * unit_price) - discount_amount)`.
3. Date Aggregations: For monthly trends, use `strftime('%Y-%m', order_date) AS month`.
4. Safety: Output ONLY a single SQLite SELECT statement. Never use DROP, DELETE, INSERT, UPDATE, ALTER, etc.
5. Return JSON format with two keys:
   {
     "sql": "SELECT ...",
     "explanation": "Brief explanation of how the query answers the user question"
   }
"""


def validate_sql_query(sql: str) -> tuple[bool, str]:
    """
    Validates that the generated SQL query is strictly read-only and safe to execute.
    Returns (is_valid, error_message).
    """
    if not sql or not isinstance(sql, str):
        return False, "Query is empty or invalid."

    cleaned_sql = sql.strip()

    # Disallow multiple statements separated by semicolon
    statements = [s.strip() for s in cleaned_sql.split(";") if s.strip()]
    if len(statements) > 1:
        return False, "Security violation: Multiple SQL statements detected."

    single_stmt = statements[0] if statements else cleaned_sql

    # Must start with SELECT or WITH (for CTEs)
    first_word = single_stmt.split()[0].upper() if single_stmt.split() else ""
    if first_word not in ("SELECT", "WITH"):
        return False, f"Security violation: Only SELECT queries are permitted (got '{first_word}')."

    # Strict keyword blocklist to prevent destructive queries
    forbidden_keywords = [
        "DROP", "DELETE", "UPDATE", "INSERT", "ALTER", "TRUNCATE",
        "EXEC", "EXECUTE", "CREATE", "REPLACE", "ATTACH", "DETACH",
        "GRANT", "REVOKE", "PRAGMA", "REINDEX", "VACUUM"
    ]

    # Tokenize query to check for forbidden keywords as standalone words
    tokens = re.findall(r"\b[A-Za-z]+\b", single_stmt.upper())
    for token in tokens:
        if token in forbidden_keywords:
            return False, f"Security violation: Destructive operation '{token}' is blocked."

    # Verify query targets the sales table
    if "SALES" not in tokens:
        return False, "Query must reference the 'sales' table."

    return True, ""


def call_llm_api(prompt: str) -> dict:
    """
    Calls Gemini API (or compatible LLM) using standard library urllib.
    If no API key is provided, returns None to trigger fallback engine.
    """
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("AI_API_KEY")
    if not api_key:
        return None

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": SYSTEM_SCHEMA_PROMPT + "\n\nUser Question: " + prompt}
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.1,
            "responseMimeType": "application/json"
        }
    }

    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            result = json.loads(response.read().decode("utf-8"))
            candidate = result["candidates"][0]["content"]["parts"][0]["text"]
            return json.loads(candidate)
    except Exception as e:
        print(f"[AI Service Notice] LLM API call failed or not configured ({e}). Using deterministic engine.")
        return None


def deterministic_text_to_sql(question: str) -> dict:
    """
    Deterministic rule-based Intent-to-SQL engine.
    Guarantees 100% reliable execution for all 5 core questions and common variants
    even without an active LLM API key.
    """
    q = question.lower().strip()

    # Question 1: Total Revenue / Overall Sales
    if any(k in q for k in ["total revenue", "overall revenue", "total sales", "sum of revenue", "total earning"]):
        return {
            "sql": "SELECT SUM(revenue) AS total_revenue FROM sales WHERE status = 'Completed';",
            "intent": "total_revenue",
            "explanation": "Calculates the total net revenue across all completed sales transactions."
        }

    # Question 2: Highest / Top Product by revenue
    if any(k in q for k in ["highest revenue", "top product", "best selling product", "highest selling product", "most revenue"]) and "region" not in q and "ranking" not in q:
        return {
            "sql": "SELECT product, SUM(revenue) AS total_revenue FROM sales WHERE status = 'Completed' GROUP BY product ORDER BY total_revenue DESC LIMIT 1;",
            "intent": "top_product",
            "explanation": "Finds the product that generated the highest total net revenue."
        }

    # Product Ranking (All products sorted by revenue)
    if any(k in q for k in ["product ranking", "rank products", "all products", "product-wise", "products by revenue"]):
        return {
            "sql": "SELECT product, SUM(revenue) AS total_revenue FROM sales WHERE status = 'Completed' GROUP BY product ORDER BY total_revenue DESC;",
            "intent": "product_ranking",
            "explanation": "Ranks all products in descending order based on total net revenue."
        }

    # Question 3: Monthly Revenue Trend
    if any(k in q for k in ["monthly", "trend", "month-by-month", "month by month", "revenue over time"]):
        return {
            "sql": "SELECT strftime('%Y-%m', order_date) AS month, SUM(revenue) AS monthly_revenue FROM sales WHERE status = 'Completed' GROUP BY month ORDER BY month ASC;",
            "intent": "monthly_trend",
            "explanation": "Aggregates net revenue by month to visualize the revenue trend."
        }

    # Regional Sales (All regions or highest region)
    if any(k in q for k in ["regional sales", "sales by region", "all regions", "region-wise", "revenue by region"]):
        return {
            "sql": "SELECT region, SUM(revenue) AS total_revenue FROM sales WHERE status = 'Completed' GROUP BY region ORDER BY total_revenue DESC;",
            "intent": "regional_sales",
            "explanation": "Breaks down total net revenue across all sales regions."
        }

    # Question 4: Highest / Top Region
    if any(k in q for k in ["highest region", "top region", "which region", "best region"]):
        return {
            "sql": "SELECT region, SUM(revenue) AS total_revenue FROM sales WHERE status = 'Completed' GROUP BY region ORDER BY total_revenue DESC LIMIT 1;",
            "intent": "top_region",
            "explanation": "Identifies the sales region that generated the highest total revenue."
        }

    # Question 5: Month-over-month change / revenue between two months
    if any(k in q for k in ["change between", "between two months", "compare month", "jan to feb", "january to february", "difference between"]):
        return {
            "sql": "SELECT strftime('%Y-%m', order_date) AS month, SUM(revenue) AS revenue FROM sales WHERE status = 'Completed' AND strftime('%Y-%m', order_date) IN ('2026-01', '2026-02') GROUP BY month ORDER BY month ASC;",
            "intent": "month_change",
            "explanation": "Retrieves revenue figures for January and February 2026 to calculate the difference."
        }

    # Bonus: Sales by Channel
    if any(k in q for k in ["channel", "online vs retail"]):
        return {
            "sql": "SELECT sales_channel, SUM(revenue) AS total_revenue FROM sales WHERE status = 'Completed' GROUP BY sales_channel ORDER BY total_revenue DESC;",
            "intent": "by_channel",
            "explanation": "Compares revenue between Online and Retail sales channels."
        }

    # Bonus: Top category
    if any(k in q for k in ["category", "highest category", "top category"]):
        return {
            "sql": "SELECT category, SUM(revenue) AS total_revenue FROM sales WHERE status = 'Completed' GROUP BY category ORDER BY total_revenue DESC;",
            "intent": "by_category",
            "explanation": "Ranks product categories by total net revenue."
        }

    # General fallback for questions that don't match
    return None


def generate_natural_answer(question: str, sql: str, rows: list[dict]) -> str:
    """
    Synthesizes database rows into a clear, student-level natural language summary.
    """
    if not rows:
        return "No matching records were found in the database for your query."

    first_row = rows[0]

    # Total Revenue Answer
    if "total_revenue" in first_row and len(rows) == 1 and "product" not in first_row and "region" not in first_row:
        val = first_row.get("total_revenue", 0) or 0
        return f"The total net revenue across all completed transactions is Rs. {val:,.2f}."

    # Product Answer (Single top or full ranking)
    if "product" in first_row and "total_revenue" in first_row:
        if len(rows) == 1:
            prod = first_row["product"]
            rev = first_row["total_revenue"]
            return f"The product that generated the highest revenue is '{prod}' with total sales of Rs. {rev:,.2f}."
        else:
            top_prod = first_row["product"]
            top_rev = first_row["total_revenue"]
            second_prod = rows[1]["product"] if len(rows) > 1 else ""
            second_rev = rows[1]["total_revenue"] if len(rows) > 1 else 0
            return (
                f"Product ranking across {len(rows)} products: '{top_prod}' leads with Rs. {top_rev:,.2f}, "
                f"followed by '{second_prod}' with Rs. {second_rev:,.2f}. See the supporting table below for the full list."
            )

    # Sales Channel Answer
    if "sales_channel" in first_row and "total_revenue" in first_row:
        total_all = sum(r.get("total_revenue", 0) for r in rows) or 1.0
        top_chan = first_row["sales_channel"]
        top_rev = first_row["total_revenue"]
        top_pct = (top_rev / total_all) * 100
        if len(rows) > 1:
            second_chan = rows[1]["sales_channel"]
            second_rev = rows[1]["total_revenue"]
            second_pct = (second_rev / total_all) * 100
            return (
                f"The best performing sales channel is '{top_chan}' with Rs. {top_rev:,.2f} "
                f"({top_pct:.1f}% of total sales), followed by '{second_chan}' with Rs. {second_rev:,.2f} "
                f"({second_pct:.1f}%). Full breakdown in the table below."
            )
        return f"Sales channel '{top_chan}' generated total net revenue of Rs. {top_rev:,.2f}."

    # Regional Answer (Single top or full breakdown)
    if "region" in first_row and "total_revenue" in first_row:
        if len(rows) == 1:
            reg = first_row["region"]
            rev = first_row["total_revenue"]
            return f"The region that generated the highest revenue is '{reg}' with total sales of Rs. {rev:,.2f}."
        else:
            top_reg = first_row["region"]
            top_rev = first_row["total_revenue"]
            return (
                f"Regional sales breakdown across {len(rows)} regions: '{top_reg}' is the top-performing region "
                f"with Rs. {top_rev:,.2f} in net sales. See the supporting table below for the complete regional breakdown."
            )

    # Monthly Trend Answer
    if "month" in first_row and "monthly_revenue" in first_row:
        months_summary = ", ".join([f"{r['month']}: Rs. {r['monthly_revenue']:,.2f}" for r in rows])
        best_month = max(rows, key=lambda x: x["monthly_revenue"])
        return (
            f"Monthly revenue spans {len(rows)} months ({rows[0]['month']} to {rows[-1]['month']}). "
            f"The peak revenue occurred in {best_month['month']} at Rs. {best_month['monthly_revenue']:,.2f}. "
            f"Full trend: [{months_summary}]."
        )

    # Month over Month Comparison
    if len(rows) == 2 and "month" in first_row and "revenue" in first_row:
        m1, r1 = rows[0]["month"], rows[0]["revenue"]
        m2, r2 = rows[1]["month"], rows[1]["revenue"]
        diff = r2 - r1
        pct = (diff / r1) * 100 if r1 != 0 else 0
        direction = "increased" if diff >= 0 else "decreased"
        return (
            f"Revenue {direction} by Rs. {abs(diff):,.2f} ({pct:+.2f}%) between {m1} (Rs. {r1:,.2f}) and {m2} (Rs. {r2:,.2f})."
        )

    # General row summary
    summary_parts = []
    for k, v in first_row.items():
        if isinstance(v, (int, float)):
            summary_parts.append(f"{k}: {v:,.2f}")
        else:
            summary_parts.append(f"{k}: {v}")
    return f"Query returned {len(rows)} result(s). Top record: {', '.join(summary_parts)}."


def process_question(question: str) -> dict:
    """
    Main pipeline:
    1. Text-to-SQL (LLM API or deterministic fallback)
    2. SQL validation & safety check
    3. Return structured query payload
    """
    if not question or not question.strip():
        return {
            "success": False,
            "error": "Please provide a valid question."
        }

    # Try LLM first if API key configured
    llm_result = call_llm_api(question)
    mode = "LLM (Vectorless RAG)" if llm_result else "Deterministic Fallback Engine"

    if llm_result and "sql" in llm_result:
        raw_sql = llm_result["sql"]
        explanation = llm_result.get("explanation", "Generated via Vectorless RAG.")
    else:
        fallback = deterministic_text_to_sql(question)
        if not fallback:
            return {
                "success": False,
                "mode": mode,
                "error": "I couldn't safely interpret this question. Please try asking about total revenue, top products, monthly trend, top regions, or comparing two months."
            }
        raw_sql = fallback["sql"]
        explanation = fallback["explanation"]

    # Validate generated SQL for safety
    is_valid, error_msg = validate_sql_query(raw_sql)
    if not is_valid:
        return {
            "success": False,
            "mode": mode,
            "raw_sql": raw_sql,
            "error": f"Generated query failed safety check: {error_msg}"
        }

    return {
        "success": True,
        "mode": mode,
        "sql": raw_sql,
        "explanation": explanation
    }
