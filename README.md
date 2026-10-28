# Sales Insight Assistant — Executive BI Dashboard & NLP Analytics

> **Enterprise Sales Business Intelligence & Deterministic Text-to-SQL Engine**  
> Built with Python, Flask, SQLite 3, Pandas, Chart.js, and Vectorless RAG. Designed for placement evaluations, college project showcases, and real-world executive decision-making.

---

## 📌 Project Overview

**Sales Insight Assistant** is a business analytics and natural language sales intelligence platform. It enables business leaders and non-technical stakeholders to ask everyday questions (e.g., *"What is the total revenue?"*, *"Which product generated the highest revenue?"*, *"Which sales channel performs best?"*) and receive deterministic answers backed by real SQL queries on SQLite, transparent audit trails, interactive charts, and dynamic multi-dimensional filters.

### 🌟 Key Highlights
- **Premium Glassmorphism Dashboard**: Deep navy background (`#080c18`), vibrant neon emerald/teal accents (`#00dca4`), purple/sky-blue highlights, frosted glass cards, and soft ambient glow effects.
- **Laptop & Desktop Optimized**: Pixel-perfect layout for standard laptop resolutions (**1366×768** and **1920×1080**) with zero horizontal overflow and responsive adaptation.
- **4 Real-Time KPI Cards**: Total Net Revenue, Completed Transactions, Top Product by Revenue, and Top Sales Region.
- **Interactive Multi-Dimensional Filters**: Filter by Month, Product, Region, Sales Channel, and Transaction Status with instant cross-dashboard synchronization.
- **4 Interactive Visualizations (2×2 Grid)**:
  1. *Monthly Revenue Trend* (Line Chart with smooth spline curve and teal area glow)
  2. *Product-wise Sales Revenue* (Multi-color bar chart ranking all 7 products)
  3. *Regional Sales Comparison* (Sky-blue gradient bar chart across North, South, East, West)
  4. *Sales Channel Breakdown* (Doughnut chart with Online vs. Retail revenue distribution and center percentage metrics)
- **Natural Language Assistant**: Safe Text-to-SQL engine with read-only validation, Vectorless RAG, and an instant deterministic fallback engine for 7+ core analytical intents.
- **Searchable & Sortable Transaction Table**: Real-time substring search, multi-column sorting (Txn ID, Date, Product, Category, Qty, Revenue, Status), and pagination (10 rows/page).
- **Data Quality & Hygiene Audit Panel**: Transparent audit metrics highlighting source records (51), valid completed records (50), excluded returns (1), imputed catalog unit prices (1), and revenue calculation rules.

---

## 🏗️ Architecture & Data Flow

```
+---------------------------------------------------------------------------------+
|                         Modern Glassmorphism Frontend                           |
|       (HTML5, CSS3 Variables, Backdrop Blur, Chart.js, Fetch REST API)         |
+----------------------------------------+----------------------------------------+
                                         |
                                         | HTTP GET/POST (/api/...)
                                         v
+---------------------------------------------------------------------------------+
|                               Flask REST API                                    |
|             (app.py - Routing, Filter Extraction, Error Handling)               |
+-------------------+--------------------+--------------------+-------------------+
                    |                    |                    |
                    v                    v                    v
      +-----------------------------+    |    +-----------------------------+
      |    Vectorless RAG Engine    |    |    |   Dynamic Multi-Filter      |
      |       (ai_service.py)       |    |    |       Query Engine          |
      | - Injects Schema + Context  |    |    |       (database.py)         |
      | - Gemini API or Fallback    |    |    | - Filtered KPIs & Charts    |
      +--------------+--------------+    |    | - Search & Sort Pagination  |
                     |                   |    +--------------+--------------+
                     v                   |                   |
      +-----------------------------+    |                   |
      |   SQL Security Validator    |    |                   |
      | - Enforces SELECT / WITH    |<---+                   |
      | - Blocks DROP/DELETE/INSERT |                        |
      +--------------+--------------+                        |
                     |                                       |
                     +-------------------+-------------------+
                                         | Safe SQL / Parameterized Queries
                                         v
+---------------------------------------------------------------------------------+
|                               SQLite 3 Database                                 |
|                                  (sales.db)                                     |
|  - Ingests & cleans sales_data.csv on startup                                   |
|  - Imputes missing unit price for TXN0051 (Laptop Stand -> ₹1,200.00)           |
|  - Enforces net revenue rule: (Quantity * Unit_Price) - Discount_Amount         |
|  - Excludes 'Returned' items (TXN0033) from completed revenue calculations      |
+---------------------------------------------------------------------------------+
```

---

## 💡 Core Design & Engineering Concepts

