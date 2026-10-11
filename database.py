import sqlite3

DATABASE_NAME = "earthglow.db"


def connect_db():
    return sqlite3.connect(DATABASE_NAME)


def create_tables():
    conn = connect_db()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS admins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            store_name TEXT,
            profile_photo TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            brand TEXT,
            price INTEGER NOT NULL DEFAULT 0,
            cost_price INTEGER,
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
            cost_total INTEGER,
            payment_method TEXT DEFAULT 'Cash',
            status TEXT DEFAULT 'Belum Lunas',
            channel TEXT NOT NULL DEFAULT 'online',
            platform TEXT,
            buyer_note TEXT,
            completed_at TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            product_id INTEGER,
            product_name TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            unit_price INTEGER NOT NULL,
            unit_cost INTEGER,
            FOREIGN KEY (order_id) REFERENCES orders(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS returns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            order_item_id INTEGER NOT NULL,
            channel TEXT NOT NULL,
            customer_name TEXT,
            returned_product TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            complaint TEXT NOT NULL,
            returned_price INTEGER NOT NULL,
            returned_cost INTEGER,
            resolution TEXT NOT NULL,
            refund_amount INTEGER NOT NULL DEFAULT 0,
            replacement_product TEXT,
            replacement_cost INTEGER NOT NULL DEFAULT 0,
            loss_amount INTEGER NOT NULL DEFAULT 0,
            profit_loss INTEGER,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (order_id) REFERENCES orders(id),
            FOREIGN KEY (order_item_id) REFERENCES order_items(id)
        )
    """)

    cursor.execute(
        "SELECT id FROM admins WHERE email = ?",
        ("admin@earthglow.com",)
    )
    if cursor.fetchone() is None:
        cursor.execute(
            """
            INSERT INTO admins (name, email, password, store_name, profile_photo)
            VALUES (?, ?, ?, ?, ?)
            """,
            ("EarthGlow Admin", "admin@earthglow.com", "admin123", "EarthGlow Soap", "")
        )

    cursor.execute("PRAGMA table_info(orders)")
    order_columns = {row[1] for row in cursor.fetchall()}
    for column_name, default_sql in {
        "platform": "ALTER TABLE orders ADD COLUMN platform TEXT",
        "buyer_note": "ALTER TABLE orders ADD COLUMN buyer_note TEXT",
        "completed_at": "ALTER TABLE orders ADD COLUMN completed_at TEXT",
    }.items():
        if column_name not in order_columns:
            cursor.execute(default_sql)

    cursor.execute("PRAGMA table_info(products)")
    product_columns = {row[1] for row in cursor.fetchall()}
    if "cost_price" not in product_columns:
        cursor.execute("ALTER TABLE products ADD COLUMN cost_price INTEGER")

    for column_name, default_sql in {
        "customer_name": "ALTER TABLE orders ADD COLUMN customer_name TEXT",
        "customer_address": "ALTER TABLE orders ADD COLUMN customer_address TEXT",
        "product_name": "ALTER TABLE orders ADD COLUMN product_name TEXT",
        "quantity": "ALTER TABLE orders ADD COLUMN quantity INTEGER DEFAULT 0",
        "total": "ALTER TABLE orders ADD COLUMN total INTEGER DEFAULT 0",
        "cost_total": "ALTER TABLE orders ADD COLUMN cost_total INTEGER",
        "payment_method": "ALTER TABLE orders ADD COLUMN payment_method TEXT DEFAULT 'Cash'",
        "status": "ALTER TABLE orders ADD COLUMN status TEXT DEFAULT 'Belum Lunas'",
        "channel": "ALTER TABLE orders ADD COLUMN channel TEXT NOT NULL DEFAULT 'online'",
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
    cursor.execute(
        "UPDATE orders SET completed_at = created_at "
        "WHERE status = 'Lunas' AND completed_at IS NULL"
    )

    conn.commit()
    conn.close()


def get_products():
    conn = connect_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, name, brand, price, description, stock, image, cost_price
        FROM products
        ORDER BY id DESC
    """)

    data = cursor.fetchall()
    conn.close()
    return data


def get_order_count(channel=None):
    conn = connect_db()
    cursor = conn.cursor()

    if channel is None:
        cursor.execute("SELECT COUNT(*) FROM orders")
    else:
        cursor.execute("SELECT COUNT(*) FROM orders WHERE channel = ?", (channel,))
    result = cursor.fetchone()[0]

    conn.close()
    return result


