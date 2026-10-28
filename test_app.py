"""
test_app.py
-----------
Automated test suite for Mini AI Business Intelligence Assistant.
Covers:
1. Data cleaning & imputation (TXN0051, TXN0033)
2. Total revenue computation (with discounts and returns excluded)
3. Highest revenue product calculation
4. Monthly trend aggregation
5. SQL security validator (blocking DROP, DELETE, multi-statements)
6. Invalid / unanswerable questions
7. Flask API endpoints integration

Author: Student Developer
Challenge: Mini AI Business Intelligence Assistant
"""

import os
import pytest
import database
import ai_service
from app import app


@pytest.fixture(scope="module")
def setup_test_db():
    """Initializes the database before running tests."""
    res = database.init_db(csv_path="sales_data.csv", db_path="test_sales.db")
    assert res["status"] == "success"
    yield "test_sales.db"
    # Cleanup test db after tests
    if os.path.exists("test_sales.db"):
        os.remove("test_sales.db")


@pytest.fixture
def client():
    """Provides a Flask test client."""
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


# --- 1. Edge Case & Data Cleaning Test ---
def test_data_cleaning_and_imputation(setup_test_db):
    """
    Edge case:
    1. Verify TXN0051 (Laptop Stand) has its missing unit_price imputed to 1200.0
    2. Verify TXN0033 is marked as 'Returned'
    3. Verify TXN0034 has quantity 0
    """
    db_path = setup_test_db

    # Check TXN0051 imputation
    res51 = database.execute_safe_query(
        "SELECT unit_price, quantity, revenue FROM sales WHERE transaction_id = 'TXN0051';",
        db_path=db_path
    )
    assert len(res51["rows"]) == 1
    assert res51["rows"][0]["unit_price"] == 1200.0
    assert res51["rows"][0]["revenue"] == 5 * 1200.0

    # Check TXN0033 Returned status
    res33 = database.execute_safe_query(
        "SELECT status FROM sales WHERE transaction_id = 'TXN0033';",
        db_path=db_path
    )
    assert res33["rows"][0]["status"] == "Returned"

    # Check TXN0034 zero quantity
    res34 = database.execute_safe_query(
        "SELECT quantity, revenue FROM sales WHERE transaction_id = 'TXN0034';",
        db_path=db_path
    )
    assert res34["rows"][0]["quantity"] == 0
    assert res34["rows"][0]["revenue"] == 0.0


# --- 2. Core Question 1: Total Revenue Test ---
def test_total_revenue_calculation(setup_test_db):
    """
    Validates total net revenue:
    - Excludes Returned transaction (TXN0033)
    - Subtracts discounts accurately
    Expected total = Rs. 1,445,200.00
    """
    db_path = setup_test_db
    q = "What is the total revenue?"
    processed = ai_service.process_question(q)
    assert processed["success"] is True

    res = database.execute_safe_query(processed["sql"], db_path=db_path)
    assert res["success"] is True
    total = res["rows"][0]["total_revenue"]
    assert total == 1445200.0

    answer = ai_service.generate_natural_answer(q, processed["sql"], res["rows"])
    assert "1,445,200.00" in answer


# --- 3. Core Question 2: Top Product Test ---
def test_highest_revenue_product(setup_test_db):
    """
    Validates highest revenue product:
    Expected: Monitor with Rs. 473,000.00
    """
    db_path = setup_test_db
    q = "Which product generated the highest revenue?"
    processed = ai_service.process_question(q)
    assert processed["success"] is True

    res = database.execute_safe_query(processed["sql"], db_path=db_path)
    assert res["success"] is True
    assert res["rows"][0]["product"] == "Monitor"
    assert res["rows"][0]["total_revenue"] == 473000.0

    answer = ai_service.generate_natural_answer(q, processed["sql"], res["rows"])
    assert "Monitor" in answer
    assert "473,000.00" in answer


