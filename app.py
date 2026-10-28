"""
app.py
------
Flask Application providing:
1. Static web UI serving (Glassmorphism Dashboard)
2. REST API endpoints for natural language questions (Vectorless RAG)
3. Dynamic multi-dimensional filtering for KPIs, charts, and transaction table
4. Data quality auditing and cleaning logs

Author: Senior Full-Stack Engineer / Student Developer
Project: Sales Insight Assistant
"""

import os
from flask import Flask, jsonify, request, send_from_directory
import database
import ai_service

app = Flask(__name__, static_folder="static", static_url_path="")


def extract_filter_params():
    """Extracts standard filter query parameters from incoming request."""
    return {
        "month": request.args.get("month", "").strip(),
        "product": request.args.get("product", "").strip(),
        "region": request.args.get("region", "").strip(),
        "sales_channel": request.args.get("sales_channel", "") or request.args.get("channel", "").strip(),
        "status": request.args.get("status", "").strip()
    }


@app.route("/")
def serve_index():
    """Serves the frontend single-page dashboard."""
    return send_from_directory("static", "index.html")


@app.route("/api/filter-options", methods=["GET"])
def get_filter_options():
    """Returns dynamic lists of available months, products, regions, and channels for dropdowns."""
    try:
        options = database.get_filter_options()
        return jsonify({
            "success": True,
            "data": options
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route("/api/overview", methods=["GET"])
def get_overview():
    """Returns dataset summary metrics and 4 KPI cards (filtered dynamically)."""
    try:
        filters = extract_filter_params()
        overview = database.get_dataset_overview(filters=filters)
        return jsonify({
            "success": True,
            "data": overview
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route("/api/charts", methods=["GET"])
def get_charts():
    """Returns aggregated data for 4 Chart.js charts (monthly, product, region, channel)."""
    try:
        filters = extract_filter_params()
        chart_data = database.get_chart_data(filters=filters)
        return jsonify({
            "success": True,
            "data": chart_data
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route("/api/transactions", methods=["GET"])
def get_transactions():
    """
    Returns paginated, searchable, and sortable transaction records
    filtered by user selections.
    """
    try:
        filters = extract_filter_params()
        search = request.args.get("search", "").strip()
        sort_col = request.args.get("sort", "order_date").strip()
        sort_order = request.args.get("order", "DESC").strip()
        page = int(request.args.get("page", 1))
        limit = int(request.args.get("limit", 10))

        result = database.get_transactions(
            filters=filters,
            search=search,
            sort_col=sort_col,
            sort_order=sort_order,
            page=page,
            limit=limit
        )
        return jsonify({
            "success": True,
            "data": result
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route("/api/data-quality", methods=["GET"])
def get_data_quality():
    """Returns data reliability metrics, cleaning audit logs, and business rules."""
    try:
        report = database.get_data_quality_report()
        return jsonify({
            "success": True,
            "data": report
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route("/api/sample-data", methods=["GET"])
def get_sample_data():
    """Preserved endpoint: Returns the first 10 rows of the cleaned sales table."""
    try:
        res = database.execute_safe_query("SELECT * FROM sales LIMIT 10;")
        return jsonify({
            "success": True,
            "columns": res["columns"],
            "rows": res["rows"]
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route("/api/query", methods=["POST"])
def handle_query():
    """
    Natural language analytical querying endpoint.
    Translates user questions into validated SQLite queries,
    executes them, and returns plain-English answers with supporting data.
    """
    data = request.get_json(silent=True) or {}
    question = data.get("question", "").strip()

    if not question:
        return jsonify({
            "success": False,
            "error": "Please enter a question to analyze."
        }), 400

    # 1. Translate question to SQL via AI service
    ai_result = ai_service.process_question(question)
    if not ai_result.get("success"):
        return jsonify({
            "success": False,
            "question": question,
            "error": ai_result.get("error", "Unable to interpret question."),
            "mode": ai_result.get("mode", "Unknown")
        }), 400

    sql_query = ai_result["sql"]
    explanation = ai_result["explanation"]
    mode = ai_result["mode"]

    # 2. Execute validated query on SQLite
    db_result = database.execute_safe_query(sql_query)
    if not db_result.get("success"):
        return jsonify({
            "success": False,
            "question": question,
            "sql": sql_query,
            "error": f"Database execution error: {db_result.get('error')}",
            "mode": mode
        }), 500

    rows = db_result["rows"]
    columns = db_result["columns"]

    # 3. Generate plain-English natural language answer
    answer = ai_service.generate_natural_answer(question, sql_query, rows)

    return jsonify({
        "success": True,
        "question": question,
        "mode": mode,
        "sql": sql_query,
        "explanation": explanation,
        "answer": answer,
        "columns": columns,
        "rows": rows,
        "row_count": len(rows)
    })


if __name__ == "__main__":
    print("[SYSTEM] Initializing database from sales_data.csv...")
    init_res = database.init_db()
    print(f"[SYSTEM] Database ready: {init_res['total_records_inserted']} records loaded.")
    for log in init_res.get("cleaning_logs", []):
        print(f"  -> {log}")

    port = int(os.environ.get("PORT", 5000))
    print(f"[SYSTEM] Starting server on http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=False)
