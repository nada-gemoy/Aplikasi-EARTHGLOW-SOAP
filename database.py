import sqlite3

DATABASE_NAME = "earthglow.db"


def connect_db():
    return sqlite3.connect(DATABASE_NAME)


def create_tables():
    conn = connect_db()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            brand TEXT,
            price INTEGER NOT NULL DEFAULT 0,
            description TEXT,
            stock INTEGER DEFAULT 0,
            image TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_name TEXT,
            customer_address TEXT,
            product_name TEXT,
            quantity INTEGER DEFAULT 0,
            total INTEGER DEFAULT 0,
            payment_method TEXT DEFAULT 'Cash',
            status TEXT DEFAULT 'Belum Lunas',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("PRAGMA table_info(orders)")
    order_columns = {row[1] for row in cursor.fetchall()}

    for column_name, default_sql in {
        "customer_name": "ALTER TABLE orders ADD COLUMN customer_name TEXT",
        "customer_address": "ALTER TABLE orders ADD COLUMN customer_address TEXT",
        "product_name": "ALTER TABLE orders ADD COLUMN product_name TEXT",
        "quantity": "ALTER TABLE orders ADD COLUMN quantity INTEGER DEFAULT 0",
        "total": "ALTER TABLE orders ADD COLUMN total INTEGER DEFAULT 0",
        "payment_method": "ALTER TABLE orders ADD COLUMN payment_method TEXT DEFAULT 'Cash'",
        "status": "ALTER TABLE orders ADD COLUMN status TEXT DEFAULT 'Belum Lunas'",
        "created_at": "ALTER TABLE orders ADD COLUMN created_at TEXT",
    }.items():
        if column_name not in order_columns:
            cursor.execute(default_sql)

    cursor.execute(
        "UPDATE orders SET created_at = CURRENT_TIMESTAMP "
        "WHERE created_at IS NULL OR created_at = ''"
    )
    cursor.execute(
        "UPDATE orders SET status = 'Lunas' WHERE status IN ('Lunas', 'lunas', 'Paid', 'paid')"
    )
    cursor.execute(
        "UPDATE orders SET status = 'Belum Lunas' WHERE status IS NULL OR status = ''"
    )

    conn.commit()
    conn.close()


def get_products():
    conn = connect_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, name, brand, price, description, stock, image
        FROM products
        ORDER BY id DESC
    """)

    data = cursor.fetchall()
    conn.close()
    return data


def get_order_count():
    conn = connect_db()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM orders")
    result = cursor.fetchone()[0]

    conn.close()
    return result


def get_orders():
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, customer_name, customer_address, product_name, quantity, total, payment_method, status, created_at
        FROM orders
        ORDER BY id DESC
    """)
    data = cursor.fetchall()
    conn.close()
    return data


def add_order(customer_name, customer_address, product_name, quantity, total, payment_method='Cash', status='Lunas'):
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO orders (customer_name, customer_address, product_name, quantity, total, payment_method, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now', 'localtime'))
    """, (customer_name, customer_address, product_name, quantity, total, payment_method, status))
    conn.commit()
    conn.close()


def get_financial_summary():
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT COUNT(*), COALESCE(SUM(total), 0)
        FROM orders
        WHERE status = 'Lunas'
    """)
    total_transactions, total_revenue = cursor.fetchone()
    cursor.execute("""
        SELECT COALESCE(SUM(total), 0)
        FROM orders
        WHERE status = 'Lunas'
          AND date(created_at) = date('now', 'localtime')
    """)
    today_revenue = cursor.fetchone()[0]
    conn.close()
    return total_transactions, total_revenue, today_revenue


def add_product(name, brand, price, description, stock, image=""):
    conn = connect_db()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO products
        (name, brand, price, description, stock, image)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (name, brand, price, description, stock, image))

    conn.commit()
    conn.close()


def update_product(product_id, name, brand, price, description, stock, image=""):
    conn = connect_db()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE products
        SET name=?, brand=?, price=?, description=?, stock=?, image=?
        WHERE id=?
    """, (name, brand, price, description, stock, image, product_id))

    conn.commit()
    conn.close()


def delete_product(product_id):
    conn = connect_db()
    cursor = conn.cursor()

    cursor.execute(
        "DELETE FROM products WHERE id=?",
        (product_id,)
    )

    conn.commit()
    conn.close()