def get_new_online_order_count():
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT COUNT(*) FROM orders WHERE channel = 'online' AND status = 'Baru'"
    )
    result = cursor.fetchone()[0]
    conn.close()
    return result


def get_orders(channel=None):
    conn = connect_db()
    cursor = conn.cursor()
    query = """
        SELECT id, customer_name, customer_address, product_name, quantity, total,
               payment_method, status, created_at, cost_total, channel
        FROM orders
    """
    parameters = ()
    if channel is not None:
        query += " WHERE channel = ?"
        parameters = (channel,)
    query += " ORDER BY id DESC"
    cursor.execute(query, parameters)
    data = cursor.fetchall()
    conn.close()
    return data


def get_order_metadata(order_id):
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT platform, buyer_note FROM orders WHERE id = ?",
        (order_id,),
    )
    metadata = cursor.fetchone()
    conn.close()
    if metadata is None:
        raise ValueError("Pesanan tidak ditemukan.")
    return metadata


def update_order_status(order_id, expected_status, new_status, channel="online"):
    transitions = {
        "Baru": "Diproses",
        "Diproses": "Siap",
        "Siap": "Lunas",
    }
    if transitions.get(expected_status) != new_status:
        raise ValueError("Perubahan status pesanan tidak valid.")

    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("BEGIN IMMEDIATE")
    cursor.execute(
        "SELECT status FROM orders WHERE id = ? AND channel = ?",
        (order_id, channel),
    )
    current = cursor.fetchone()
    if current is None:
        conn.rollback()
        conn.close()
        raise ValueError("Pesanan tidak ditemukan.")
    if current[0] != expected_status:
        conn.rollback()
        conn.close()
        raise ValueError("Status pesanan sudah berubah. Muat ulang daftar pesanan.")
    cursor.execute(
        (
            "UPDATE orders SET status = ?, completed_at = "
            "CASE WHEN ? = 'Lunas' THEN datetime('now', 'localtime') "
            "ELSE completed_at END "
            "WHERE id = ? AND channel = ? AND status = ?"
        ),
        (new_status, new_status, order_id, channel, expected_status),
    )
    if cursor.rowcount != 1:
        conn.rollback()
        conn.close()
        raise ValueError("Status pesanan gagal diperbarui.")
    conn.commit()
    conn.close()


def add_order(
    customer_name,
    customer_address,
    product_name,
    quantity,
    total,
    payment_method='Cash',
    status='Lunas',
    cost_total=None,
    channel='online',
    items=None,
    platform=None,
    buyer_note="",
):
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("BEGIN")
    for item in items or ():
        cursor.execute(
            "SELECT stock FROM products WHERE id = ?",
            (item["product_id"],),
        )
        product_stock = cursor.fetchone()
        if product_stock is None or (product_stock[0] or 0) < item["quantity"]:
            conn.rollback()
            conn.close()
            raise ValueError(f"Stok {item['product_name']} tidak mencukupi.")
    cursor.execute("""
        INSERT INTO orders (
            customer_name, customer_address, product_name, quantity, total,
            cost_total, payment_method, status, channel, platform, buyer_note,
            completed_at, created_at
        )
        VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
            CASE WHEN ? = 'Lunas' THEN datetime('now', 'localtime') ELSE NULL END,
            datetime('now', 'localtime')
        )
    """, (
        customer_name,
        customer_address,
        product_name,
        quantity,
        total,
        cost_total,
        payment_method,
        status,
        channel,
        platform,
        buyer_note,
        status,
    ))
    order_id = cursor.lastrowid
    for item in items or ():
        cursor.execute(
            "UPDATE products SET stock = stock - ? WHERE id = ?",
            (item["quantity"], item["product_id"]),
        )
        cursor.execute("""
            INSERT INTO order_items (
                order_id, product_id, product_name, quantity, unit_price, unit_cost
            ) VALUES (?, ?, ?, ?, ?, ?)
        """, (
            order_id,
            item["product_id"],
            item["product_name"],
            item["quantity"],
            item["unit_price"],
            item["unit_cost"],
        ))
    conn.commit()
    conn.close()
    return order_id


