import html
import os
import tempfile
from datetime import datetime

from kivy.app import App
from kivy.core.window import Window
from kivy.clock import Clock
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

import database as database_module
from financial_export import export_financial_workbook
from database import (
    create_tables,
    get_products,
    get_order_count,
    get_new_online_order_count,
    add_product,
    update_product,
    add_order,
    get_orders,
    get_order_metadata,
    update_order_status,
    get_financial_summary,
    get_channel_financial_summary,
    get_order_items,
    add_return,
    get_returns,
    get_admin_by_email_and_password,
    update_admin_profile
)


class ProductPhoto(ButtonBehavior, Image):
    pass


_IMAGE_PICKER_REQUEST_CODE = 7823
_EXCEL_EXPORT_REQUEST_CODE = 7824
_EXCEL_MIME_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
_pending_image_selection = None
_pending_excel_export = None
_image_picker_bound = False


def _handle_android_activity_result(request_code, result_code, intent):
    global _pending_image_selection, _pending_excel_export
    if request_code == _EXCEL_EXPORT_REQUEST_CODE:
        callback = _pending_excel_export
        _pending_excel_export = None
        if callback is not None:
            uri = intent.getData() if result_code == -1 and intent is not None else None
            Clock.schedule_once(lambda dt: callback(uri))
        return
    if request_code != _IMAGE_PICKER_REQUEST_CODE:
        return

    callback = _pending_image_selection
    _pending_image_selection = None
    if callback is None or result_code != -1 or intent is None:
        return

    try:
        image_path = _copy_android_image(intent.getData())
    except Exception as error:
        error_message = f"Gagal membaca foto: {error}"
        Clock.schedule_once(
            lambda dt: callback(None, error_message)
        )
        return

    Clock.schedule_once(lambda dt: callback(image_path, ""))


def _request_android_excel_destination(filename, callback):
    global _pending_excel_export, _image_picker_bound
    from android import activity
    from jnius import autoclass

    if not _image_picker_bound:
        activity.bind(on_activity_result=_handle_android_activity_result)
        _image_picker_bound = True
    if _pending_excel_export is not None:
        raise RuntimeError("Ekspor Excel sedang berlangsung.")

    intent_class = autoclass("android.content.Intent")
    intent = intent_class(intent_class.ACTION_CREATE_DOCUMENT)
    intent.addCategory(intent_class.CATEGORY_OPENABLE)
    intent.setType(_EXCEL_MIME_TYPE)
    intent.putExtra(intent_class.EXTRA_TITLE, filename)
    _pending_excel_export = callback
    try:
        autoclass("org.kivy.android.PythonActivity").mActivity.startActivityForResult(
            intent,
            _EXCEL_EXPORT_REQUEST_CODE,
        )
    except Exception:
        _pending_excel_export = None
        raise


def _copy_export_to_android_uri(source_path, destination_uri):
    from jnius import autoclass

    activity = autoclass("org.kivy.android.PythonActivity").mActivity
    output_stream = activity.getContentResolver().openOutputStream(destination_uri)
    if output_stream is None:
        raise OSError("Lokasi penyimpanan tidak dapat dibuka.")
    try:
        with open(source_path, "rb") as source_file:
            while True:
                data = source_file.read(64 * 1024)
                if not data:
                    break
                output_stream.write(data)
        output_stream.flush()
    finally:
        output_stream.close()


def _open_excel_or_web(destination_uri, filename):
    from jnius import autoclass

    activity = autoclass("org.kivy.android.PythonActivity").mActivity
    intent_class = autoclass("android.content.Intent")
    excel_intent = intent_class(intent_class.ACTION_VIEW)
    excel_intent.setDataAndType(destination_uri, _EXCEL_MIME_TYPE)
    excel_intent.addFlags(intent_class.FLAG_GRANT_READ_URI_PERMISSION)

    if excel_intent.resolveActivity(activity.getPackageManager()) is not None:
        activity.startActivity(intent_class.createChooser(excel_intent, "Buka file Excel"))
        return "Excel tersimpan. Pilih aplikasi untuk membuka file."

    web_intent = intent_class(intent_class.ACTION_VIEW)
    web_intent.setData(
        autoclass("android.net.Uri").parse("https://www.office.com/launch/excel")
    )
    try:
        activity.startActivity(web_intent)
    except Exception as error:
        return (
            f"Excel tersimpan sebagai {filename}, tetapi Excel Web tidak dapat dibuka: "
            f"{error}"
        )
    return (
        f"Excel tersimpan sebagai {filename}. Upload file itu ke Excel Web "
        "yang baru dibuka."
    )


def _copy_android_image(uri):
    if uri is None:
        raise ValueError("Foto tidak dipilih.")

    from jnius import autoclass

    activity = autoclass("org.kivy.android.PythonActivity").mActivity
    resolver = activity.getContentResolver()
    stream = resolver.openInputStream(uri)
    if stream is None:
        raise OSError("Foto tidak dapat dibuka.")

    bitmap_factory = autoclass("android.graphics.BitmapFactory")
    bitmap_options = autoclass("android.graphics.BitmapFactory$Options")
    options = bitmap_options()
    options.inJustDecodeBounds = True
    try:
        bitmap_factory.decodeStream(stream, None, options)
    finally:
        stream.close()

    max_dimension = 1600
    sample_size = 1
    while max(options.outWidth, options.outHeight) // sample_size > max_dimension * 2:
        sample_size *= 2
    options.inSampleSize = sample_size
    options.inJustDecodeBounds = False
    stream = resolver.openInputStream(uri)
    if stream is None:
        raise OSError("Foto tidak dapat dibuka.")
    try:
        bitmap = bitmap_factory.decodeStream(stream, None, options)
    finally:
        stream.close()

    if bitmap is None:
        raise ValueError("Format foto tidak didukung.")

    output_stream = None
    output_path = ""
    width = bitmap.getWidth()
    height = bitmap.getHeight()
    if max(width, height) > max_dimension:
        scale = max_dimension / max(width, height)
        scaled_bitmap = autoclass("android.graphics.Bitmap").createScaledBitmap(
            bitmap,
            max(1, int(width * scale)),
            max(1, int(height * scale)),
            True,
        )
        bitmap.recycle()
        bitmap = scaled_bitmap

    app_data_dir = App.get_running_app().user_data_dir
    os.makedirs(app_data_dir, exist_ok=True)
    file_descriptor, output_path = tempfile.mkstemp(
        prefix="earthglow_photo_",
        suffix=".jpg",
        dir=app_data_dir,
    )
    os.close(file_descriptor)
    try:
        output_stream = autoclass("java.io.FileOutputStream")(output_path)
        compress_format = autoclass("android.graphics.Bitmap$CompressFormat").JPEG
        if not bitmap.compress(compress_format, 90, output_stream):
            raise OSError("Foto tidak berhasil disimpan.")
        output_stream.flush()
    except Exception:
        if output_path and os.path.exists(output_path):
            os.remove(output_path)
        raise
    finally:
        if output_stream is not None:
            output_stream.close()
        bitmap.recycle()
    return output_path


