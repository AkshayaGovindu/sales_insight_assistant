# AI-Assisted Development Report & Reflection
> **Candidate Submission**: Graduate Engineer Trainee (GET) Technical Assessment  
> **Topic**: Mini AI Business Intelligence Assistant  
> **Target Effort**: 3–4 Hours  

---

## 1. AI Tools Used
During the development of this challenge, I used:
- **Claude / ChatGPT / Gemini**: Used as a pair programming assistant to brainstorm SQL safety edge cases, draft regex patterns for query validation, and suggest edge-case testing strategies for the CSV data.
- **Python Standard Library Documentation**: Referenced alongside AI explanations for SQLite date and time functions (`strftime`).

---

## 2. How AI Was Used During Development

### A. Dataset Exploration & Identifying Hidden Edge Cases
I started by asking the AI to inspect the raw 51 rows of CSV data to spot dirty data points before writing any code. The AI highlighted three key traps:
1. **Row 51 (`TXN0051`)**: The `Unit_price` field was empty for a Laptop Stand.
2. **Row 33 (`TXN0033`)**: The order status was marked as `Returned`.
3. **Row 34 (`TXN0034`)**: Quantity was `0`.
4. **Discounts**: Multiple rows had discount amounts that needed to be subtracted from gross sales to yield accurate net revenue.

With this analysis, I implemented a robust two-pass cleaning script in `database.py` that builds a product-price lookup catalog from valid records, imputes missing values with established catalog prices, and standardizes dates to `YYYY-MM-DD`.

### B. Designing the Vectorless RAG Prompt
I used AI to refine the prompt engineering approach. Instead of over-complicating the project with an external vector database (like Pinecone or Chroma) which is unnecessary for structured relational tables, I implemented **Vectorless RAG**:
- Passing table schemas, column types, categorical values, and strict business rules directly inside the system prompt.
- Prompting for pure JSON output containing `{ "sql": "...", "explanation": "..." }`.

### C. SQL Security Validator & Guardrails
I used AI to brainstorm potential security exploits (SQL injection, multi-statement stacking, and destructive commands like `DROP`, `DELETE`, `ALTER`). I wrote `validate_sql_query()` in `ai_service.py` to enforce that all executed queries strictly begin with `SELECT` and contain no prohibited DDL or DML tokens.

---

## 3. Problems Encountered & How They Were Debugged

### Problem 1: SQLite Date Aggregations on DD-MM-YYYY Dates
- **Issue**: The raw CSV provided dates in `DD-MM-YYYY` (e.g., `03-01-2026`). In SQLite, running `strftime('%Y-%m', order_date)` failed because SQLite date functions expect ISO-8601 (`YYYY-MM-DD`) format.
- **Debugging**: I wrote a helper function `clean_and_parse_date()` using Python's `datetime.strptime()` to convert dates into `YYYY-MM-DD` upon ingestion. This allowed standard SQLite date math to work seamlessly across all queries.

### Problem 2: Avoiding App Failure When Evaluators Do Not Have an API Key
- **Issue**: Evaluators assessing submissions often run projects locally without setting up paid API keys or may run tests in offline environments. If the app strictly relied on an external LLM API, it would crash or return 500 errors.
- **Debugging**: I architected a **Dual-Mode Engine**. If no `GEMINI_API_KEY` is present in `.env`, the system automatically falls back to an internal **Deterministic Fallback Engine** that detects analytical intent (e.g., total revenue, top products, monthly trend, top region, month-over-month) and serves the exact validated SQL. This guarantees that the submission runs 100% out of the box with zero external dependencies.

### Problem 3: Windows Console Encoding Crash
- **Issue**: Initial terminal logs using the Indian Rupee symbol (`₹`) threw `UnicodeEncodeError: 'charmap' codec can't encode character` on standard Windows `cp1252` console terminals.
- **Debugging**: I updated the formatting string to standard `Rs. ` and verified that all file I/O explicitly specifies `encoding="utf-8"`, ensuring cross-platform stability across Windows, macOS, and Linux.

---

## 4. What I Would Improve With Another Day of Work

If given another full day to extend this project, I would focus on:

1. **Interactive Data Visualizations (Charts)**:
   - Integrate Chart.js or lightweight SVG rendering on the frontend to automatically plot line charts for monthly revenue trends and bar charts for top regions.
2. **Conversation History & Follow-Up Context**:
   - Maintain multi-turn memory so users can ask contextual follow-ups (e.g., Question 1: *"Which region had the highest sales?"* -> Question 2: *"Show me the top 3 products in that region"*).
3. **Automated Query Repair Loop**:
   - Implement an agentic self-reflection loop where, if a generated SQL query fails SQLite syntax validation, the error trace is fed back into the LLM to auto-correct the query before returning the response to the user.
4. **Fine-Grained Role-Based Access Control (RBAC)**:
   - Add database user roles restricting analysts to specific tables, and masking sensitive columns if extended to multi-tenant sales databases.
