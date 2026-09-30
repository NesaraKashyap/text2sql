import duckdb

from text2sql import DB_PATH

REV = "SUM(oi.quantity * oi.unit_price)"

FINAL = [
    # simple
    ("simple", "How many customers are from Brazil?",
     "SELECT COUNT(*) FROM customers WHERE country = 'Brazil'"),
    ("simple", "How many shipped orders are there?",
     "SELECT COUNT(*) FROM orders WHERE status = 'shipped'"),
    ("simple", "What is the price of the Coffee Maker?",
     "SELECT price FROM products WHERE product_name = 'Coffee Maker'"),
    ("simple", "List the product names in the Books category that cost less than 20 dollars.",
     "SELECT product_name FROM products WHERE category = 'Books' AND price < 20"),
    # aggregation
    ("aggregation", "What is the average price of Home products?",
     "SELECT ROUND(AVG(price), 2) FROM products WHERE category = 'Home'"),
    ("aggregation", "How many customers have placed more than 4 orders?",
     "SELECT COUNT(*) FROM (SELECT customer_id FROM orders GROUP BY customer_id "
     "HAVING COUNT(*) > 4)"),
    ("aggregation", "What is the highest product price in each category?",
     "SELECT category, MAX(price) FROM products GROUP BY category"),
    ("aggregation", "How many orders contain more than 2 line items?",
     "SELECT COUNT(*) FROM (SELECT order_id FROM order_items GROUP BY order_id "
     "HAVING COUNT(*) > 2)"),
    # join
    ("join", "How many orders were placed by customers from Australia?",
     "SELECT COUNT(*) FROM orders o JOIN customers c ON o.customer_id = c.customer_id "
     "WHERE c.country = 'Australia'"),
    ("join", "How many units of Desk Lamp have been sold?",
     "SELECT SUM(oi.quantity) FROM order_items oi "
     "JOIN products p ON oi.product_id = p.product_id WHERE p.product_name = 'Desk Lamp'"),
    ("join", "What is the revenue from Sports products?",
     f"SELECT {REV} FROM order_items oi JOIN orders o ON oi.order_id = o.order_id "
     "JOIN products p ON oi.product_id = p.product_id "
     "WHERE o.status = 'completed' AND p.category = 'Sports'"),
    ("join", "What is the average order value for shipped orders?",
     f"SELECT AVG(t) FROM (SELECT {REV} AS t FROM order_items oi "
     "JOIN orders o ON oi.order_id = o.order_id WHERE o.status = 'shipped' "
     "GROUP BY o.order_id)"),
    ("join", "How many orders did customers from the USA place in 2024?",
     "SELECT COUNT(*) FROM orders o JOIN customers c ON o.customer_id = c.customer_id "
     "WHERE c.country = 'USA' AND EXTRACT(YEAR FROM o.order_date) = 2024"),
    ("join", "What is the total quantity sold for each product category?",
     "SELECT p.category, SUM(oi.quantity) FROM order_items oi "
     "JOIN products p ON oi.product_id = p.product_id GROUP BY p.category"),
    # date
    ("date", "How many orders were placed in December 2024?",
     "SELECT COUNT(*) FROM orders WHERE EXTRACT(YEAR FROM order_date) = 2024 "
     "AND EXTRACT(MONTH FROM order_date) = 12"),
    ("date", "How many customers signed up in the first half of 2023?",
     "SELECT COUNT(*) FROM customers WHERE EXTRACT(YEAR FROM signup_date) = 2023 "
     "AND EXTRACT(MONTH FROM signup_date) <= 6"),
    ("date", "What was the revenue in 2025?",
     f"SELECT {REV} FROM order_items oi JOIN orders o ON oi.order_id = o.order_id "
     "WHERE o.status = 'completed' AND EXTRACT(YEAR FROM o.order_date) = 2025"),
    ("date", "How many orders were placed on or after 2025-01-01?",
     "SELECT COUNT(*) FROM orders WHERE order_date >= DATE '2025-01-01'"),
    # unanswerable
    ("unanswerable", "What is the average delivery time of an order?", None),
    ("unanswerable", "How many employees work at the company?", None),
    ("unanswerable", "Which customers are subscribed to the newsletter?", None),
    ("unanswerable", "What is the average weight of a product?", None),
    ("unanswerable", "What payment method did customer 5 use?", None),
    ("unanswerable", "Which warehouse ships the most orders?", None),
]

if __name__ == "__main__":
    con = duckdb.connect(DB_PATH, read_only=True)
    ok = total = 0
    for category, question, sql in FINAL:
        if sql is None:
            continue
        total += 1
        try:
            con.execute(sql).df()
            ok += 1
        except Exception as e:
            print(f"BROKEN: {question}\n  {e}")
    print(f"{ok}/{total} final-set golden queries run OK. {len(FINAL)} questions total.")