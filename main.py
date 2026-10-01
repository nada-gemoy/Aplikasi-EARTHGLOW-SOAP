import html
import os
import tempfile
from datetime import datetime

from kivy.app import App
from kivy.core.window import Window
from kivy.graphics import Color, Line, Rectangle
from kivy.lang import Builder
from kivy.metrics import dp
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.properties import StringProperty
from kivy.uix.label import Label
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.filechooser import FileChooserIconView
from kivy.uix.image import Image
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.uix.spinner import Spinner
from kivy.uix.textinput import TextInput
from kivy.utils import platform

from database import (
    create_tables,
    get_products,
    get_order_count,
    add_product,
    update_product,
    add_order,
    get_orders,
    get_financial_summary
)


class ProductPhoto(ButtonBehavior, Image):
    pass


def open_image_picker(on_select):
    initial_path = "/storage/emulated/0" if platform == "android" else os.path.expanduser("~")
    chooser = FileChooserIconView(
        path=initial_path,
        filters=["*.png", "*.jpg", "*.jpeg", "*.webp"]
    )
    content = BoxLayout(orientation="vertical", spacing=dp(8), padding=dp(8))
    content.add_widget(chooser)
    actions = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(8))
    popup = Popup(title="Pilih Gambar", content=content, size_hint=(0.95, 0.9))

    def select_image(button):
        if chooser.selection:
            on_select(chooser.selection[0])
            popup.dismiss()

    actions.add_widget(Button(text="Pilih", on_release=select_image))
    actions.add_widget(Button(text="Batal", on_release=lambda button: popup.dismiss()))
    content.add_widget(actions)
    popup.open()


class WelcomeScreen(Screen):
    pass


class LoginScreen(Screen):
    pesan = StringProperty("")

    def login(self):
        email = self.ids.email_input.text.strip()
        password = self.ids.password_input.text.strip()

        if email == "" or password == "":
            self.pesan = "Email dan password wajib diisi"
            return

        self.pesan = ""
        self.manager.current = "dashboard"


class DashboardScreen(Screen):
    total_products = StringProperty("0")
    total_stock = StringProperty("0")
    total_orders = StringProperty("0")
    cart_count = StringProperty("0")
    catalog_message = StringProperty("")

    def on_pre_enter(self, *args):
        self.refresh_dashboard()

    def refresh_dashboard(self):
        try:
            products = get_products()

            self.total_products = str(len(products))

            total_stock = 0
            for product in products:
                try:
                    total_stock += int(product[5] or 0)
                except Exception:
                    pass

            self.total_stock = str(total_stock)
            self.total_orders = str(get_order_count())
            self.load_catalog(products)

        except Exception as error:
            print("Dashboard error:", error)
            self.total_products = "0"
            self.total_stock = "0"
            self.total_orders = "0"

    def load_catalog(self, products):
        catalog = self.ids.catalog_grid
        catalog.clear_widgets()

        for product in products:
            product_id, name, brand, price, description, stock, image_path = product
            card = BoxLayout(
                orientation="vertical",
                padding=8,
                spacing=5,
                size_hint_y=None,
                height=dp(270)
            )
            card.canvas.before.clear()
            with card.canvas.before:
                from kivy.graphics import Color, RoundedRectangle
                Color(0.98, 0.99, 0.97, 1)
                card.background = RoundedRectangle(pos=card.pos, size=card.size, radius=[8])
            card.bind(
                pos=lambda widget, value: setattr(widget.background, "pos", value),
                size=lambda widget, value: setattr(widget.background, "size", value)
            )

            if image_path and os.path.isfile(image_path):
                card.add_widget(ProductPhoto(
                    source=image_path,
                    size_hint_y=None,
                    height=dp(155),
                    fit_mode="contain",
                    on_release=lambda photo, path=image_path, title=name: self.show_product_photo(path, title)
                ))
            else:
                card.add_widget(Label(
                    text="Foto belum tersedia",
                    size_hint_y=None,
                    height=dp(155),
                    color=(0.42, 0.48, 0.43, 1)
                ))

            product_details = Label(
                text=f"{name}\nRp{int(price):,} | Stok {stock or 0}",
                size_hint_y=None,
                height=dp(48),
                color=(0.12, 0.25, 0.18, 1),
                halign="center",
                valign="middle",
                text_size=(card.width - dp(16), dp(48)),
                font_size="14sp"
            )
            card.bind(width=lambda widget, value, label=product_details: setattr(
                label, "text_size", (value - dp(16), dp(48))
            ))
            card.add_widget(product_details)
            card.add_widget(Button(
                text="Tambah ke Keranjang",
                size_hint_y=None,
                height=dp(42),
                background_normal="",
                background_color=(0.18, 0.52, 0.38, 1),
                on_release=lambda button, item=product: self.add_to_cart(item)
            ))
            catalog.add_widget(card)

        if not products:
            catalog.add_widget(Label(
                text="Belum ada produk. Tambahkan barang melalui menu Kelola Produk.",
                size_hint_y=None,
                height=60,
                color=(0.42, 0.48, 0.43, 1)
            ))

        self.update_cart_count()

    def show_product_photo(self, image_path, title):
        content = BoxLayout(orientation="vertical", spacing=dp(8), padding=dp(8))
        content.add_widget(Image(source=image_path, fit_mode="contain"))
        popup = Popup(title=title, content=content, size_hint=(0.96, 0.86))
        content.add_widget(Button(
            text="Tutup",
            size_hint_y=None,
            height=dp(44),
            on_release=lambda button: popup.dismiss()
        ))
        popup.open()

    def add_to_cart(self, product):
        cart = self.manager.cart_items
        product_id = product[0]
        current_quantity = cart.get(product_id, {}).get("quantity", 0)
        if current_quantity >= int(product[5] or 0):
            self.catalog_message = "Stok produk ini sudah habis di keranjang"
            return
        if product_id in cart:
            cart[product_id]["quantity"] += 1
        else:
            cart[product_id] = {"product": product, "quantity": 1}
        self.catalog_message = f"{product[1]} ditambahkan ke keranjang"
        self.update_cart_count()

    def update_cart_count(self):
        self.cart_count = str(sum(item["quantity"] for item in self.manager.cart_items.values()))

    def open_cashier(self):
        self.manager.current = "cashier"