# --- 4. Core Question 3: Monthly Trend Test ---
def test_monthly_revenue_trend(setup_test_db):
    """
    Validates that the monthly trend spans 6 months (Jan to Jun 2026) in chronological order.
    """
    db_path = setup_test_db
    q = "What is the monthly revenue trend?"
    processed = ai_service.process_question(q)
    assert processed["success"] is True

    res = database.execute_safe_query(processed["sql"], db_path=db_path)
    assert res["success"] is True
    assert len(res["rows"]) == 6
    months = [r["month"] for r in res["rows"]]
    assert months == ["2026-01", "2026-02", "2026-03", "2026-04", "2026-05", "2026-06"]


# --- 5. Core Question 4: Highest Region Test ---
def test_highest_region(setup_test_db):
    """
    Validates region with highest sales:
    Expected: South with Rs. 411,200.00
    """
    db_path = setup_test_db
    q = "Which region generated the highest sales?"
    processed = ai_service.process_question(q)
    assert processed["success"] is True

    res = database.execute_safe_query(processed["sql"], db_path=db_path)
    assert res["success"] is True
    assert res["rows"][0]["region"] == "South"
    assert res["rows"][0]["total_revenue"] == 411200.0


# --- 6. Core Question 5: Revenue Change Between Months Test ---
def test_revenue_change_between_months(setup_test_db):
    """
    Validates change between Jan 2026 (210,250) and Feb 2026 (234,600).
    Difference = +24,350.00
    """
    db_path = setup_test_db
    q = "How did revenue change between two months?"
    processed = ai_service.process_question(q)
    assert processed["success"] is True

    res = database.execute_safe_query(processed["sql"], db_path=db_path)
    assert res["success"] is True
    assert len(res["rows"]) == 2

    answer = ai_service.generate_natural_answer(q, processed["sql"], res["rows"])
    assert "increased" in answer
    assert "24,350.00" in answer


# --- 7. Security: SQL Injection & Destructive Query Blocking ---
def test_sql_validator_blocks_destructive_queries():
    """
    Verifies that the validator strictly rejects destructive SQL operations and multiple statements.
    """
    # 1. DROP TABLE attempt
    is_valid, err = ai_service.validate_sql_query("DROP TABLE sales;")
    assert is_valid is False
    assert "Security violation" in err

    # 2. DELETE FROM attempt
    is_valid, err = ai_service.validate_sql_query("DELETE FROM sales WHERE quantity = 0;")
    assert is_valid is False
    assert "Security violation" in err

    # 3. UPDATE attempt
    is_valid, err = ai_service.validate_sql_query("UPDATE sales SET revenue = 0;")
    assert is_valid is False
    assert "Security violation" in err

    # 4. Multi-statement injection: SELECT then DROP
    is_valid, err = ai_service.validate_sql_query("SELECT * FROM sales; DROP TABLE sales;")
    assert is_valid is False
    assert "Multiple SQL statements" in err


# --- 8. Invalid Questions / Error Handling ---
def test_invalid_questions_handling():
    """
    Verifies that empty questions or unanswerable requests return clean errors.
    """
    # Empty question
    res_empty = ai_service.process_question("")
    assert res_empty["success"] is False

    # Irrelevant / nonsensical question
    res_random = ai_service.process_question("What is the recipe for chocolate cake?")
    assert res_random["success"] is False
    assert "couldn't safely interpret" in res_random["error"]


