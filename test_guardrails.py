from guardrails import check_sql

# (query, should it be allowed?)
CASES = [
    ("SELECT * FROM customers", True),
    ("SELECT country, COUNT(*) FROM customers GROUP BY country LIMIT 5", True),
    ("SELECT * FROM products WHERE product_name = 'Update Kit'", True),
    ("WITH t AS (SELECT * FROM orders) SELECT COUNT(*) FROM t", True),
    ("DROP TABLE customers", False),
    ("DELETE FROM orders WHERE order_id = 1", False),
    ("UPDATE products SET price = 0", False),
    ("INSERT INTO customers VALUES (1,'a','b','c','d','2024-01-01')", False),
    ("CREATE TABLE hacked (x INT)", False),
    ("ALTER TABLE products ADD COLUMN x INT", False),
    ("SELECT 1; DROP TABLE customers", False),
    ("SELECT * FROM customers -- hidden", False),
    ("SELECT * FROM read_csv('C:/Windows/win.ini')", False),
    ("SELECT * FROM 'secrets.csv'", False),
    ("COPY customers TO 'out.csv'", False),
    ("ATTACH 'other.db' AS x", False),
    ("PRAGMA database_list", False),
    ("SELECT * FROM (SELECT * FROM (SELECT * FROM (SELECT * FROM (SELECT * FROM customers))))", False),
]

passed = 0
for sql, should_allow in CASES:
    result = check_sql(sql)
    ok = result["allowed"] == should_allow
    passed += ok
    status = "PASS" if ok else "FAIL"
    print(f"[{status}] allowed={result['allowed']!s:5}  {sql[:70]}")

print(f"\n{passed}/{len(CASES)} guardrail tests passed")

# Row limit checks
print("\nRow limit checks:")
print(check_sql("SELECT * FROM orders")["sql"])
print(check_sql("SELECT * FROM orders LIMIT 999999")["sql"])
print(check_sql("SELECT * FROM orders LIMIT 10")["sql"])