class CashierScreen(Screen):
    total_text = StringProperty("Rp0")
    change_text = StringProperty("Kembalian: Rp0")
    payment_method = StringProperty("Cash")
    payment_destination_hint = StringProperty("Tidak diperlukan untuk tunai")
    payment_destination_label = StringProperty("Tujuan pembayaran")

    def on_pre_enter(self, *args):
        self.refresh_cashier()

    def refresh_cashier(self):
        cart_list = self.ids.cart_list
        cart_list.clear_widgets()
        total = 0

        for product_id, item in list(self.manager.cart_items.items()):
            product = item["product"]
            quantity = item["quantity"]
            line_total = int(product[3]) * quantity
            total += line_total

            row = BoxLayout(orientation="vertical", size_hint_y=None, height=dp(78), spacing=dp(2))
            row.add_widget(Label(
                text=f"{product[1]}  |  Rp{int(product[3]):,} / pcs",
                size_hint_y=None,
                height=dp(30),
                halign="left",
                text_size=(self.width - dp(40), dp(30)),
                color=(0.12, 0.25, 0.18, 1),
                font_size="15sp"
            ))
            controls = BoxLayout(size_hint_y=None, height=dp(42), spacing=dp(5))
            controls.add_widget(Button(
                text="-",
                size_hint_x=None,
                width=dp(42),
                on_release=lambda button, pid=product_id: self.change_quantity(pid, -1)
            ))
            controls.add_widget(Label(
                text=str(quantity),
                size_hint_x=None,
                width=dp(38),
                color=(0.12, 0.25, 0.18, 1)
            ))
            controls.add_widget(Button(
                text="+",
                size_hint_x=None,
                width=dp(42),
                on_release=lambda button, pid=product_id: self.change_quantity(pid, 1)
            ))
            controls.add_widget(Button(
                text="Hapus",
                size_hint_x=None,
                width=dp(72),
                on_release=lambda button, pid=product_id: self.remove_item(pid)
            ))
            controls.add_widget(Label(
                text=f"Rp{line_total:,}",
                halign="right",
                color=(0.12, 0.25, 0.18, 1)
            ))
            row.add_widget(controls)
            cart_list.add_widget(row)

        if not self.manager.cart_items:
            cart_list.add_widget(Label(
                text="Keranjang masih kosong. Tambahkan produk dari beranda.",
                size_hint_y=None,
                height=dp(55),
                color=(0.42, 0.48, 0.43, 1)
            ))

        self.total_amount = total
        self.total_text = f"Rp{total:,}"
        self.update_change()

    def change_quantity(self, product_id, amount):
        item = self.manager.cart_items.get(product_id)
        if not item:
            return
        new_quantity = item["quantity"] + amount
        stock = int(item["product"][5] or 0)
        if new_quantity <= 0:
            self.remove_item(product_id)
            return
        if new_quantity > stock:
            self.ids.cashier_message.text = "Jumlah melebihi stok tersedia"
            return
        item["quantity"] = new_quantity
        self.ids.cashier_message.text = ""
        self.refresh_cashier()

    def remove_item(self, product_id):
        self.manager.cart_items.pop(product_id, None)
        self.ids.cashier_message.text = ""
        self.refresh_cashier()

    def update_change(self, *args):
        if self.payment_method != "Cash":
            self.change_text = "Kembalian: Rp0 (pembayaran non-tunai)"
            return
        received_text = self.ids.cash_received.text.strip()
        try:
            received = int(received_text) if received_text else 0
        except ValueError:
            received = 0
        difference = received - getattr(self, "total_amount", 0)
        if difference < 0:
            self.change_text = f"Kurang: Rp{-difference:,}"
        else:
            self.change_text = f"Kembalian: Rp{difference:,}"

    def select_payment(self, method):
        self.payment_method = method
        is_cash = method == "Cash"
        self.ids.payment_destination_row.height = 0 if is_cash else dp(64)
        self.ids.cash_received_row.height = dp(42) if is_cash else 0
        self.ids.payment_destination.text = ""
        if method == "QRIS":
            self.payment_destination_label = "Tujuan QRIS"
            self.payment_destination_hint = "Nama merchant atau ID QRIS"
        elif method == "Debit":
            self.payment_destination_label = "Tujuan Debit"
            self.payment_destination_hint = "Nama bank dan rekening / mesin EDC"
        else:
            self.payment_destination_label = "Tujuan pembayaran"
            self.payment_destination_hint = "Tidak diperlukan untuk tunai"
        self.ids.cash_received.disabled = not is_cash
        self.update_change()

    def show_receipt(self, receipt_text):
        content = BoxLayout(orientation="vertical", spacing=dp(8), padding=dp(12))
        with content.canvas.before:
            Color(1, 1, 1, 1)
            content.paper = Rectangle(pos=content.pos, size=content.size)
            Color(0.72, 0.77, 0.73, 1)
            content.paper_border = Line(rectangle=(*content.pos, *content.size), width=1)
        content.bind(
            pos=lambda widget, value: setattr(widget.paper, "pos", value),
            size=lambda widget, value: (
                setattr(widget.paper, "size", value),
                setattr(widget.paper_border, "rectangle", (*widget.pos, *widget.size))
            )
        )
        scroll = ScrollView(do_scroll_x=False)
        receipt_label = Label(
            text=receipt_text,
            size_hint_y=None,
            halign="left",
            valign="top",
            color=(0.12, 0.15, 0.13, 1),
            font_size="16sp"
        )
        receipt_label.bind(width=lambda label, width: setattr(label, "text_size", (width, None)))
        receipt_label.bind(texture_size=lambda label, size: setattr(label, "height", size[1]))
        scroll.add_widget(receipt_label)
        content.add_widget(scroll)
        popup = Popup(title="Nota Pembayaran", content=content, size_hint=(0.92, 0.82))
        content.add_widget(Button(
            text="Tutup Nota",
            size_hint_y=None,
            height=dp(46),
            background_normal="",
            background_color=(0.18, 0.52, 0.38, 1),
            on_release=lambda button: popup.dismiss()
        ))
        popup.open()

    def complete_sale(self):
        if not self.manager.cart_items:
            self.ids.cashier_message.text = "Keranjang masih kosong"
            return

        customer_name = self.ids.customer_input.text.strip() or "Pelanggan umum"
        payment = self.payment_method
        status = self.ids.status_spinner.text
        destination = self.ids.payment_destination.text.strip()
        if payment != "Cash" and not destination:
            self.ids.cashier_message.text = f"Isi tujuan pembayaran {payment} terlebih dahulu"
            return
        payment_record = f"{payment} - {destination}" if destination else payment
        try:
            received = int(self.ids.cash_received.text or 0)
        except ValueError:
            self.ids.cashier_message.text = "Nominal uang diterima harus berupa angka"
            return

        if payment == "Cash" and status == "Lunas" and received < self.total_amount:
            self.ids.cashier_message.text = "Uang diterima masih kurang dari total belanja"
            return

        latest_products = {product[0]: product for product in get_products()}
        for product_id, item in self.manager.cart_items.items():
            latest_product = latest_products.get(product_id)
            if not latest_product or item["quantity"] > int(latest_product[5] or 0):
                self.ids.cashier_message.text = f"Stok {item['product'][1]} berubah. Periksa keranjang."
                return

        sale_items = []
        receipt_lines = [
            "EARTHGLOW SOAP",
            "NOTA PEMBAYARAN",
            datetime.now().strftime("Tanggal: %d-%m-%Y %H:%M"),
            f"Pelanggan: {customer_name}",
            "-" * 30
        ]
        total_quantity = 0
        for product_id, item in self.manager.cart_items.items():
            product = latest_products[product_id]
            quantity = item["quantity"]
            sale_items.append(f"{product[1]} x{quantity}")
            receipt_lines.append(f"{product[1]} x{quantity}  Rp{int(product[3]) * quantity:,}")
            total_quantity += quantity
            update_product(
                product_id,
                product[1],
                product[2],
                product[3],
                product[4],
                int(product[5] or 0) - quantity,
                product[6] or ""
            )

        add_order(
            customer_name,
            "-",
            ", ".join(sale_items),
            total_quantity,
            self.total_amount,
            payment_record,
            status
        )
        receipt_lines.extend([
            "-" * 30,
            f"TOTAL: Rp{self.total_amount:,}",
            f"Pembayaran: {payment_record}",
            f"Status: {status}"
        ])
        if payment == "Cash":
            receipt_lines.append(f"Diterima: Rp{received:,}")
            receipt_lines.append(f"Kembalian: Rp{max(received - self.total_amount, 0):,}")
        elif status == "Lunas":
            receipt_lines.append(f"Dibayar: Rp{self.total_amount:,}")
        self.last_receipt = "\n".join(receipt_lines)
        self.manager.cart_items.clear()
        self.ids.customer_input.text = ""
        self.ids.cash_received.text = ""
        self.ids.payment_destination.text = ""
        self.ids.cashier_message.text = "Transaksi berhasil disimpan"
        self.refresh_cashier()
        self.manager.get_screen("dashboard").refresh_dashboard()
        self.show_receipt(self.last_receipt)

    def back_to_catalog(self):
        self.manager.current = "dashboard"