def open_image_picker(on_select, on_error=None):
    if platform == "android":
        global _pending_image_selection, _image_picker_bound
        from android import activity
        from jnius import autoclass

        def handle_selection(image_path, error_message):
            if error_message:
                if on_error:
                    on_error(error_message)
                else:
                    print(error_message)
            elif image_path:
                on_select(image_path)

        if not _image_picker_bound:
            activity.bind(on_activity_result=_handle_android_activity_result)
            _image_picker_bound = True
        if _pending_image_selection is not None:
            raise RuntimeError("Pemilih foto sedang digunakan.")
        _pending_image_selection = handle_selection

        intent_class = autoclass("android.content.Intent")
        intent = intent_class(intent_class.ACTION_OPEN_DOCUMENT)
        intent.addCategory(intent_class.CATEGORY_OPENABLE)
        intent.setType("image/*")
        try:
            autoclass("org.kivy.android.PythonActivity").mActivity.startActivityForResult(
                intent,
                _IMAGE_PICKER_REQUEST_CODE,
            )
        except Exception:
            _pending_image_selection = None
            raise
        return

    def show_picker():
        initial_path = os.path.expanduser("~")
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

    show_picker()


def scrollable_form_content(form, actions):
    form.size_hint_y = None
    form.bind(minimum_height=form.setter("height"))
    scroll = ScrollView(do_scroll_x=False, do_scroll_y=True)
    scroll.add_widget(form)
    content = BoxLayout(orientation="vertical", spacing=dp(6))
    content.add_widget(scroll)
    content.add_widget(actions)
    return content


class WelcomeScreen(Screen):
    pass


class LoginScreen(Screen):
    pesan = StringProperty("")

    def clear_form(self):
        self.ids.email_input.text = ""
        self.ids.password_input.text = ""
        self.pesan = ""

    def login(self):
        email = self.ids.email_input.text.strip()
        password = self.ids.password_input.text.strip()

        if email == "" or password == "":
            self.pesan = "Email dan password wajib diisi"
            return

        user = get_admin_by_email_and_password(email, password)
        if user is None:
            self.pesan = "Email atau password salah"
            return

        self.pesan = ""
        database_module.activate_admin_database(user["id"])
        self.manager.current_user = user
        self.manager.current = "dashboard"


class RegisterScreen(Screen):
    pesan = StringProperty("")

    def clear_form(self):
        for field_id in (
            "nama_input",
            "toko_input",
            "email_input",
            "password_input",
            "konfirmasi_input",
        ):
            self.ids[field_id].text = ""
        self.pesan = ""

    def register(self):
        name = self.ids.nama_input.text.strip()
        store_name = self.ids.toko_input.text.strip()
        email = self.ids.email_input.text.strip()
        password = self.ids.password_input.text.strip()
        confirmation = self.ids.konfirmasi_input.text.strip()

        if not all((name, store_name, email, password, confirmation)):
            self.pesan = "Semua data wajib diisi"
            return
        if password != confirmation:
            self.pesan = "Konfirmasi password tidak sama"
            return

        try:
            user = database_module.create_admin_account(
                name,
                email,
                password,
                store_name,
            )
            database_module.activate_admin_database(user["id"])
        except ValueError as error:
            self.pesan = str(error)
            return

        self.pesan = ""
        self.manager.current_user = user
        self.manager.current = "dashboard"


