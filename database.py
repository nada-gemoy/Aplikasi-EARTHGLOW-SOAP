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
            total INTEGER DEFAULT 0,
            status TEXT DEFAULT 'Pending'
        )
    """)

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