class ProductsScreen(Screen):
    def on_pre_enter(self, *args):
        self.load_products()

    def load_products(self):
        self.ids.product_list.clear_widgets()

        products = get_products()

        if not products:
            self.ids.product_list.add_widget(
                Label(
                    text="Belum ada produk di database",
                    size_hint_y=None,
                    height=50,
                    font_size="16sp"
                )
            )
            return

        for product in products:
            product_id = product[0]
            name = product[1]
            brand = product[2] or "-"
            price = product[3]
            stock = product[5] or 0
            image_path = product[6] or ""

            text = (
                f"ID: {product_id}\n"
                f"{name} | Brand: {brand}\n"
                f"Harga: Rp{price:,} | Stok: {stock}"
            )

            row = BoxLayout(size_hint_y=None, height=110, spacing=8)
            if image_path and os.path.isfile(image_path):
                row.add_widget(Image(source=image_path, size_hint_x=None, width=90))
            else:
                row.add_widget(Label(text="Tanpa foto", size_hint_x=None, width=90))
            row.add_widget(Label(text=text, halign="left", valign="middle"))
            row.add_widget(Button(
                text="Edit",
                size_hint_x=None,
                width=75,
                on_release=lambda button, item=product: self.open_product_form(item)
            ))
            row.add_widget(Button(
                text="Jual",
                size_hint_x=None,
                width=75,
                on_release=lambda button, item=product: self.open_sale_form(item)
            ))
            self.ids.product_list.add_widget(row)

    def choose_image(self, image_input):
        open_image_picker(lambda file_path: setattr(image_input, "text", file_path))

    def open_product_form(self, product=None):
        is_edit = product is not None
        form = BoxLayout(orientation="vertical", padding=15, spacing=8)
        name_input = TextInput(hint_text="Nama barang", text=product[1] if is_edit else "", multiline=False)
        brand_input = TextInput(hint_text="Merek", text=product[2] or "" if is_edit else "", multiline=False)
        price_input = TextInput(hint_text="Harga jual (angka)", text=str(product[3]) if is_edit else "", multiline=False, input_filter="int")
        description_input = TextInput(hint_text="Deskripsi", text=product[4] or "" if is_edit else "", multiline=False)
        stock_input = TextInput(hint_text="Stok", text=str(product[5] or 0) if is_edit else "", multiline=False, input_filter="int")
        image_input = TextInput(hint_text="Pilih lokasi foto", text=product[6] or "" if is_edit else "", multiline=False, readonly=True, size_hint_x=0.72)
        message = Label(text="", size_hint_y=None, height=28)
        form.add_widget(name_input)
        form.add_widget(brand_input)
        form.add_widget(price_input)
        form.add_widget(description_input)
        form.add_widget(stock_input)
        image_row = BoxLayout(size_hint_y=None, height=42, spacing=6)
        image_row.add_widget(image_input)
        image_row.add_widget(Button(text="Pilih Foto", on_release=lambda button: self.choose_image(image_input)))
        form.add_widget(image_row)
        form.add_widget(message)
        actions = BoxLayout(size_hint_y=None, height=45, spacing=8)
        popup = Popup(title="Ubah Barang" if is_edit else "Tambah Barang", content=form, size_hint=(0.88, 0.8))

        def save_product(button):
            name = name_input.text.strip()
            if not name or not price_input.text or not stock_input.text:
                message.text = "Nama, harga, dan stok wajib diisi"
                return
            try:
                price = int(price_input.text)
                stock = int(stock_input.text)
                if price < 0 or stock < 0:
                    raise ValueError
                values = (name, brand_input.text.strip(), price, description_input.text.strip(), stock, image_input.text.strip())
                if is_edit:
                    update_product(product[0], *values)
                else:
                    add_product(*values)
                popup.dismiss()
                self.load_products()
            except ValueError:
                message.text = "Harga dan stok harus angka nol atau lebih"

        actions.add_widget(Button(text="Simpan", on_release=save_product))
        actions.add_widget(Button(text="Batal", on_release=lambda button: popup.dismiss()))
        form.add_widget(actions)
        popup.open()

    def open_sale_form(self, product):
        form = BoxLayout(orientation="vertical", padding=15, spacing=8)
        form.add_widget(Label(text=f"{product[1]} | Stok tersedia: {product[5] or 0}"))
        customer_input = TextInput(hint_text="Nama pelanggan", multiline=False)
        address_input = TextInput(hint_text="Alamat pemesan", multiline=False)
        quantity_input = TextInput(hint_text="Jumlah terjual", multiline=False, input_filter="int")
        message = Label(text="", size_hint_y=None, height=28)

        payment_row = BoxLayout(size_hint_y=None, height=42, spacing=8)
        payment_row.add_widget(Label(text="Bayar: ", size_hint_x=None, width=80))
        payment_spinner = Spinner(text='Cash', values=['Cash', 'QRIS', 'Debit'], size_hint_x=1)
        payment_row.add_widget(payment_spinner)

        status_row = BoxLayout(size_hint_y=None, height=42, spacing=8)
        status_row.add_widget(Label(text="Status: ", size_hint_x=None, width=80))
        status_spinner = Spinner(text='Lunas', values=['Lunas', 'Belum Lunas'], size_hint_x=1)
        status_row.add_widget(status_spinner)

        form.add_widget(customer_input)
        form.add_widget(address_input)
        form.add_widget(quantity_input)
        form.add_widget(payment_row)
        form.add_widget(status_row)
        form.add_widget(message)
        popup = Popup(title="Catat Penjualan", content=form, size_hint=(0.82, 0.72))
        actions = BoxLayout(size_hint_y=None, height=44, spacing=8)

        def save_sale(button):
            try:
                quantity = int(quantity_input.text)
                stock = int(product[5] or 0)
                if quantity <= 0 or quantity > stock:
                    raise ValueError
                total = int(product[3]) * quantity
                customer_name = customer_input.text.strip() or "Pelanggan umum"
                address = address_input.text.strip() or "-"
                payment = payment_spinner.text or 'Cash'
                order_status = status_spinner.text or 'Lunas'
                add_order(customer_name, address, product[1], quantity, total, payment, order_status)
                update_product(product[0], product[1], product[2], product[3], product[4], stock - quantity, product[6] or "")
                popup.dismiss()
                self.load_products()
            except ValueError:
                message.text = "Jumlah harus lebih dari nol dan tidak melebihi stok"

        actions.add_widget(Button(text="Simpan Penjualan", on_release=save_sale))
        actions.add_widget(Button(text="Batal", on_release=lambda button: popup.dismiss()))
        form.add_widget(actions)
        popup.open()