class DashboardScreen(Screen):
    total_products = StringProperty("0")
    total_stock = StringProperty("0")
    total_orders = StringProperty("0")
    new_online_orders = StringProperty("0")
    total_direct = StringProperty("0")
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
            self.total_orders = str(get_order_count("online"))
            self.new_online_orders = str(get_new_online_order_count())
            self.total_direct = str(get_order_count("direct"))

        except Exception as error:
            print("Dashboard error:", error)
            self.total_products = "0"
            self.total_stock = "0"
            self.total_orders = "0"
            self.new_online_orders = "0"
            self.total_direct = "0"

    def load_catalog(self, products):
        catalog = self.ids.catalog_grid
        catalog.clear_widgets()

        for product in products:
            product_id, name, brand, price, description, stock, image_path = product[:7]
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
    payment_button_text = StringProperty("KONFIRMASI PEMBAYARAN")

    def on_pre_enter(self, *args):
        self.refresh_product_options()
        if not getattr(self, "_payment_spinner_bound", False):
            self.ids.payment_spinner.bind(
                text=lambda spinner, value: self.select_payment(value)
            )
            self._payment_spinner_bound = True
        self.select_payment(self.ids.payment_spinner.text)
        self.refresh_cashier()

    def refresh_product_options(self):
        products = get_products()
        self.product_options = {
            (
                f"#{product[0]} - {product[1]} | "
                f"Rp{int(product[3]):,} | stok {product[5] or 0}"
            ): product
            for product in products
        }
        self.ids.product_spinner.values = list(self.product_options)
        self.ids.product_spinner.text = (
            next(iter(self.product_options), "Belum ada produk")
        )
        self.ids.add_product_button.disabled = not self.product_options

    def add_selected_product(self):
        product = self.product_options.get(self.ids.product_spinner.text)
        if product is None:
            self.ids.cashier_message.text = "Pilih produk yang tersedia."
            return
        product_id = product[0]
        item = self.manager.cart_items.get(product_id)
        current_quantity = item["quantity"] if item else 0
        if current_quantity >= int(product[5] or 0):
            self.ids.cashier_message.text = f"Stok {product[1]} tidak mencukupi."
            return
        if item:
            item["quantity"] += 1
        else:
            self.manager.cart_items[product_id] = {
                "product": product,
                "quantity": 1,
            }
        self.ids.cashier_message.text = ""
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
                text="Keranjang kosong. Pilih produk dari katalog di atas.",
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
        self.payment_button_text = (
            "KONFIRMASI PEMBAYARAN"
            if is_cash
            else "TAMPILKAN QRIS SIMULASI"
        )
        self.ids.cash_received_row.height = dp(42) if is_cash else 0
        self.update_change()

    def request_payment(self):
        if not self.manager.cart_items:
            self.ids.cashier_message.text = "Keranjang masih kosong"
            return
        if self.payment_method == "QRIS":
            self.show_qris_simulation()
        else:
            self.complete_sale()

    def show_qris_simulation(self):
        content = BoxLayout(
            orientation="vertical",
            spacing=dp(12),
            padding=dp(16),
        )
        with content.canvas.before:
            Color(1, 1, 1, 1)
            content.background = Rectangle(pos=content.pos, size=content.size)
        content.bind(
            pos=lambda widget, value: setattr(widget.background, "pos", value),
            size=lambda widget, value: setattr(widget.background, "size", value),
        )
        content.add_widget(Label(
            text="QRIS • SIMULASI",
            size_hint_y=None,
            height=dp(40),
            font_size="20sp",
            bold=True,
            color=(0.12, 0.35, 0.25, 1),
        ))
        content.add_widget(Label(
            text=f"Total tagihan\n{self.total_text}",
            size_hint_y=None,
            height=dp(80),
            font_size="24sp",
            bold=True,
            color=(0.12, 0.25, 0.18, 1),
        ))
        content.add_widget(Label(
            text=(
                "Mode demo: pembayaran tidak dikirim ke DANA, ShopeePay, "
                "bank, atau gateway. Tidak ada kode yang dapat dipindai."
            ),
            halign="center",
            valign="middle",
            text_size=(dp(340), None),
            color=(0.42, 0.35, 0.18, 1),
        ))
        popup = Popup(
            title="Pembayaran QRIS Simulasi",
            content=content,
            size_hint=(0.9, 0.6),
        )
        actions = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(8))
        actions.add_widget(Button(
            text="Simulasikan berhasil",
            background_normal="",
            background_color=(0.18, 0.52, 0.38, 1),
            on_release=lambda button: self.finish_qris_simulation(popup),
        ))
        actions.add_widget(Button(
            text="Batal",
            on_release=lambda button: popup.dismiss(),
        ))
        content.add_widget(actions)
        popup.open()

    def finish_qris_simulation(self, popup):
        popup.dismiss()
        self.complete_sale(qris_confirmed=True)

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
        popup = Popup(
            title="Pembayaran Telah Berhasil",
            content=content,
            size_hint=(0.92, 0.82),
        )
        content.add_widget(Button(
            text="Tutup Nota",
            size_hint_y=None,
            height=dp(46),
            background_normal="",
            background_color=(0.18, 0.52, 0.38, 1),
            on_release=lambda button: popup.dismiss()
        ))
        popup.open()

    def complete_sale(self, qris_confirmed=False):
        if not self.manager.cart_items:
            self.ids.cashier_message.text = "Keranjang masih kosong"
            return

        customer_name = self.ids.customer_input.text.strip() or "Pelanggan umum"
        payment = self.payment_method
        if payment == "QRIS" and not qris_confirmed:
            self.show_qris_simulation()
            return
        status = "Lunas"
        payment_record = "QRIS (simulasi)" if payment == "QRIS" else "Cash"
        received = 0
        if payment == "Cash":
            try:
                received = int(self.ids.cash_received.text or 0)
            except ValueError:
                self.ids.cashier_message.text = "Nominal uang diterima harus berupa angka"
                return
            if received < self.total_amount:
                self.ids.cashier_message.text = "Uang diterima masih kurang dari total belanja"
                return

        latest_products = {product[0]: product for product in get_products()}
        for product_id, item in self.manager.cart_items.items():
            latest_product = latest_products.get(product_id)
            if not latest_product or item["quantity"] > int(latest_product[5] or 0):
                self.ids.cashier_message.text = f"Stok {item['product'][1]} berubah. Periksa keranjang."
                return
            if latest_product[7] is None:
                self.ids.cashier_message.text = f"Isi HPP produk {latest_product[1]} sebelum mencatat penjualan"
                return

        sale_items = []
        receipt_lines = [
            "EARTHGLOW SOAP",
            "PEMBAYARAN TELAH BERHASIL",
            "NOTA PEMBAYARAN",
            datetime.now().strftime("Tanggal: %d-%m-%Y %H:%M"),
            f"Pelanggan: {customer_name}",
            "-" * 30
        ]
        total_quantity = 0
        total_cost = 0
        order_lines = []
        for product_id, item in self.manager.cart_items.items():
            product = latest_products[product_id]
            quantity = item["quantity"]
            sale_items.append(f"{product[1]} x{quantity}")
            receipt_lines.append(f"{product[1]} x{quantity}  Rp{int(product[3]) * quantity:,}")
            total_quantity += quantity
            total_cost += int(product[7]) * quantity
            order_lines.append({
                "product_id": product_id,
                "product_name": product[1],
                "quantity": quantity,
                "unit_price": int(product[3]),
                "unit_cost": int(product[7]),
            })

        try:
            add_order(
                customer_name,
                "-",
                ", ".join(sale_items),
                total_quantity,
                self.total_amount,
                payment_record,
                status,
                total_cost,
                "direct",
                order_lines,
            )
        except ValueError as error:
            self.ids.cashier_message.text = str(error)
            return
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
        self.ids.payment_spinner.text = "Cash"
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
            cost_text = "Belum diisi" if product[7] is None else f"Rp{product[7]:,}"

            text = (
                f"ID: {product_id}\n"
                f"{name}\n"
                f"Merek: {brand}\n"
                f"Harga: Rp{price:,} | HPP: {cost_text}\n"
                f"Stok: {stock}"
            )

            row = BoxLayout(
                orientation="vertical",
                size_hint_y=None,
                padding=dp(10),
                spacing=dp(6),
            )
            with row.canvas.before:
                Color(1, 1, 1, 1)
                row.background = Rectangle(pos=row.pos, size=row.size)
                Color(0.75, 0.82, 0.77, 1)
                row.border = Line(rectangle=(*row.pos, *row.size), width=1)
            row.bind(
                pos=lambda widget, value: (
                    setattr(widget.background, "pos", value),
                    setattr(widget.border, "rectangle", (*widget.pos, *widget.size)),
                ),
                size=lambda widget, value: (
                    setattr(widget.background, "size", value),
                    setattr(widget.border, "rectangle", (*widget.pos, *widget.size)),
                ),
            )
            if image_path and os.path.isfile(image_path):
                row.add_widget(Image(
                    source=image_path,
                    size_hint_y=None,
                    height=dp(118),
                    fit_mode="contain",
                ))
            else:
                row.add_widget(Label(
                    text="Tanpa foto",
                    size_hint_y=None,
                    height=dp(70),
                    font_size="13sp",
                    color=(0.42, 0.48, 0.43, 1),
                ))
            product_details = Label(
                text=text,
                size_hint_y=None,
                halign="left",
                valign="top",
                font_size="13sp",
                color=(0.12, 0.25, 0.18, 1),
            )
            product_details.bind(
                width=lambda label, width: setattr(label, "text_size", (width, None)),
                texture_size=lambda label, size: setattr(
                    label, "height", size[1] + dp(8)
                ),
            )
            row.add_widget(product_details)
            row.add_widget(Button(
                text="Edit",
                size_hint_y=None,
                height=dp(42),
                on_release=lambda button, item=product: self.open_product_form(item)
            ))
            row.bind(minimum_height=row.setter("height"))
            self.ids.product_list.add_widget(row)

    def choose_image(self, image_input, message, on_selected):
        def image_selected(file_path):
            image_input.text = os.path.basename(file_path)
            message.text = "Foto berhasil dipilih."
            on_selected(file_path)

        try:
            open_image_picker(image_selected, lambda error: setattr(message, "text", error))
        except Exception as error:
            message.text = f"Tidak dapat membuka pemilih foto: {error}"

    def open_product_form(self, product=None):
        is_edit = product is not None
        form = BoxLayout(
            orientation="vertical",
            padding=dp(12),
            spacing=dp(8),
            size_hint_y=None,
        )
        name_input = TextInput(hint_text="Nama barang", text=product[1] if is_edit else "", multiline=False, size_hint_y=None, height=dp(44))
        brand_input = TextInput(hint_text="Merek", text=product[2] or "" if is_edit else "", multiline=False, size_hint_y=None, height=dp(44))
        price_input = TextInput(hint_text="Harga jual (angka)", text=str(product[3]) if is_edit else "", multiline=False, input_filter="int", size_hint_y=None, height=dp(44))
        cost_input = TextInput(hint_text="HPP / biaya modal per produk (angka)", text=str(product[7]) if is_edit and product[7] is not None else "", multiline=False, input_filter="int", size_hint_y=None, height=dp(44))
        description_input = TextInput(hint_text="Deskripsi", text=product[4] or "" if is_edit else "", multiline=False, size_hint_y=None, height=dp(44))
        stock_input = TextInput(hint_text="Stok", text=str(product[5] or 0) if is_edit else "", multiline=False, input_filter="int", size_hint_y=None, height=dp(44))
        selected_image_path = product[6] or "" if is_edit else ""
        image_input = TextInput(
            hint_text="Foto belum dipilih",
            text=os.path.basename(selected_image_path) or "Belum dipilih",
            multiline=False,
            readonly=True,
            size_hint_x=0.68,
        )
        message = Label(text="", size_hint_y=None, height=dp(36), halign="left", valign="middle", text_size=(0, None))
        message.bind(width=lambda label, width: setattr(label, "text_size", (width, None)))

        def set_product_image(file_path):
            nonlocal selected_image_path
            selected_image_path = file_path

        form.add_widget(name_input)
        form.add_widget(brand_input)
        form.add_widget(price_input)
        form.add_widget(cost_input)
        form.add_widget(description_input)
        form.add_widget(stock_input)
        image_row = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(6))
        image_row.add_widget(image_input)
        image_row.add_widget(Button(
            text="Pilih Foto",
            on_release=lambda button: self.choose_image(
                image_input,
                message,
                set_product_image,
            ),
        ))
        form.add_widget(image_row)
        form.add_widget(message)
        actions = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(8), padding=(dp(12), 0))
        popup = Popup(
            title="Ubah Barang" if is_edit else "Tambah Barang",
            content=scrollable_form_content(form, actions),
            size_hint=(0.92, 0.78),
        )

        def save_product(button):
            name = name_input.text.strip()
            if not name or not price_input.text or not cost_input.text or not stock_input.text:
                message.text = "Nama, harga jual, HPP, dan stok wajib diisi"
                return
            try:
                price = int(price_input.text)
                cost_price = int(cost_input.text)
                stock = int(stock_input.text)
                if price < 0 or cost_price < 0 or stock < 0:
                    raise ValueError
                values = (
                    name,
                    brand_input.text.strip(),
                    price,
                    description_input.text.strip(),
                    stock,
                    selected_image_path,
                    cost_price
                )
                if is_edit:
                    update_product(product[0], *values)
                else:
                    add_product(*values)
                popup.dismiss()
                self.load_products()
            except ValueError:
                message.text = "Harga jual, HPP, dan stok harus angka nol atau lebih"

        actions.add_widget(Button(text="Simpan", on_release=save_product))
        actions.add_widget(Button(text="Batal", on_release=lambda button: popup.dismiss()))
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
                if product[7] is None:
                    message.text = "Isi HPP produk melalui menu Edit sebelum mencatat penjualan"
                    return
                total = int(product[3]) * quantity
                customer_name = customer_input.text.strip() or "Pelanggan umum"
                address = address_input.text.strip() or "-"
                payment = payment_spinner.text or 'Cash'
                order_status = status_spinner.text or 'Lunas'
                cost_total = int(product[7]) * quantity
                add_order(
                    customer_name,
                    address,
                    product[1],
                    quantity,
                    total,
                    payment,
                    order_status,
                    cost_total,
                    "direct",
                    [{
                        "product_id": product[0],
                        "product_name": product[1],
                        "quantity": quantity,
                        "unit_price": int(product[3]),
                        "unit_cost": int(product[7]),
                    }],
                )
                popup.dismiss()
                self.load_products()
            except ValueError:
                message.text = "Jumlah harus lebih dari nol dan tidak melebihi stok"

        actions.add_widget(Button(text="Simpan Penjualan", on_release=save_sale))
        actions.add_widget(Button(text="Batal", on_release=lambda button: popup.dismiss()))
        form.add_widget(actions)
        popup.open()