# --- 9. Flask API Integration Test ---
def test_api_query_endpoint(client, setup_test_db):
    """
    Tests the POST /api/query API route with valid and invalid payloads.
    """
    # Valid question
    resp = client.post("/api/query", json={"question": "What is the total revenue?"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert "1,445,200.00" in data["answer"]
    assert len(data["rows"]) == 1

    # Empty payload
    resp_empty = client.post("/api/query", json={"question": ""})
    assert resp_empty.status_code == 400
    data_empty = resp_empty.get_json()
    assert data_empty["success"] is False


# --- 10. Product Ranking & Regional Breakdown Queries ---
def test_product_ranking_and_regional_sales(setup_test_db):
    """
    Tests queries for 'Product ranking' and 'Regional sales'.
    """
    db_path = setup_test_db

    # Test Product ranking
    q_prod = "Product ranking"
    p_prod = ai_service.process_question(q_prod)
    assert p_prod["success"] is True
    res_prod = database.execute_safe_query(p_prod["sql"], db_path=db_path)
    assert res_prod["success"] is True
    assert len(res_prod["rows"]) > 1
    assert res_prod["rows"][0]["product"] == "Monitor"

    # Test Regional sales
    q_reg = "Regional sales"
    p_reg = ai_service.process_question(q_reg)
    assert p_reg["success"] is True
    res_reg = database.execute_safe_query(p_reg["sql"], db_path=db_path)
    assert res_reg["success"] is True
    assert len(res_reg["rows"]) == 4


# --- 11. Dashboard Charts Endpoint Test ---
def test_api_charts_endpoint(client, setup_test_db):
    """
    Tests the GET /api/charts endpoint providing data for Chart.js.
    """
    resp = client.get("/api/charts")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert "monthly_trend" in data["data"]
    assert "product_sales" in data["data"]
    assert "regional_sales" in data["data"]
    assert len(data["data"]["monthly_trend"]["labels"]) == 6


# --- 12. Sales Channel NLP & Query Test ---
def test_sales_channel_query(client, setup_test_db):
    """
    Validates natural language questioning for sales channel performance:
    Expected: Online with Rs. 752,750.00 leads over Retail with Rs. 692,450.00.
    """
    db_path = setup_test_db
    q = "Which sales channel performs best?"
    processed = ai_service.process_question(q)
    assert processed["success"] is True

    res = database.execute_safe_query(processed["sql"], db_path=db_path)
    assert res["success"] is True
    assert len(res["rows"]) == 2
    assert res["rows"][0]["sales_channel"] == "Online"
    assert res["rows"][0]["total_revenue"] == 752750.0

    answer = ai_service.generate_natural_answer(q, processed["sql"], res["rows"])
    assert "Online" in answer
    assert "752,750.00" in answer


# --- 13. Dynamic Filtered Overview Test ---
def test_filtered_overview_endpoint(client, setup_test_db):
    """
    Tests GET /api/overview with filters (e.g. region=South):
    South region has 13 completed transactions, total revenue = 411,200.00.
    """
    resp = client.get("/api/overview?region=South")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert data["data"]["is_filtered"] is True
    assert data["data"]["total_net_revenue"] == 411200.0
    assert data["data"]["completed_transactions"] == 13


# --- 14. 4-Chart Datasets (including channel distribution) ---
def test_four_charts_endpoint(client, setup_test_db):
    """
    Verifies GET /api/charts returns all 4 required chart datasets:
    monthly_trend, product_sales, regional_sales, and channel_sales.
    """
    resp = client.get("/api/charts")
    assert resp.status_code == 200
    d = resp.get_json()["data"]
    assert "monthly_trend" in d
    assert "product_sales" in d
    assert "regional_sales" in d
    assert "channel_sales" in d
    assert d["channel_sales"]["labels"] == ["Online", "Retail"]
    assert d["channel_sales"]["values"] == [752750.0, 692450.0]


# --- 15. Transaction Table Endpoint (Search, Sort, Pagination) ---
def test_transactions_table_endpoint(client, setup_test_db):
    """
    Tests GET /api/transactions with search, sort, and pagination.
    """
    # Test pagination
    resp = client.get("/api/transactions?page=1&limit=10")
    assert resp.status_code == 200
    d = resp.get_json()["data"]
    assert len(d["transactions"]) == 10
    assert d["total_count"] == 51
    assert d["total_pages"] == 6

    # Test search query
    resp_search = client.get("/api/transactions?search=Monitor")
    assert resp_search.status_code == 200
    d_search = resp_search.get_json()["data"]
    assert all("Monitor" in t["product"] for t in d_search["transactions"])


# --- 16. Data Quality & Reliability Endpoint Test ---
def test_data_quality_endpoint(client, setup_test_db):
    """
    Tests GET /api/data-quality returns audit details and rules.
    """
    resp = client.get("/api/data-quality")
    assert resp.status_code == 200
    d = resp.get_json()["data"]
    assert d["total_source_records"] == 51
    assert d["valid_completed_records"] == 50
    assert d["flagged_returned_records"] == 1
    assert d["imputed_records"] == 1
    assert "TXN0051" in d["imputation_details"]