class OrdersScreen(Screen):
    def on_pre_enter(self, *args):
        self.load_orders()

    def load_orders(self):
        table = self.ids.orders_table
        table.clear_widgets()
        table.cols = 8
        table.size_hint = (None, None)
        table.width = 1400
        table.height = 200

        headers = ["No", "Nama", "Alamat", "Produk", "Qty", "Total", "Bayar", "Status"]
        for header in headers:
            table.add_widget(Label(
                text=header,
                bold=True,
                color=(0.1, 0.2, 0.15, 1),
                size_hint=(None, None),
                width=150,
                height=32,
                halign="center",
                valign="middle",
                text_size=(150, 32)
            ))

        orders = get_orders()
        if not orders:
            table.add_widget(Label(
                text="Belum ada penjualan tercatat",
                color=(0.2, 0.3, 0.2, 1),
                size_hint=(None, None),
                width=1400,
                height=50,
                halign="center",
                valign="middle",
                text_size=(1400, 50)
            ))
            return

        for order in orders:
            order_id, customer_name, customer_address, product_name, quantity, total, payment_method, status, created_at = order
            values = [
                str(order_id),
                customer_name or "Pelanggan umum",
                customer_address or "-",
                product_name or "-",
                str(quantity or 0),
                f"Rp{total:,}",
                payment_method or "Cash",
                status or "Lunas",
            ]
            for value in values:
                table.add_widget(Label(
                    text=value,
                    color=(0.15, 0.2, 0.15, 1),
                    size_hint=(None, None),
                    width=150,
                    height=32,
                    halign="center",
                    valign="middle",
                    text_size=(150, 32)
                ))

        table.height = max(table.minimum_height, 200)