class ChannelTransactionsScreen(Screen):
    channel = StringProperty("")
    screen_title = StringProperty("")

    def on_pre_enter(self, *args):
        self.load_orders()

    @property
    def manages_returns(self):
        return self.channel == "returns"

    def add_record_card(
        self,
        container,
        fields,
        action_text=None,
        action_callback=None,
        action_disabled=False,
    ):
        card = BoxLayout(
            orientation="vertical",
            size_hint_y=None,
            padding=(dp(8), dp(6)),
            spacing=dp(3),
        )
        with card.canvas.before:
            Color(1, 1, 1, 1)
            card.background = Rectangle(pos=card.pos, size=card.size)
            Color(0.75, 0.82, 0.77, 1)
            card.outline = Line(rectangle=(*card.pos, *card.size), width=1)
        card.bind(
            pos=lambda widget, value: (
                setattr(widget.background, "pos", value),
                setattr(widget.outline, "rectangle", (*widget.pos, *widget.size)),
            ),
            size=lambda widget, value: (
                setattr(widget.background, "size", value),
                setattr(widget.outline, "rectangle", (*widget.pos, *widget.size)),
            ),
        )
        for label_text, value_text in fields:
            row = BoxLayout(size_hint_y=None, height=dp(32), spacing=dp(6))
            key = Label(
                text=f"{label_text}:",
                size_hint_x=0.36,
                halign="left",
                valign="middle",
                font_size="12sp",
                bold=True,
                color=(0.18, 0.36, 0.27, 1),
                text_size=(0, None),
            )
            value = Label(
                text=str(value_text),
                size_hint_x=0.64,
                halign="left",
                valign="middle",
                font_size="12sp",
                color=(0.12, 0.2, 0.15, 1),
                text_size=(0, None),
            )
            key.bind(width=lambda widget, width: setattr(widget, "text_size", (width, None)))
            value.bind(
                width=lambda widget, width: setattr(widget, "text_size", (width, None)),
                texture_size=lambda widget, size, row=row: setattr(
                    row, "height", max(dp(32), size[1] + dp(8))
                ),
            )
            row.add_widget(key)
            row.add_widget(value)
            card.add_widget(row)
        if action_text and action_callback:
            action_button = Button(
                text=action_text,
                size_hint_y=None,
                height=dp(42),
                font_size="13sp",
                background_normal="",
                background_color=(0.18, 0.52, 0.38, 1),
                disabled=action_disabled,
                on_release=action_callback,
            )
            card.add_widget(action_button)
        card.bind(minimum_height=card.setter("height"))
        container.add_widget(card)

    def load_orders(self):
        channels = ("direct", "online") if self.manages_returns else (self.channel,)
        summaries = [get_channel_financial_summary(channel) for channel in channels]
        count = sum(summary[0] for summary in summaries)
        revenue = sum(summary[1] for summary in summaries)
        gross_profit = sum(summary[2] for summary in summaries)
        no_hpp = sum(summary[3] for summary in summaries)
        refund_amount = sum(summary[4] for summary in summaries)
        loss_amount = sum(summary[5] for summary in summaries)
        profit_loss = sum(summary[6] for summary in summaries)
        unknown_return_profit = sum(summary[7] for summary in summaries)
        self.ids.channel_summary.text = (
            f"Transaksi lunas: {count}    Omzet: Rp{revenue:,}\n"
            f"Laba kotor: Rp{gross_profit:,}    Tanpa HPP: {no_hpp}\n"
            f"Refund: Rp{refund_amount:,}    Kerugian retur: Rp{loss_amount:,}\n"
            f"Laba berkurang: Rp{profit_loss:,}    Retur tanpa HPP: {unknown_return_profit}"
        )
        table = self.ids.orders_table
        table.clear_widgets()
        table.cols = 1
        table.size_hint = (1, None)
        table.width = self.ids.orders_scroll.width
        if not getattr(table, "tracks_minimum_height", False):
            table.bind(minimum_height=table.setter("height"))
            table.tracks_minimum_height = True

        orders = get_orders(None if self.manages_returns else self.channel)
        if not orders:
            self.add_record_card(table, [("Data transaksi", "Belum ada transaksi")])
        else:
            for order in orders:
                order_id, customer, address, product, quantity, total, payment, status, created_at, cost_total, _ = order
                order_profit = (
                    f"Rp{total - cost_total:,}" if cost_total is not None else "Belum ada HPP"
                )
                fields = [
                    ("No. transaksi", order_id),
                    ("Tanggal", (created_at or "-").split(" ")[0]),
                    ("Saluran", "Langsung" if order[10] == "direct" else "Online"),
                    ("Nama pemesan", customer or "Pelanggan umum"),
                    ("Alamat", address or "-"),
                    ("Barang", product or "-"),
                    ("Jumlah", quantity or 0),
                    ("Total harga", f"Rp{total:,}"),
                    ("HPP", f"Rp{cost_total:,}" if cost_total is not None else "Belum ada HPP"),
                    ("Laba kotor", order_profit),
                    ("Pembayaran", payment or "Cash"),
                    ("Status", status or "Belum Lunas"),
                ]
                if order[10] == "online" and not self.manages_returns:
                    platform_name, buyer_note = get_order_metadata(order_id)
                    fields.extend([
                        ("Platform", platform_name or "Web / Manual"),
                        ("Catatan pembeli", buyer_note or "-"),
                    ])
                action_callback = None
                action_text = None
                if self.manages_returns:
                    action_text = "PROSES RETUR"
                    action_callback = lambda button, order=order: self.open_return_form(order)
                elif self.channel == "online":
                    if status == "Baru":
                        action_text = "TERIMA & PROSES"
                        action_callback = lambda button, order=order: self.advance_online_order(
                            order, "Baru", "Diproses"
                        )
                    elif status == "Diproses":
                        action_text = "PESANAN SIAP"
                        action_callback = lambda button, order=order: self.advance_online_order(
                            order, "Diproses", "Siap"
                        )
                    elif status == "Siap":
                        action_text = "SELESAIKAN & TAMPILKAN LABEL"
                        action_callback = lambda button, order=order: self.advance_online_order(
                            order, "Siap", "Lunas"
                        )
                    elif status == "Lunas":
                        action_text = "LIHAT STRUK / LABEL (SIMULASI)"
                        action_callback = lambda button, order=order: self.show_online_label(order)
                self.add_record_card(
                    table,
                    fields,
                    action_text,
                    action_callback,
                    action_disabled=self.manages_returns and status != "Lunas",
                )
        if self.manages_returns:
            self.load_return_history()

    def advance_online_order(self, order, expected_status, new_status):
        try:
            update_order_status(order[0], expected_status, new_status, "online")
        except ValueError as error:
            self.ids.channel_message.text = str(error)
            self.load_orders()
            return

        if new_status == "Diproses":
            self.ids.channel_message.text = (
                "Pesanan diterima. Diteruskan ke persiapan (simulasi)."
            )
        elif new_status == "Siap":
            self.ids.channel_message.text = "Pesanan ditandai siap diambil / diserahkan."
        else:
            self.ids.channel_message.text = "Pesanan selesai dan tercatat lunas."
        self.load_orders()
        self.manager.get_screen("dashboard").refresh_dashboard()
        if new_status == "Lunas":
            self.show_online_label(order)

    def open_pos(self):
        self.manager.current = "cashier"

    def show_online_label(self, order):
        order_id, customer, address, product, quantity, total = order[:6]
        platform_name, buyer_note = get_order_metadata(order_id)
        items = get_order_items(order_id)
        item_lines = [
            f"{item[2]} x{item[3]}"
            for item in items
        ] or [f"{product or '-'} x{quantity or 0}"]
        label_text = "\n".join([
            "EARTHGLOW SOAP",
            "STRUK / LABEL PESANAN ONLINE",
            f"No. pesanan: {order_id}",
            f"Platform: {platform_name or 'Web / Manual'}",
            f"Pelanggan: {customer or '-'}",
            f"Alamat: {address or '-'}",
            "Barang:",
            *item_lines,
            f"Total: Rp{total:,}",
            f"Pembayaran: Sudah dibayar online",
            f"Catatan: {buyer_note or '-'}",
            "",
            "SIMULASI CETAK - tidak dikirim ke printer atau kurir.",
        ])
        content = BoxLayout(
            orientation="vertical",
            spacing=dp(8),
            padding=dp(12),
        )
        with content.canvas.before:
            Color(1, 1, 1, 1)
            content.background = Rectangle(pos=content.pos, size=content.size)
        content.bind(
            pos=lambda widget, value: setattr(widget.background, "pos", value),
            size=lambda widget, value: setattr(widget.background, "size", value),
        )
        scroll = ScrollView(do_scroll_x=False)
        label = Label(
            text=label_text,
            size_hint_y=None,
            halign="left",
            valign="top",
            font_size="15sp",
            color=(0.12, 0.2, 0.15, 1),
        )
        label.bind(
            width=lambda widget, width: setattr(widget, "text_size", (width, None))
        )
        label.bind(
            texture_size=lambda widget, size: setattr(widget, "height", size[1])
        )
        scroll.add_widget(label)
        content.add_widget(scroll)
        popup = Popup(
            title="Pratinjau Label Simulasi",
            content=content,
            size_hint=(0.92, 0.78),
        )
        content.add_widget(Button(
            text="Tutup",
            size_hint_y=None,
            height=dp(44),
            on_release=lambda button: popup.dismiss(),
        ))
        popup.open()

    def create_order_form(self):
        if self.manages_returns:
            return
        products = get_products()
        if not products:
            self.ids.channel_message.text = "Tambahkan produk terlebih dahulu."
            return
        is_online = self.channel == "online"
        form = BoxLayout(
            orientation="vertical",
            padding=dp(12),
            spacing=dp(7),
            size_hint_y=None,
        )
        form.add_widget(Label(
            text=(
                "Mode simulasi: pesanan online dicatat manual."
                if is_online
                else "Pilih produk dan jumlah. Stok akan berkurang otomatis."
            ),
            size_hint_y=None,
            height=dp(38),
        ))
        product_options = {
            f"{product[0]} - {product[1]} (stok {product[5] or 0})": product
            for product in products
        }
        product_spinner = Spinner(
            text=next(iter(product_options)),
            values=list(product_options),
            size_hint_y=None,
            height=dp(44),
        )
        customer_input = TextInput(
            hint_text="Nama pemesan",
            multiline=False,
            size_hint_y=None,
            height=dp(44),
        )
        address_input = TextInput(
            hint_text="Alamat pembeli / pengiriman",
            multiline=False,
            size_hint_y=None,
            height=dp(44),
        )
        quantity_input = TextInput(
            hint_text="Jumlah barang",
            multiline=False,
            input_filter="int",
            size_hint_y=None,
            height=dp(44),
        )
        platform_spinner = Spinner(
            text="GoFood",
            values=["GoFood", "GrabFood", "ShopeeFood", "Web / Manual"],
            size_hint_y=None,
            height=dp(44),
        )
        buyer_note_input = TextInput(
            hint_text="Catatan pembeli (opsional)",
            multiline=True,
            size_hint_y=None,
            height=dp(68),
        )
        payment_spinner = Spinner(
            text="Cash",
            values=["Cash", "QRIS"],
            size_hint_y=None,
            height=dp(44),
        )
        status_spinner = Spinner(
            text="Lunas",
            values=["Lunas", "Belum Lunas"],
            size_hint_y=None,
            height=dp(44),
        )
        message = Label(
            text="",
            size_hint_y=None,
            height=dp(44),
            halign="left",
            valign="middle",
        )
        message.bind(
            width=lambda label, width: setattr(label, "text_size", (width, None)),
            texture_size=lambda label, size: setattr(
                label, "height", max(dp(44), size[1] + dp(8))
            ),
        )
        form_widgets = [
            product_spinner,
            customer_input,
            address_input,
            quantity_input,
        ]
        if is_online:
            form_widgets.extend((platform_spinner, buyer_note_input))
        else:
            form_widgets.extend((payment_spinner, status_spinner))
        form_widgets.append(message)
        for widget in form_widgets:
            form.add_widget(widget)

        actions = BoxLayout(
            size_hint_y=None,
            height=dp(44),
            spacing=dp(8),
            padding=(dp(12), 0),
        )
        popup = Popup(
            title="Catat Transaksi Langsung" if self.channel == "direct" else "Tambah Pesanan Online",
            content=scrollable_form_content(form, actions),
            size_hint=(0.92, 0.88),
        )

        def save_order(button):
            try:
                product = product_options[product_spinner.text]
                quantity = int(quantity_input.text)
                if quantity <= 0:
                    raise ValueError("Jumlah harus lebih dari nol.")
                if product[7] is None:
                    raise ValueError(f"Isi HPP {product[1]} melalui Kelola Produk terlebih dahulu.")
                customer = customer_input.text.strip() or "Pelanggan umum"
                if self.channel == "online" and customer == "Pelanggan umum":
                    raise ValueError("Nama pemesan wajib diisi untuk pesanan online.")
                if self.channel == "online" and address_input.text.strip() == "":
                    raise ValueError("Alamat pengiriman wajib diisi untuk pesanan online.")
                address = address_input.text.strip() or "-"
                total = int(product[3]) * quantity
                cost_total = int(product[7]) * quantity
                payment = "Sudah Dibayar (Online)" if is_online else payment_spinner.text
                order_status = "Baru" if is_online else status_spinner.text
                add_order(
                    customer,
                    address,
                    product[1],
                    quantity,
                    total,
                    payment,
                    order_status,
                    cost_total,
                    self.channel,
                    [{
                        "product_id": product[0],
                        "product_name": product[1],
                        "quantity": quantity,
                        "unit_price": int(product[3]),
                        "unit_cost": int(product[7]),
                    }],
                    platform=platform_spinner.text if is_online else None,
                    buyer_note=buyer_note_input.text.strip() if is_online else "",
                )
            except (ValueError, KeyError) as error:
                message.text = str(error) or "Jumlah tidak valid."
                return
            popup.dismiss()
            self.ids.channel_message.text = (
                "Pesanan baru dicatat sebagai sudah dibayar online."
                if is_online
                else "Transaksi berhasil dicatat dan stok diperbarui."
            )
            self.load_orders()

        actions.add_widget(Button(text="Simpan transaksi", on_release=save_order))
        actions.add_widget(Button(text="Batal", on_release=lambda button: popup.dismiss()))
        popup.open()

    def open_return_form(self, order):
        order_id = order[0]
        items = get_order_items(order_id)
        if not items:
            self.ids.channel_message.text = (
                "Detail barang transaksi lama tidak tersedia, sehingga retur otomatis tidak dapat diproses."
            )
            return
        products = get_products()
        replacement_options = {
            f"{product[0]} - {product[1]} (stok {product[5] or 0})": product
            for product in products
        }
        item_options = {
            f"{item[0]} - {item[2]} (sisa dapat diretur {item[3] - item[6]})": item
            for item in items
            if item[3] - item[6] > 0
        }
        if not item_options:
            self.ids.channel_message.text = "Semua barang pada transaksi ini sudah diretur."
            return

        form = BoxLayout(
            orientation="vertical",
            padding=dp(12),
            spacing=dp(7),
            size_hint_y=None,
        )
        form.add_widget(Label(
            text=f"Nama pemesan: {order[1] or 'Pelanggan umum'}",
            size_hint_y=None,
            height=dp(34),
        ))
        item_spinner = Spinner(
            text=next(iter(item_options)),
            values=list(item_options),
            size_hint_y=None,
            height=dp(44),
        )
        quantity_input = TextInput(
            hint_text="Jumlah barang yang diretur",
            multiline=False,
            input_filter="int",
            size_hint_y=None,
            height=dp(44),
        )
        complaint_input = TextInput(
            hint_text="Keluhan pelanggan",
            multiline=True,
            size_hint_y=None,
            height=dp(80),
        )
        resolution_spinner = Spinner(
            text="Uang kembali",
            values=["Uang kembali", "Kirim pengganti"],
            size_hint_y=None,
            height=dp(44),
        )
        replacement_spinner = Spinner(
            text=next(iter(replacement_options)) if replacement_options else "Produk belum tersedia",
            values=list(replacement_options),
            size_hint_y=None,
            height=dp(44),
            opacity=0,
            disabled=True,
        )
        explanation = Label(
            text=(
                "Nilai barang retur = harga jual x jumlah. Pilih uang kembali atau "
                "kirim produk pengganti; HPP dan laba yang berkurang dihitung otomatis."
            ),
            size_hint_y=None,
            height=dp(62),
            halign="left",
            valign="middle",
        )
        explanation.bind(
            width=lambda label, width: setattr(label, "text_size", (width, None)),
            texture_size=lambda label, size: setattr(
                label, "height", max(dp(62), size[1] + dp(8))
            ),
        )
        message = Label(
            text="",
            size_hint_y=None,
            height=dp(40),
            halign="left",
            valign="middle",
        )
        message.bind(
            width=lambda label, width: setattr(label, "text_size", (width, None)),
            texture_size=lambda label, size: setattr(
                label, "height", max(dp(40), size[1] + dp(8))
            ),
        )

        def update_resolution(_spinner, value):
            is_replacement = value == "Kirim pengganti"
            replacement_spinner.opacity = 1 if is_replacement else 0
            replacement_spinner.disabled = not is_replacement

        resolution_spinner.bind(text=update_resolution)
        for widget in (
            item_spinner,
            quantity_input,
            complaint_input,
            resolution_spinner,
            replacement_spinner,
            explanation,
            message,
        ):
            form.add_widget(widget)
        actions = BoxLayout(
            size_hint_y=None,
            height=dp(44),
            spacing=dp(8),
            padding=(dp(12), 0),
        )
        popup = Popup(
            title="Proses Retur",
            content=scrollable_form_content(form, actions),
            size_hint=(0.92, 0.88),
        )

        def save_return(button):
            try:
                item = item_options[item_spinner.text]
                quantity = int(quantity_input.text)
                replacement_id = None
                if resolution_spinner.text == "Kirim pengganti":
                    replacement = replacement_options.get(replacement_spinner.text)
                    if replacement is None:
                        raise ValueError("Pilih barang pengganti.")
                    replacement_id = replacement[0]
                add_return(
                    order_id,
                    item[0],
                    quantity,
                    complaint_input.text,
                    resolution_spinner.text,
                    replacement_id,
                )
            except (ValueError, KeyError) as error:
                message.text = str(error)
                return
            popup.dismiss()
            self.ids.channel_message.text = (
                "Retur dicatat. Stok barang retur diperbarui; "
                "uang kembali atau penggantian tersimpan."
            )
            self.load_orders()

        actions.add_widget(Button(text="Simpan retur", on_release=save_return))
        actions.add_widget(Button(text="Batal", on_release=lambda button: popup.dismiss()))
        popup.open()

    def load_return_history(self):
        history = self.ids.return_history
        history.clear_widgets()
        history.cols = 1
        history.size_hint = (1, None)
        history.width = self.ids.return_scroll.width
        if not getattr(history, "tracks_minimum_height", False):
            history.bind(minimum_height=history.setter("height"))
            history.tracks_minimum_height = True
        return_records = get_returns(None if self.manages_returns else self.channel)
        for record in return_records:
            (
                _, _, _, customer, product, quantity, complaint,
                returned_price, _, resolution, _, replacement,
                _, loss, profit_loss, created_at
            ) = record
            fields = [
                ("Tanggal", (created_at or "-").split(" ")[0]),
                ("Nama pemesan", customer or "Pelanggan umum"),
                ("Barang retur", product),
                ("Jumlah", quantity),
                ("Keluhan", complaint),
                ("Penggantian", f"{resolution}: {replacement or 'uang kembali'}"),
                ("Nilai barang", f"Rp{returned_price:,}"),
                ("Nilai kerugian", f"Rp{loss:,}"),
                ("Laba berkurang", f"Rp{profit_loss:,}" if profit_loss is not None else "HPP belum ada"),
            ]
            self.add_record_card(history, fields)
        if not return_records:
            self.add_record_card(history, [("Riwayat retur", "Belum ada retur")])


