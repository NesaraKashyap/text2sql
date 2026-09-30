import random
from datetime import date, timedelta

import duckdb

# A fixed seed means we get the same "random" data every time,
# which makes our tests repeatable later.
random.seed(42)

# This creates (or opens) a database file called store.duckdb
con = duckdb.connect("store.duckdb")

# Remove old tables if we re-run this script (child tables first)
for table in ["order_items", "orders", "products", "customers"]:
    con.execute(f"DROP TABLE IF EXISTS {table}")

# ---------- Create the tables ----------
con.execute("""
CREATE TABLE customers (
    customer_id INTEGER PRIMARY KEY,
    first_name VARCHAR,
    last_name VARCHAR,
    email VARCHAR,
    country VARCHAR,
    signup_date DATE
)
""")

con.execute("""
CREATE TABLE products (
    product_id INTEGER PRIMARY KEY,
    product_name VARCHAR,
    category VARCHAR,
    price DECIMAL(10,2)
)
""")

con.execute("""
CREATE TABLE orders (
    order_id INTEGER PRIMARY KEY,
    customer_id INTEGER REFERENCES customers(customer_id),
    order_date DATE,
    status VARCHAR
)
""")

con.execute("""
CREATE TABLE order_items (
    order_item_id INTEGER PRIMARY KEY,
    order_id INTEGER REFERENCES orders(order_id),
    product_id INTEGER REFERENCES products(product_id),
    quantity INTEGER,
    unit_price DECIMAL(10,2)
)
""")

# ---------- Fill customers ----------
first_names = ["Aarav", "Priya", "John", "Emma", "Liam", "Sofia", "Wei", "Mei",
               "Carlos", "Anna", "Omar", "Fatima", "Noah", "Olivia", "Ravi", "Sara"]
last_names = ["Sharma", "Smith", "Garcia", "Chen", "Khan", "Brown", "Patel",
              "Muller", "Silva", "Kim", "Johnson", "Rossi"]
countries = ["India", "USA", "UK", "Germany", "Brazil", "Canada", "Australia"]

customers = []
for i in range(1, 201):
    fn = random.choice(first_names)
    ln = random.choice(last_names)
    signup = date(2023, 1, 1) + timedelta(days=random.randint(0, 700))
    customers.append((i, fn, ln, f"{fn.lower()}.{ln.lower()}{i}@example.com",
                      random.choice(countries), signup))
con.executemany("INSERT INTO customers VALUES (?, ?, ?, ?, ?, ?)", customers)

# ---------- Fill products ----------
products = [
    (1, "Wireless Mouse", "Electronics", 24.99),
    (2, "Mechanical Keyboard", "Electronics", 89.50),
    (3, "USB-C Hub", "Electronics", 39.99),
    (4, "Noise Cancelling Headphones", "Electronics", 199.00),
    (5, "Webcam HD", "Electronics", 59.00),
    (6, "Running Shoes", "Sports", 79.99),
    (7, "Yoga Mat", "Sports", 25.00),
    (8, "Dumbbell Set", "Sports", 120.00),
    (9, "Water Bottle", "Sports", 14.50),
    (10, "Cycling Helmet", "Sports", 55.00),
    (11, "Python Programming Book", "Books", 35.00),
    (12, "Data Science Handbook", "Books", 42.00),
    (13, "Mystery Novel", "Books", 12.99),
    (14, "Cookbook", "Books", 22.50),
    (15, "Science Fiction Anthology", "Books", 16.00),
    (16, "Desk Lamp", "Home", 29.99),
    (17, "Coffee Maker", "Home", 74.00),
    (18, "Throw Blanket", "Home", 34.50),
    (19, "Air Purifier", "Home", 149.00),
    (20, "Bookshelf", "Home", 110.00),
    (21, "T-Shirt", "Clothing", 19.99),
    (22, "Jeans", "Clothing", 49.99),
    (23, "Winter Jacket", "Clothing", 129.00),
    (24, "Sneakers", "Clothing", 64.99),
]
con.executemany("INSERT INTO products VALUES (?, ?, ?, ?)", products)

# ---------- Fill orders and order_items ----------
statuses = ["completed", "completed", "completed", "completed",
            "shipped", "pending", "cancelled", "refunded"]
price_lookup = {p[0]: p[3] for p in products}

orders = []
items = []
item_id = 1
for order_id in range(1, 1001):
    customer_id = random.randint(1, 200)
    order_date = date(2024, 1, 1) + timedelta(days=random.randint(0, 545))
    orders.append((order_id, customer_id, order_date, random.choice(statuses)))
    for _ in range(random.randint(1, 4)):
        pid = random.randint(1, 24)
        items.append((item_id, order_id, pid, random.randint(1, 3), price_lookup[pid]))
        item_id += 1

con.executemany("INSERT INTO orders VALUES (?, ?, ?, ?)", orders)
con.executemany("INSERT INTO order_items VALUES (?, ?, ?, ?, ?)", items)

# ---------- Quick check ----------
for table in ["customers", "products", "orders", "order_items"]:
    count = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    print(f"{table}: {count} rows")

print("\nRevenue by category (completed orders only):")
print(con.execute("""
    SELECT p.category, ROUND(SUM(oi.quantity * oi.unit_price), 2) AS revenue
    FROM order_items oi
    JOIN orders o ON oi.order_id = o.order_id
    JOIN products p ON oi.product_id = p.product_id
    WHERE o.status = 'completed'
    GROUP BY p.category
    ORDER BY revenue DESC
""").df())

con.close()