### 1. Vectorless RAG (Retrieval-Augmented Generation)
Traditional RAG converts documents into vector embeddings and queries a vector store using cosine similarity. While effective for unstructured text, vector search often hallucinates or fuzzy-matches inaccurate numbers over structured financial tables.

**Vectorless RAG** passes the exact database schema, column types, and business rules directly into the LLM system prompt:
- The model outputs a deterministic, syntactically correct SQLite query.
- The SQL query executes against SQLite to retrieve exact mathematical sums.
- The result rows are synthesized into natural English answers with currency symbols.

### 2. Dual-Engine Intelligence (LLM + Deterministic Fallback)
The project runs reliably offline or in air-gapped evaluation environments:
- **LLM Mode**: Active whenever `GEMINI_API_KEY` is present in your environment or `.env` file.
- **Deterministic Engine**: Instantly takes over if no API key is provided, matching natural language intents across total revenue, product rankings, monthly trends, regional sales, channel performance, and month-over-month comparisons.

### 3. Strict SQL Security Validator
Every query must pass strict validation before execution:
- **Read-Only**: Must begin with `SELECT` or `WITH`.
- **Forbidden Keyword Blocklist**: Rejects queries with `DROP`, `DELETE`, `UPDATE`, `INSERT`, `ALTER`, `TRUNCATE`, `EXEC`, `CREATE`, `REPLACE`, `ATTACH`, `DETACH`, or `PRAGMA`.
- **Anti-Stacking**: Multiple statements separated by semicolons are strictly blocked.
- **Table Whitelist**: Queries must reference the `sales` table.

---

## 🧹 Data Quality & Edge Case Auditing

The dataset (`sales_data.csv`) contains 51 transaction rows with real-world data hygiene edge cases:

| Issue | Record | Description & Resolution |
|---|---|---|
| **Missing Unit Price** | `TXN0051` | Laptop Stand transaction with empty `Unit_price`. Automatically imputed using the catalog unit price of other Laptop Stand orders (`₹ 1,200.00`). |
| **Returned Item** | `TXN0033` | Marked as `Status = 'Returned'`. Excluded from completed net sales and valid revenue KPIs (`WHERE status = 'Completed'`). |
| **Zero Quantity** | `TXN0034` | Desk order with `Quantity = 0`. Handled cleanly without zero-division or mathematical errors (evaluated to `₹ 0.00`). |
| **Monetary Discounts** | Multiple | Discretionary discounts (e.g., `TXN0004`, `TXN0012`) are deducted at the row level: `Revenue = (Quantity × Unit_Price) - Discount_Amount`. |
| **Date Normalization** | All | Normalized from `DD-MM-YYYY` to ISO format `YYYY-MM-DD` during ingestion for SQLite `strftime('%Y-%m', order_date)`. |

---

## 📊 Summary of Baseline Metrics (All Completed Records)

- **Total Transactions in CSV**: 51
- **Valid Completed Transactions**: 50
- **Returned Transactions**: 1 (`TXN0033`)
- **Total Net Revenue**: **₹ 1,445,200.00**
- **Highest-Revenue Product**: **Monitor** (**₹ 473,000.00**, 32.7% of total sales)
- **Highest-Revenue Region**: **South** (**₹ 411,200.00**, 28.5% of total sales)
- **Top Sales Channel**: **Online** (**₹ 752,750.00**, 52.1% of total sales; Retail = ₹ 692,450.00)
- **Date Range**: `2026-01-03` to `2026-06-28`

---

## 🚀 Setup & Execution Instructions

### Prerequisites
- Python 3.9 or higher
- PowerShell, Command Prompt, or Bash

### 1. Clone or Extract the Project
```powershell
cd "c:\Users\govin\OneDrive\Desktop\AI Sales Assistant"
```

### 2. Create and Activate Virtual Environment
```powershell
# Create virtual environment
python -m venv .venv

# Activate on Windows PowerShell
.\.venv\Scripts\Activate.ps1

# (Or on Command Prompt)
# .venv\Scripts\activate.bat

# (Or on Linux / macOS)
# source .venv/bin/activate
```

### 3. Install Dependencies
```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### 4. Optional: Configure Gemini AI Key
Create a `.env` file if you want to test live LLM generation:
```ini
GEMINI_API_KEY=your_google_gemini_api_key_here
```
*(If omitted, the built-in deterministic fallback engine handles all queries automatically).*

### 5. Launch the Application
```powershell
python app.py
```
Output:
```
[SYSTEM] Initializing database from sales_data.csv...
[SYSTEM] Database ready: 51 records loaded.
  -> Imputed missing Unit_price for TXN0051 (Laptop Stand) -> 1200.00
[SYSTEM] Starting server on http://localhost:5000
 * Serving Flask app 'app'
 * Running on http://127.0.0.1:5000