def get_order_items(order_id):
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT items.id, items.product_id, items.product_name, items.quantity,
               items.unit_price, items.unit_cost,
               COALESCE(SUM(returns.quantity), 0) AS returned_quantity
        FROM order_items AS items
        LEFT JOIN returns ON returns.order_item_id = items.id
        WHERE items.order_id = ?
        GROUP BY items.id
        ORDER BY items.id
    """, (order_id,))
    items = cursor.fetchall()
    if not items:
        cursor.execute("""
            SELECT orders.product_name, orders.quantity, orders.total, orders.cost_total,
                   products.id, products.name, products.price
            FROM orders
            LEFT JOIN products ON products.name = orders.product_name
            WHERE orders.id = ?
        """, (order_id,))
        legacy = cursor.fetchone()
        if legacy and legacy[4] is not None and legacy[1]:
            _, quantity, total, cost_total, product_id, name, price = legacy
            unit_price = total // quantity if quantity else price
            unit_cost = (
                cost_total // quantity
                if cost_total is not None and quantity
                else None
            )
            cursor.execute("""
                INSERT INTO order_items (
                    order_id, product_id, product_name, quantity, unit_price, unit_cost
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (order_id, product_id, name, quantity, unit_price, unit_cost))
            conn.commit()
            cursor.execute("""
                SELECT items.id, items.product_id, items.product_name, items.quantity,
                       items.unit_price, items.unit_cost, 0
                FROM order_items AS items
                WHERE items.order_id = ?
            """, (order_id,))
            items = cursor.fetchall()
    conn.close()
    return items


def add_return(order_id, order_item_id, quantity, complaint, resolution, replacement_product_id=None):
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("BEGIN IMMEDIATE")
    cursor.execute("""
        SELECT orders.channel, orders.customer_name, orders.status,
               items.product_id, items.product_name, items.quantity,
               items.unit_price, items.unit_cost,
               COALESCE(SUM(returns.quantity), 0)
        FROM orders
        JOIN order_items AS items ON items.order_id = orders.id
        LEFT JOIN returns ON returns.order_item_id = items.id
        WHERE orders.id = ? AND items.id = ?
        GROUP BY items.id
    """, (order_id, order_item_id))
    item = cursor.fetchone()
    if item is None:
        conn.rollback()
        conn.close()
        raise ValueError("Detail produk pada transaksi ini tidak ditemukan.")

    channel, customer, status, product_id, product_name, sold_quantity, unit_price, unit_cost, returned_quantity = item
    if status != "Lunas":
        conn.rollback()
        conn.close()
        raise ValueError("Retur hanya dapat diproses untuk transaksi yang sudah lunas.")
    if quantity <= 0 or quantity > sold_quantity - returned_quantity:
        conn.rollback()
        conn.close()
        raise ValueError("Jumlah retur melebihi jumlah barang yang masih dapat diretur.")
    if not complaint.strip():
        conn.rollback()
        conn.close()
        raise ValueError("Keluhan wajib diisi.")
    if resolution not in ("Uang kembali", "Kirim pengganti"):
        conn.rollback()
        conn.close()
        raise ValueError("Pilih uang kembali atau kirim barang pengganti.")

    returned_price = unit_price * quantity
    returned_cost = unit_cost * quantity if unit_cost is not None else None
    refund_amount = 0
    replacement_name = None
    replacement_cost = 0

    if resolution == "Uang kembali":
        refund_amount = returned_price
        profit_loss = returned_price - returned_cost if returned_cost is not None else None
        loss_amount = refund_amount
    else:
        if replacement_product_id is None:
            conn.rollback()
            conn.close()
            raise ValueError("Pilih barang pengganti.")
        cursor.execute("""
            SELECT name, stock, cost_price
            FROM products
            WHERE id = ?
        """, (replacement_product_id,))
        replacement = cursor.fetchone()
        if replacement is None:
            conn.rollback()
            conn.close()
            raise ValueError("Produk pengganti tidak ditemukan.")
        replacement_name, replacement_stock, replacement_unit_cost = replacement
        available_replacement_stock = replacement_stock
        if replacement_product_id == product_id:
            available_replacement_stock += quantity
        if available_replacement_stock < quantity:
            conn.rollback()
            conn.close()
            raise ValueError("Stok barang pengganti tidak mencukupi.")
        if replacement_unit_cost is None:
            conn.rollback()
            conn.close()
            raise ValueError("Isi HPP barang pengganti sebelum memproses retur.")
        replacement_cost = replacement_unit_cost * quantity
        profit_loss = (
            max(replacement_cost - returned_cost, 0)
            if returned_cost is not None
            else replacement_cost
        )
        loss_amount = replacement_cost
        cursor.execute(
            "UPDATE products SET stock = stock - ? WHERE id = ?",
            (quantity, replacement_product_id),
        )

    if product_id is not None:
        cursor.execute(
            "UPDATE products SET stock = stock + ? WHERE id = ?",
            (quantity, product_id),
        )

    cursor.execute("""
        INSERT INTO returns (
            order_id, order_item_id, channel, customer_name, returned_product,
            quantity, complaint, returned_price, returned_cost, resolution,
            refund_amount, replacement_product, replacement_cost, loss_amount,
            profit_loss, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now', 'localtime'))
    """, (
        order_id,
        order_item_id,
        channel,
        customer,
        product_name,
        quantity,
        complaint.strip(),
        returned_price,
        returned_cost,
        resolution,
        refund_amount,
        replacement_name,
        replacement_cost,
        loss_amount,
        profit_loss,
    ))
    conn.commit()
    conn.close()


