import tkinter as tk
from tkinter import filedialog
import html
import os
import tempfile

from kivy.app import App
from kivy.core.window import Window
from kivy.lang import Builder
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.properties import StringProperty
from kivy.uix.label import Label
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.image import Image
from kivy.uix.popup import Popup
from kivy.uix.spinner import Spinner
from kivy.uix.textinput import TextInput

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

        except Exception as error:
            print("Dashboard error:", error)
            self.total_products = "0"
            self.total_stock = "0"
            self.total_orders = "0"


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
        root_tk = tk.Tk()
        root_tk.withdraw()
        root_tk.attributes("-topmost", True)
        file_path = filedialog.askopenfilename(
            title="Pilih Foto Produk",
            filetypes=[("File Gambar", "*.png *.jpg *.jpeg *.webp"), ("Semua File", "*.*")]
        )
        root_tk.destroy()
        if file_path:
            image_input.text = file_path

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
    def on_pre_enter(self, *args):
        self.refresh_report()

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
        table.width = 1400
        table.height = 200

        headers = ["Tanggal", "Nama", "Alamat", "Produk", "Qty", "Bayar", "Total", "Status"]
        for header in headers:
            table.add_widget(Label(
                text=header,
                bold=True,
                color=(0.1, 0.2, 0.15, 1),
                size_hint=(None, None),
                width=160,
                height=32,
                halign="center",
                valign="middle",
                text_size=(160, 32)
            ))

        orders = [order for order in get_orders() if order[7] == "Lunas"]
        if not orders:
            table.add_widget(Label(
                text="Belum ada transaksi lunas",
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
                (created_at or "-").split(" ")[0],
                customer_name or "Pelanggan umum",
                customer_address or "-",
                product_name or "-",
                str(quantity or 0),
                payment_method or "Cash",
                f"Rp{total:,}",
                status or "Lunas",
            ]
            for value in values:
                table.add_widget(Label(
                    text=value,
                    color=(0.15, 0.2, 0.15, 1),
                    size_hint=(None, None),
                    width=160,
                    height=32,
                    halign="center",
                    valign="middle",
                    text_size=(160, 32)
                ))

        table.height = max(table.minimum_height, 200)

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
        root_tk = tk.Tk()
        root_tk.withdraw()
        root_tk.attributes("-topmost", True)

        file_path = filedialog.askopenfilename(
            title="Pilih Foto Profil",
            filetypes=[
                ("File Gambar", "*.png *.jpg *.jpeg *.webp"),
                ("Semua File", "*.*")
            ]
        )

        root_tk.destroy()

        if file_path:
            self.ids.foto_profil.source = file_path
            self.ids.foto_profil.reload()
            self.ids.profile_message.text = "Foto profil berhasil dipilih"

    def save_profile(self):
        nama = self.ids.nama_admin.text.strip()
        email = self.ids.email_admin.text.strip()
        toko = self.ids.nama_toko.text.strip()

        if nama == "" or email == "" or toko == "":
            self.ids.profile_message.text = "Semua data wajib diisi"
            return

        self.ids.profile_message.text = "Perubahan berhasil disimpan"


class NavigasiManager(ScreenManager):
    pass


class EarthGlowApp(App):
    def build(self):
        create_tables()
        Window.size = (420, 840)
        Window.minimum_width = 360
        Window.minimum_height = 640
        self.title = "EarthGlow Soap Admin"
        return Builder.load_file("navigasi.kv")


if __name__ == "__main__":
    EarthGlowApp().run()