class FinancialReportScreen(Screen):
    column_widths = (100, 145, 170, 240, 70, 170, 140, 110)

    def on_pre_enter(self, *args):
        self.refresh_report()

    def add_report_cell(self, table, text, column, is_header=False, row_index=0):
        width = dp(self.column_widths[column])
        cell = Label(
            text=str(text),
            bold=is_header,
            color=(1, 1, 1, 1) if is_header else (0.12, 0.2, 0.15, 1),
            font_size="14sp",
            size_hint=(None, None),
            width=width,
            text_size=(width - dp(14), None),
            halign="center" if is_header or column in (0, 4, 6, 7) else "left",
            valign="middle",
            padding=(dp(7), dp(7))
        )
        cell.texture_update()
        cell.height = max(dp(42), cell.texture_size[1] + dp(16))

        background = (0.16, 0.42, 0.31, 1) if is_header else (
            (1, 1, 1, 1) if row_index % 2 == 0 else (0.96, 0.98, 0.96, 1)
        )
        with cell.canvas.before:
            Color(*background)
            cell.fill = Rectangle(pos=cell.pos, size=cell.size)
            Color(0.72, 0.78, 0.73, 1)
            cell.border = Line(rectangle=(*cell.pos, *cell.size), width=1)
        cell.bind(
            pos=lambda widget, value: setattr(widget.fill, "pos", value),
            size=lambda widget, value: (
                setattr(widget.fill, "size", value),
                setattr(widget.border, "rectangle", (*widget.pos, *widget.size))
            )
        )
        table.add_widget(cell)

    def refresh_report(self):
        count, revenue, today = get_financial_summary()
        self.ids.report_summary.text = (
            f"Transaksi lunas: {count}\n"
            f"Pendapatan hari ini: Rp{today:,}\n"
            f"Total pendapatan: Rp{revenue:,}"
        )

        table = self.ids.report_table
        table.clear_widgets()
        table.cols = 8
        table.size_hint = (None, None)
        table.width = dp(sum(self.column_widths))
        table.row_force_default = False
        if not getattr(table, "tracks_minimum_height", False):
            table.bind(minimum_height=table.setter("height"))
            table.tracks_minimum_height = True

        headers = ["Tanggal", "Nama", "Alamat", "Produk", "Qty", "Bayar", "Total", "Status"]
        for column, header in enumerate(headers):
            self.add_report_cell(table, header, column, is_header=True)

        orders = [order for order in get_orders() if order[7] == "Lunas"]
        if not orders:
            empty_row = ["Belum ada transaksi lunas"] + [""] * 7
            for column, value in enumerate(empty_row):
                self.add_report_cell(table, value, column, row_index=0)
            return

        for row_index, order in enumerate(orders):
            order_id, customer_name, customer_address, product_name, quantity, total, payment_method, status, created_at = order
            values = [
                (created_at or "-").split(" ")[0],
                customer_name or "Pelanggan umum",
                customer_address or "-",
                product_name or "-",
                str(quantity or 0),
                payment_method or "Cash",
                f"Rp{total:,}",
                status or "Lunas",
            ]
            for column, value in enumerate(values):
                self.add_report_cell(table, value, column, row_index=row_index)

    def print_report(self):
        count, revenue, today = get_financial_summary()
        rows = "".join(
            f"<tr><td>{html.escape(str(order[7] or '-'))}</td>"
            f"<td>{html.escape(str(order[1] or 'Pelanggan umum'))}</td>"
            f"<td>{html.escape(str(order[2] or '-'))}</td>"
            f"<td>{html.escape(str(order[3] or '-'))}</td>"
            f"<td>{html.escape(str(order[4] or 0))}</td>"
            f"<td>Rp{order[5]:,}</td></tr>"
            for order in get_orders() if order[6] == "Lunas"
        )
        report_html = f"""<!doctype html><html><head><meta charset="utf-8">
<title>Laporan Keuangan EarthGlow Soap</title><style>
body{{font-family:Arial,sans-serif;margin:32px;color:#20382c}}h1{{color:#286344}}
table{{border-collapse:collapse;width:100%;margin-top:20px}}th,td{{border:1px solid #aaa;padding:8px;text-align:left}}
</style></head><body><h1>Laporan Keuangan EarthGlow Soap</h1>
<p>Transaksi lunas: {count}<br>Pendapatan hari ini: Rp{today:,}<br>Total pendapatan: Rp{revenue:,}</p>
<table><thead><tr><th>Tanggal</th><th>Nama</th><th>Alamat</th><th>Produk</th><th>Qty</th><th>Total</th></tr></thead><tbody>{rows}</tbody></table>
</body></html>"""
        report_path = os.path.join(tempfile.gettempdir(), "laporan_keuangan_earthglow.html")
        with open(report_path, "w", encoding="utf-8") as report_file:
            report_file.write(report_html)
        try:
            os.startfile(report_path, "print")
            self.ids.report_message.text = "Laporan dikirim ke printer"
        except OSError:
            os.startfile(report_path)
            self.ids.report_message.text = "Laporan dibuka di browser untuk dicetak"


class ProfileScreen(Screen):
    def pilih_foto(self):
        def set_profile_photo(file_path):
            self.ids.foto_profil.source = file_path
            self.ids.foto_profil.reload()
            self.ids.profile_message.text = "Foto profil berhasil dipilih"

        open_image_picker(set_profile_photo)

    def save_profile(self):
        nama = self.ids.nama_admin.text.strip()
        email = self.ids.email_admin.text.strip()
        toko = self.ids.nama_toko.text.strip()

        if nama == "" or email == "" or toko == "":
            self.ids.profile_message.text = "Semua data wajib diisi"
            return

        self.ids.profile_message.text = "Perubahan berhasil disimpan"


class NavigasiManager(ScreenManager):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.cart_items = {}


class EarthGlowApp(App):
    def build(self):
        create_tables()
        if platform == "android":
            Window.fullscreen = "auto"
        else:
            Window.size = (420, 840)
            Window.minimum_width = 360
            Window.minimum_height = 640
        self.title = "EarthGlow Soap Admin"
        return Builder.load_file("navigasi.kv")


if __name__ == "__main__":
    EarthGlowApp().run()