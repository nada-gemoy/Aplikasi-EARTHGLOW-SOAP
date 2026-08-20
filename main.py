"""
EarthGlow Soap - Aplikasi Toko Sabun
Tugas Projek Tahap 1: Navigasi & Event Handling
Dibuat dengan Python + Kivy

Struktur navigasi (sesuai rancangan Figma):
Welcome -> Create Account -> Login -> Profile -> Search -> Shop
  -> Detail Produk -> Cart
"""

from kivy.app import App
from kivy.lang import Builder
from kivy.uix.screenmanager import ScreenManager, Screen, SlideTransition
from kivy.properties import NumericProperty, StringProperty
from kivy.core.window import Window

# Ukuran window disamakan dengan proporsi HP, disesuaikan agar tidak
# terpotong di layar laptop (360x640 muat di hampir semua ukuran layar).
Window.size = (360, 640)


# ------------------------------------------------------------------
# DATA SEMENTARA (nanti bisa diganti database / API)
# ------------------------------------------------------------------
PRODUCTS = [
    {"name": "Cocoberry Soap", "price": 40000, "img": "assets/cocoberry.png"},
    {"name": "Beauty White Soap", "price": 47000, "img": "assets/beautywhite.png"},
    {"name": "Sabun Keraton", "price": 60000, "img": "assets/keraton.png"},
    {"name": "Harmoni Soap", "price": 5000, "img": "assets/harmoni.png"},
]


# ------------------------------------------------------------------
# SCREEN 1: WELCOME
# ------------------------------------------------------------------
class WelcomeScreen(Screen):
    def go_to_create_account(self):
        """Event handler tombol 'Let's get started'"""
        self.manager.transition = SlideTransition(direction="left")
        self.manager.current = "create_account"


# ------------------------------------------------------------------
# SCREEN 2: CREATE ACCOUNT
# ------------------------------------------------------------------
class CreateAccountScreen(Screen):
    def submit_account(self):
        """Event handler tombol 'Done'"""
        email = self.ids.email_input.text
        password = self.ids.password_input.text

        if not email or not password:
            self.ids.error_label.text = "Email dan password wajib diisi!"
            return

        self.ids.error_label.text = ""
        self.manager.transition = SlideTransition(direction="left")
        self.manager.current = "login"


# ------------------------------------------------------------------
# SCREEN 3: LOGIN
# ------------------------------------------------------------------
class LoginScreen(Screen):
    def do_login(self):
        """Event handler tombol 'Next' pada Login"""
        # Di sini nanti bisa ditambahkan validasi login sungguhan
        self.manager.transition = SlideTransition(direction="left")
        self.manager.current = "profile"


# ------------------------------------------------------------------
# SCREEN 4: PROFILE / AKUN
# ------------------------------------------------------------------
class ProfileScreen(Screen):
    def go_to_search(self):
        self.manager.transition = SlideTransition(direction="left")
        self.manager.current = "search"

    def go_home(self):
        self.manager.transition = SlideTransition(direction="right")
        self.manager.current = "shop"

    def go_cart(self):
        self.manager.current = "cart"


# ------------------------------------------------------------------
# SCREEN 5: SEARCH
# ------------------------------------------------------------------
class SearchScreen(Screen):
    def select_category(self, category_name):
        """Event handler saat kategori (AHA, DOVE, dst) ditekan"""
        print(f"Kategori dipilih: {category_name}")
        self.manager.current = "shop"

    def go_home(self):
        self.manager.current = "shop"

    def go_profile(self):
        self.manager.current = "profile"

    def go_cart(self):
        self.manager.current = "cart"


