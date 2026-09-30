import duckdb

from text2sql import DB_PATH

REV = "SUM(oi.quantity * oi.unit_price)"

# Same format as the golden set. SQL = None means "cannot be answered".
HELDOUT = [
    ("simple", "How many refunded orders are there?",
     "SELECT COUNT(*) FROM orders WHERE status = 'refunded'"),
    ("simple", "How many distinct products have been ordered at least once?",
     "SELECT COUNT(DISTINCT product_id) FROM order_items"),
    ("aggregation", "What is the average price of Electronics products?",
     "SELECT ROUND(AVG(price), 2) FROM products WHERE category = 'Electronics'"),
    ("aggregation", "What is the average number of line items per order?",
     "SELECT AVG(c) FROM (SELECT COUNT(*) AS c FROM order_items GROUP BY order_id)"),
    ("aggregation", "How many customers have placed more than 5 orders?",
     "SELECT COUNT(*) FROM (SELECT customer_id FROM orders "
     "GROUP BY customer_id HAVING COUNT(*) > 5)"),
    ("join", "How many orders were placed by customers from the UK?",
     "SELECT COUNT(*) FROM orders o JOIN customers c ON o.customer_id = c.customer_id "
     "WHERE c.country = 'UK'"),
    ("join", "How many units of Running Shoes have been sold?",
     "SELECT SUM(oi.quantity) FROM order_items oi "
     "JOIN products p ON oi.product_id = p.product_id WHERE p.product_name = 'Running Shoes'"),
    ("join", "What is the total revenue from Canadian customers?",
     f"SELECT {REV} FROM order_items oi JOIN orders o ON oi.order_id = o.order_id "
     "JOIN customers c ON o.customer_id = c.customer_id "
     "WHERE o.status = 'completed' AND c.country = 'Canada'"),
    ("join", "What is the average order value across all orders, regardless of status?",
     "SELECT AVG(t) FROM (SELECT SUM(quantity * unit_price) AS t FROM order_items GROUP BY order_id)"),
    ("date", "How many customers signed up in 2024?",
     "SELECT COUNT(*) FROM customers WHERE EXTRACT(YEAR FROM signup_date) = 2024"),
    ("date", "How many orders were placed in June 2025?",
     "SELECT COUNT(*) FROM orders WHERE EXTRACT(YEAR FROM order_date) = 2025 "
     "AND EXTRACT(MONTH FROM order_date) = 6"),
    ("unanswerable", "How many products are out of stock?", None),
    ("unanswerable", "What is the average customer rating of each product?", None),
    ("unanswerable", "What city does each customer live in?", None),
    ("unanswerable", "What is the total discount given on all orders?", None),
]

if __name__ == "__main__":
    con = duckdb.connect(DB_PATH, read_only=True)
    ok = 0
    total = 0
    for category, question, sql in HELDOUT:
        if sql is None:
            continue
        total += 1
        try:
            con.execute(sql).df()
            ok += 1
        except Exception as e:
            print(f"BROKEN: {question}\n  {e}")
    print(f"{ok}/{total} held-out golden queries run OK. {len(HELDOUT)} questions total.")