def get_returns(channel=None):
    conn = connect_db()
    cursor = conn.cursor()
    query = """
        SELECT id, order_id, channel, customer_name, returned_product, quantity,
               complaint, returned_price, returned_cost, resolution, refund_amount,
               replacement_product, replacement_cost, loss_amount, profit_loss, created_at
        FROM returns
    """
    parameters = ()
    if channel is not None:
        query += " WHERE channel = ?"
        parameters = (channel,)
    query += " ORDER BY id DESC"
    cursor.execute(query, parameters)
    data = cursor.fetchall()
    conn.close()
    return data


def get_channel_financial_summary(channel):
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT COUNT(*), COALESCE(SUM(total), 0),
               COALESCE(SUM(CASE WHEN cost_total IS NOT NULL THEN total - cost_total ELSE 0 END), 0),
               COALESCE(SUM(CASE WHEN cost_total IS NULL THEN 1 ELSE 0 END), 0)
        FROM orders
        WHERE status = 'Lunas' AND channel = ?
    """, (channel,))
    count, revenue, gross_profit, orders_without_cost = cursor.fetchone()
    cursor.execute("""
        SELECT COALESCE(SUM(refund_amount), 0),
               COALESCE(SUM(loss_amount), 0),
               COALESCE(SUM(profit_loss), 0),
               COALESCE(SUM(CASE WHEN profit_loss IS NULL THEN 1 ELSE 0 END), 0)
        FROM returns
        WHERE channel = ?
    """, (channel,))
    refunds, return_loss, return_profit_loss, unknown_return_profit = cursor.fetchone()
    conn.close()
    return (
        count,
        revenue,
        gross_profit,
        orders_without_cost,
        refunds,
        return_loss,
        return_profit_loss,
        unknown_return_profit,
    )


def get_financial_summary():
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT COUNT(*), COALESCE(SUM(total), 0),
               COALESCE(SUM(CASE WHEN cost_total IS NOT NULL THEN total - cost_total ELSE 0 END), 0),
               COALESCE(SUM(CASE WHEN cost_total IS NULL THEN 1 ELSE 0 END), 0)
        FROM orders
        WHERE status = 'Lunas'
    """)
    total_transactions, total_revenue, recorded_gross_profit, orders_without_cost = cursor.fetchone()
    cursor.execute("""
        SELECT COALESCE(SUM(total), 0)
        FROM orders
        WHERE status = 'Lunas'
          AND date(COALESCE(completed_at, created_at)) = date('now', 'localtime')
    """)
    today_revenue = cursor.fetchone()[0]
    conn.close()
    return total_transactions, total_revenue, today_revenue, recorded_gross_profit, orders_without_cost


def get_admin_by_email_and_password(email, password):
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, name, email, password, store_name, profile_photo
        FROM admins
        WHERE LOWER(email) = LOWER(?) AND password = ?
        """,
        (email.strip(), password)
    )
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    admin_id, name, email_value, stored_password, store_name, profile_photo = row
    return {
        "id": admin_id,
        "name": name,
        "email": email_value,
        "password": stored_password,
        "store_name": store_name,
        "profile_photo": profile_photo or "",
    }


def update_admin_profile(admin_id, name, email, password, store_name, profile_photo=""):
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE admins
        SET name = ?, email = ?, password = ?, store_name = ?, profile_photo = ?
        WHERE id = ?
        """,
        (name, email, password, store_name, profile_photo, admin_id)
    )
    conn.commit()
    conn.close()


def add_product(name, brand, price, description, stock, image="", cost_price=None):
    conn = connect_db()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO products
        (name, brand, price, description, stock, image, cost_price)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (name, brand, price, description, stock, image, cost_price))

    conn.commit()
    conn.close()


def update_product(product_id, name, brand, price, description, stock, image="", cost_price=None):
    conn = connect_db()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE products
        SET name=?, brand=?, price=?, description=?, stock=?, image=?, cost_price=?
        WHERE id=?
    """, (name, brand, price, description, stock, image, cost_price, product_id))

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