class DirectTransactionsScreen(ChannelTransactionsScreen):
    channel = StringProperty("direct")
    screen_title = StringProperty("TRANSAKSI LANGSUNG")


class OrdersScreen(ChannelTransactionsScreen):
    channel = StringProperty("online")
    screen_title = StringProperty("PESANAN ONLINE")


class ReturnsScreen(ChannelTransactionsScreen):
    channel = StringProperty("returns")
    screen_title = StringProperty("RETUR BARANG")


class FinancialReportScreen(Screen):
    def on_pre_enter(self, *args):
        self.refresh_report()

    def refresh_report(self):
        count, revenue, today, profit, orders_without_cost = get_financial_summary()
        direct = get_channel_financial_summary("direct")
        online = get_channel_financial_summary("online")
        self.ids.report_summary.text = (
            f"LANGSUNG: omzet Rp{direct[1]:,} | laba kotor Rp{direct[2]:,} | "
            f"refund retur Rp{direct[4]:,} | kerugian retur Rp{direct[5]:,} | "
            f"laba berkurang Rp{direct[6]:,}\n"
            f"ONLINE: omzet Rp{online[1]:,} | laba kotor Rp{online[2]:,} | "
            f"refund retur Rp{online[4]:,} | kerugian retur Rp{online[5]:,} | "
            f"laba berkurang Rp{online[6]:,}\n"
            f"TOTAL: transaksi lunas {count} | omzet Rp{revenue:,} | hari ini Rp{today:,} | "
            f"laba kotor Rp{profit:,} | transaksi tanpa HPP {orders_without_cost}"
        )
        self.ids.report_summary.font_size = "13sp"

        table = self.ids.report_table
        table.clear_widgets()
        table.cols = 1
        table.size_hint = (1, None)
        table.width = self.ids.report_scroll.width
        if not getattr(table, "tracks_minimum_height", False):
            table.bind(minimum_height=table.setter("height"))
            table.tracks_minimum_height = True

        orders = [order for order in get_orders() if order[7] == "Lunas"]
        if not orders:
            ChannelTransactionsScreen.add_record_card(
                self,
                table,
                [("Laporan", "Belum ada transaksi lunas")],
            )
            return

        for row_index, order in enumerate(orders):
            _, customer_name, customer_address, product_name, quantity, total, payment_method, status, created_at, cost_total, channel = order
            gross_profit = (
                f"Rp{total - cost_total:,}" if cost_total is not None else "Belum ada HPP"
            )
            fields = [
                ("Tanggal", (created_at or "-").split(" ")[0]),
                ("Saluran", "Transaksi langsung" if channel == "direct" else "Pesanan online"),
                ("Nama pemesan", customer_name or "Pelanggan umum"),
                ("Alamat", customer_address or "-"),
                ("Barang", product_name or "-"),
                ("Jumlah", quantity or 0),
                ("Pembayaran", payment_method or "Cash"),
                ("Total", f"Rp{total:,}"),
                ("HPP", f"Rp{cost_total:,}" if cost_total is not None else "Belum ada HPP"),
                ("Laba kotor", gross_profit),
                ("Status", status or "Lunas"),
            ]
            ChannelTransactionsScreen.add_record_card(self, table, fields)

    def print_report(self):
        if platform == "android":
            content = BoxLayout(
                orientation="vertical",
                spacing=dp(12),
                padding=dp(16),
            )
            with content.canvas.before:
                Color(1, 1, 1, 1)
                content.background = Rectangle(pos=content.pos, size=content.size)
            content.bind(
                pos=lambda widget, value: setattr(widget.background, "pos", value),
                size=lambda widget, value: setattr(widget.background, "size", value),
            )
            content.add_widget(Label(
                text=(
                    "Cetak langsung belum didukung di Android. "
                    "Gunakan EKSPOR EXCEL untuk menyimpan laporan."
                ),
                color=(0.12, 0.25, 0.18, 1),
                halign="center",
                valign="middle",
            ))
            popup = Popup(
                title="Cetak Laporan",
                content=content,
                size_hint=(0.9, 0.42),
            )
            content.add_widget(Button(
                text="Tutup",
                size_hint_y=None,
                height=dp(44),
                on_release=lambda button: popup.dismiss(),
            ))
            popup.open()
            return

        count, revenue, today, profit, orders_without_cost = get_financial_summary()
        direct = get_channel_financial_summary("direct")
        online = get_channel_financial_summary("online")
        store_name = html.escape(
            (self.manager.current_user or {}).get("store_name") or "Toko"
        )
        rows = "".join(
            f"<tr><td>{html.escape(str(order[7] or '-'))}</td>"
            f"<td>{html.escape('Transaksi langsung' if order[10] == 'direct' else 'Pesanan online')}</td>"
            f"<td>{html.escape(str(order[1] or 'Pelanggan umum'))}</td>"
            f"<td>{html.escape(str(order[2] or '-'))}</td>"
            f"<td>{html.escape(str(order[3] or '-'))}</td>"
            f"<td>{html.escape(str(order[4] or 0))}</td>"
            f"<td>Rp{order[5]:,}</td>"
            f"<td>{'Belum ada HPP' if order[9] is None else f'Rp{order[9]:,}'}</td>"
            f"<td>{'Belum ada HPP' if order[9] is None else f'Rp{order[5] - order[9]:,}'}</td></tr>"
            for order in get_orders() if order[6] == "Lunas"
        )
        report_html = f"""<!doctype html><html><head><meta charset="utf-8">
<title>Laporan Keuangan {store_name}</title><style>
body{{font-family:Arial,sans-serif;margin:32px;color:#20382c}}h1{{color:#286344}}
table{{border-collapse:collapse;width:100%;margin-top:20px}}th,td{{border:1px solid #aaa;padding:8px;text-align:left}}
</style></head><body><h1>Laporan Keuangan {store_name}</h1>
<p>Transaksi langsung: omzet Rp{direct[1]:,}, laba kotor Rp{direct[2]:,}, retur Rp{direct[5]:,}<br>
Pesanan online: omzet Rp{online[1]:,}, laba kotor Rp{online[2]:,}, retur Rp{online[5]:,}<br>
Transaksi lunas: {count}<br>Pendapatan hari ini: Rp{today:,}<br>Total pendapatan: Rp{revenue:,}<br>
Laba kotor (omzet - HPP): Rp{profit:,}<br>Transaksi lunas tanpa HPP: {orders_without_cost}</p>
<table><thead><tr><th>Status</th><th>Saluran</th><th>Nama</th><th>Alamat</th><th>Produk</th><th>Qty</th><th>Omzet</th><th>HPP</th><th>Laba</th></tr></thead><tbody>{rows}</tbody></table>
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

    def export_excel(self):
        is_android = platform == "android"
        downloads_dir = (
            self.user_data_dir
            if is_android
            else os.path.join(os.path.expanduser("~"), "Downloads")
        )
        try:
            os.makedirs(downloads_dir, exist_ok=True)
            filename = f"laporan_keuangan_earthglow_{datetime.now():%Y%m%d_%H%M%S}.xlsx"
            output_path = os.path.join(downloads_dir, filename)
            user = self.manager.current_user or {}
            export_financial_workbook(
                get_orders(),
                output_path,
                get_returns(),
                user.get("store_name") or "Toko",
            )
        except OSError as error:
            self.ids.report_message.text = f"Gagal menyimpan Excel: {error}"
            return

        if is_android:
            def finish_export(destination_uri):
                try:
                    if destination_uri is None:
                        self.ids.report_message.text = "Ekspor Excel dibatalkan"
                        return
                    _copy_export_to_android_uri(output_path, destination_uri)
                except Exception as error:
                    self.ids.report_message.text = f"Gagal mengekspor Excel: {error}"
                else:
                    try:
                        self.ids.report_message.text = _open_excel_or_web(
                            destination_uri,
                            filename,
                        )
                    except Exception as error:
                        self.ids.report_message.text = (
                            f"Excel tersimpan sebagai {filename}, tetapi gagal dibuka: "
                            f"{error}"
                        )
                finally:
                    if os.path.exists(output_path):
                        os.remove(output_path)

            try:
                _request_android_excel_destination(filename, finish_export)
            except Exception as error:
                if os.path.exists(output_path):
                    os.remove(output_path)
                self.ids.report_message.text = f"Gagal membuka penyimpanan Excel: {error}"
            return

        self.ids.report_message.text = f"Excel tersimpan di Downloads: {filename}"


class ProfileScreen(Screen):
    def on_pre_enter(self, *args):
        self.refresh_profile()

    def refresh_profile(self):
        user = getattr(self.manager, "current_user", None)
        if user is None:
            self.manager.current = "welcome"
            return
        self.ids.nama_admin.text = user.get("name") or ""
        self.ids.email_admin.text = user.get("email") or ""
        self.ids.nama_toko.text = user.get("store_name") or ""
        self.ids.foto_profil.source = user.get("profile_photo", "")
        if self.ids.foto_profil.source:
            self.ids.foto_profil.reload()

    def pilih_foto(self):
        def set_profile_photo(file_path):
            self.ids.foto_profil.source = file_path
            self.ids.foto_profil.reload()
            self.ids.profile_message.text = "Foto profil berhasil dipilih"

        try:
            open_image_picker(
                set_profile_photo,
                lambda error: setattr(self.ids.profile_message, "text", error),
            )
        except Exception as error:
            self.ids.profile_message.text = f"Tidak dapat membuka pemilih foto: {error}"

    def save_profile(self):
        user = getattr(self.manager, "current_user", None)
        if user is None:
            self.manager.current = "welcome"
            return

        nama = self.ids.nama_admin.text.strip()
        email = self.ids.email_admin.text.strip()
        toko = self.ids.nama_toko.text.strip()

        if nama == "" or email == "" or toko == "":
            self.ids.profile_message.text = "Semua data wajib diisi"
            return

        try:
            update_admin_profile(
                user["id"],
                nama,
                email,
                user["password"],
                toko,
                self.ids.foto_profil.source or "",
            )
        except ValueError as error:
            self.ids.profile_message.text = str(error)
            return

        user.update({
            "name": nama,
            "email": email,
            "store_name": toko,
            "profile_photo": self.ids.foto_profil.source or "",
        })
        self.manager.current_user = user
        self.ids.profile_message.text = "Perubahan berhasil disimpan"

    def logout(self):
        self.manager.cart_items.clear()
        self.manager.current_user = None
        database_module.reset_active_database()
        self.manager.get_screen("login").clear_form()
        self.manager.get_screen("register").clear_form()
        self.manager.current = "welcome"


class NavigasiManager(ScreenManager):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.cart_items = {}
        self.current_user = None


class EarthGlowApp(App):
    def build(self):
        Window.clearcolor = (0.94, 0.98, 0.95, 1)
        if platform == "android":
            Window.softinput_mode = "below_target"
            database_module.configure_database(
                os.path.join(self.user_data_dir, "earthglow.db")
            )
        else:
            database_module.configure_database(
                os.path.abspath(database_module.DATABASE_NAME)
            )
        create_tables()
        if platform == "android":
            Window.fullscreen = "auto"
        else:
            Window.size = (420, 840)
            Window.minimum_width = 360
            Window.minimum_height = 640
        self.title = "EarthGlow Soap Admin"
        kv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "navigasi.kv")
        return Builder.load_file(kv_path)


if __name__ == "__main__":
    EarthGlowApp().run()