```

### 6. View the Dashboard
Open your browser and navigate to:
👉 **[http://127.0.0.1:5000](http://127.0.0.1:5000)**

---

## 🧪 Automated Test Suite

Run the full automated test suite containing 16 unit and integration test cases:
```powershell
python -m pytest tests/test_app.py -v
```

### Test Coverage Highlights:
1. `test_data_cleaning_and_imputation`: Verifies `TXN0051` price imputation, `TXN0033` returned status, `TXN0034` zero quantity.
2. `test_total_revenue_calculation`: Verifies ₹ 1,445,200.00 net calculation after discounts.
3. `test_highest_revenue_product`: Verifies Monitor (₹ 473,000.00).
4. `test_monthly_revenue_trend`: Chronological ordering across all 6 months (Jan–Jun 2026).
5. `test_highest_region`: Verifies South region (₹ 411,200.00).
6. `test_revenue_change_between_months`: Verifies Jan to Feb month-over-month delta (+₹ 24,350.00).
7. `test_sql_validator_blocks_destructive_queries`: Confirms blocking of `DROP`, `DELETE`, `UPDATE`, and multi-statement injection.
8. `test_invalid_questions_handling`: Graceful handling of empty or unanswerable queries.
9. `test_api_query_endpoint`: End-to-end integration for `POST /api/query`.
10. `test_product_ranking_and_regional_sales`: Ranking and regional breakdowns.
11. `test_api_charts_endpoint`: Chart.js payloads.
12. `test_sales_channel_query`: Channel comparison (Online vs. Retail).
13. `test_filtered_overview_endpoint`: Dynamic KPI calculations under parameter filters.
14. `test_four_charts_endpoint`: Verification of all 4 chart datasets.
15. `test_transactions_table_endpoint`: Search, sort, and pagination.
16. `test_data_quality_endpoint`: Data reliability and audit metrics.

---

## 📡 REST API Reference

| Endpoint | Method | Description | Parameters |
|---|---|---|---|
| `/` | `GET` | Serves single-page glassmorphism dashboard | None |
| `/api/filter-options` | `GET` | Returns distinct months, products, regions, channels | None |
| `/api/overview` | `GET` | Returns 4 KPI cards and summary statistics | `month`, `product`, `region`, `sales_channel`, `status` |
| `/api/charts` | `GET` | Returns data for 4 Chart.js charts | `month`, `product`, `region`, `sales_channel`, `status` |
| `/api/transactions` | `GET` | Returns paginated, searched, and sorted transactions | `page`, `limit`, `sort`, `order`, `search`, filters |
| `/api/data-quality` | `GET` | Returns data hygiene audit metrics and rules | None |
| `/api/query` | `POST` | Natural language question answering | JSON: `{"question": "..."}` |
| `/api/sample-data` | `GET` | Returns sample records (legacy compatibility) | None |

---

## 📁 Repository Structure

```
AI Sales Assistant/
├── app.py                     # Flask web server & REST API controller
├── database.py                # SQLite initialization, cleaning, filters, pagination
├── ai_service.py              # Vectorless RAG, SQL security validator, fallback engine
├── sales_data.csv             # Raw source dataset (51 transaction rows)
├── sales.db                   # SQLite database (auto-generated & cleaned on startup)
├── requirements.txt           # Python dependencies (Flask, pandas, pytest, dotenv)
├── README.md                  # Comprehensive technical documentation & run guide
├── AI_USAGE_REPORT.md         # Full AI usage, prompt log, and architectural reflection
├── static/
│   ├── index.html             # Presentation-ready Glassmorphism UI
│   ├── style.css              # Custom design system with CSS variables & blur filters
│   └── script.js              # Interactive charts, dynamic filters, table pagination, NLP
└── tests/
    └── test_app.py            # 16 automated pytest unit & integration test cases
```

---

## 🎓 Placement & Interview Defense Notes

- **Why SQLite over in-memory Python structures?** SQLite allows demonstration of genuine SQL proficiency (`GROUP BY`, `strftime`, `LIMIT`, window functions) and mirrors enterprise SQL warehouses like BigQuery, Snowflake, and PostgreSQL.
- **Why Vectorless RAG over standard Vector DB RAG?** Vector databases perform fuzzy similarity searches on text embeddings, which causes hallucination or inaccurate figures when performing mathematical calculations. Vectorless RAG feeds relational schemas to the LLM so it generates exact SQL queries executed deterministically against the relational engine.
- **How was data cleanliness ensured?** Data anomalies were identified, audited, and resolved programmatically: `TXN0051` unit price was imputed from catalog records, `TXN0033` was excluded from net revenue, and discount deductions were calculated transparently.