# ------------------------------------------------------------------
# SCREEN 6: SHOP
# ------------------------------------------------------------------
class ShopScreen(Screen):
    def on_pre_enter(self, *args):
        self.load_products()

    def load_products(self):
        grid = self.ids.product_grid
        grid.clear_widgets()
        from kivy.uix.button import Button

        for product in PRODUCTS:
            harga = f"Rp.{product['price']:,}".replace(",", ".")
            btn = Button(
                text=f"[b]{product['name']}[/b]\n[color=1766f2]{harga}[/color]",
                markup=True,
                halign="center",
                size_hint_y=None,
                height=140,
                background_normal="",
                background_color=(0.96, 0.96, 0.96, 1),
                color=(0, 0, 0, 1),
            )
            btn.bind(on_release=lambda inst, p=product: self.open_detail(p))
            grid.add_widget(btn)

    def open_detail(self, product):
        """Event handler saat produk ditekan -> ke halaman detail"""
        detail_screen = self.manager.get_screen("detail_produk")
        detail_screen.set_product(product)
        self.manager.transition = SlideTransition(direction="left")
        self.manager.current = "detail_produk"

    def go_search(self):
        self.manager.current = "search"

    def go_profile(self):
        self.manager.current = "profile"

    def go_cart(self):
        self.manager.current = "cart"


# ------------------------------------------------------------------
# SCREEN 7: DETAIL PRODUK
# ------------------------------------------------------------------
class DetailProdukScreen(Screen):
    product_name = StringProperty("")
    product_price = NumericProperty(0)

    def set_product(self, product):
        self.product_name = product["name"]
        self.product_price = product["price"]

    def add_to_cart(self):
        """Event handler tombol 'Add to cart'"""
        app = App.get_running_app()
        app.cart.append({"name": self.product_name, "price": self.product_price})
        print(f"{self.product_name} ditambahkan ke keranjang")

    def buy_now(self):
        """Event handler tombol 'Buy now' -> langsung ke cart"""
        self.add_to_cart()
        self.manager.transition = SlideTransition(direction="left")
        self.manager.current = "cart"

    def go_back(self):
        self.manager.transition = SlideTransition(direction="right")
        self.manager.current = "shop"


# ------------------------------------------------------------------
# SCREEN 8: CART (KERANJANG)
# ------------------------------------------------------------------
class CartScreen(Screen):
    def on_pre_enter(self, *args):
        self.load_cart()

    def load_cart(self):
        app = App.get_running_app()
        grid = self.ids.cart_grid
        grid.clear_widgets()
        from kivy.uix.label import Label

        total = 0
        for item in app.cart:
            harga = f"Rp.{item['price']:,}".replace(",", ".")
            grid.add_widget(
                Label(
                    text=f"{item['name']}   [color=1766f2]{harga}[/color]",
                    markup=True,
                    halign="left",
                    text_size=(320, None),
                    size_hint_y=None,
                    height=40,
                    color=(0, 0, 0, 1),
                )
            )
            total += item["price"]

        self.ids.total_label.text = f"Total: Rp.{total:,}".replace(",", ".")

    def pay(self):
        """Event handler tombol 'Pay'"""
        print("Pembayaran diproses...")
        app = App.get_running_app()
        app.cart.clear()
        self.manager.current = "shop"

    def go_shop(self):
        self.manager.current = "shop"


# ------------------------------------------------------------------
# SCREEN MANAGER
# ------------------------------------------------------------------
class NavigasiManager(ScreenManager):
    pass


# ------------------------------------------------------------------
# APLIKASI UTAMA
# ------------------------------------------------------------------
class EarthGlowApp(App):
    def build(self):
        self.cart = []  # menyimpan item keranjang belanja (state sederhana)
        self.title = "EarthGlow Soap"
        # PENTING: navigasi.kv berisi definisi root widget (NavigasiManager
        # beserta semua screen di dalamnya). Builder.load_file() akan
        # MENGEMBALIKAN widget tersebut -- harus di-return langsung,
        # bukan membuat NavigasiManager() baru yang kosong tanpa screen.
        return Builder.load_file("navigasi.kv")


if __name__ == "__main__":
    EarthGlowApp().run()
