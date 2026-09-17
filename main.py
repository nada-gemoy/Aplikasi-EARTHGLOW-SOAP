import tkinter as tk
from tkinter import filedialog

from kivy.app import App
from kivy.lang import Builder
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.properties import StringProperty
from kivy.uix.label import Label

from database import (
    create_tables,
    get_products,
    get_order_count
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

            text = (
                f"ID: {product_id}\n"
                f"{name} | Brand: {brand}\n"
                f"Harga: Rp{price:,} | Stok: {stock}"
            )

            self.ids.product_list.add_widget(
                Label(
                    text=text,
                    size_hint_y=None,
                    height=80,
                    halign="left",
                    valign="middle",
                    font_size="15sp"
                )
            )


class OrdersScreen(Screen):
    def on_pre_enter(self, *args):
        self.ids.orders_message.text = (
            f"Total pesanan saat ini: {get_order_count()}"
        )


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
        self.title = "EarthGlow Soap Admin"
        return Builder.load_file("navigasi.kv")


if __name__ == "__main__":
    EarthGlowApp().run()