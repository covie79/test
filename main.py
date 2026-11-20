import csv
import os
import sqlite3
from datetime import datetime
from kivy.app import App
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.textinput import TextInput
from kivy.utils import platform

if platform == "android":
    from android import activity
    from android.permissions import Permission, request_permissions
    from jnius import autoclass

    PythonActivity = autoclass("org.kivy.android.PythonActivity")
    Intent = autoclass("android.content.Intent")


def format_price(value: float) -> str:
    text = f"{value:.2f}".rstrip("0").rstrip(".")
    return text if text else "0"


class BarcodePriceDB:
    def __init__(self, db_path="barcode_prices.db"):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.create_tables()

    def create_tables(self):
        with self.conn:
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS products (
                    barcode TEXT PRIMARY KEY,
                    name TEXT NOT NULL DEFAULT '',
                    price REAL NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            cur = self.conn.cursor()
            cur.execute("PRAGMA table_info(products)")
            columns = {row[1] for row in cur.fetchall()}
            if "name" not in columns:
                self.conn.execute("ALTER TABLE products ADD COLUMN name TEXT NOT NULL DEFAULT ''")

    def get_product(self, barcode: str):
        cur = self.conn.cursor()
        cur.execute(
            "SELECT name, price, updated_at FROM products WHERE barcode = ?",
            (barcode,),
        )
        return cur.fetchone()

    def save_product(self, barcode: str, name: str, price: float):
        now = datetime.now().isoformat(timespec="seconds")
        clean_name = name.strip()
        with self.conn:
            self.conn.execute("""
                INSERT INTO products (barcode, name, price, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(barcode) DO UPDATE SET
                    name = CASE
                        WHEN excluded.name != '' THEN excluded.name
                        ELSE products.name
                    END,
                    price = excluded.price,
                    updated_at = excluded.updated_at
            """, (barcode, clean_name, price, now))

    def get_all_products(self):
        cur = self.conn.cursor()
        cur.execute(
            "SELECT barcode, name, price, updated_at FROM products ORDER BY updated_at DESC"
        )
        return cur.fetchall()

    def close(self):
        if self.conn:
            self.conn.close()
            self.conn = None


class BarcodePriceApp(App):
    SCAN_REQUEST_CODE = 9001

    def get_export_candidates(self):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"barcode_prices_{timestamp}.csv"
        candidates = []

        if platform == "android":
            download_dir = "/storage/emulated/0/Download"
            if os.path.isdir(download_dir):
                candidates.append(os.path.join(download_dir, filename))
            candidates.append(os.path.join(self.user_data_dir, filename))
        else:
            candidates.append(os.path.join(os.getcwd(), filename))

        return candidates

    def make_button(self, text: str, height_dp: float = 54, font_sp: str = "16sp") -> Button:
        return Button(
            text=text,
            size_hint_y=None,
            height=dp(height_dp),
            font_size=font_sp,
        )

    def make_input(self, hint_text: str, input_filter=None) -> TextInput:
        kwargs = {
            "hint_text": hint_text,
            "multiline": False,
            "size_hint_y": None,
            "height": dp(52),
            "font_size": "17sp",
            "padding": [dp(14), dp(12)],
        }
        if input_filter is not None:
            kwargs["input_filter"] = input_filter
        return TextInput(**kwargs)

    def build(self):
        db_path = (
            os.path.join(self.user_data_dir, "barcode_prices.db")
            if platform == "android"
            else "barcode_prices.db"
        )
        self.db = BarcodePriceDB(db_path=db_path)

        if platform == "android":
            activity.bind(on_activity_result=self.on_activity_result)
            try:
                request_permissions([
                    Permission.CAMERA,
                    Permission.WRITE_EXTERNAL_STORAGE,
                    Permission.READ_EXTERNAL_STORAGE,
                ])
            except Exception:
                pass

        layout = BoxLayout(
            orientation="vertical",
            padding=[dp(20), dp(22), dp(20), dp(20)],
            spacing=dp(11),
        )

        title_label = Label(
            text="Barcode Price Tracker",
            size_hint_y=None,
            height=dp(36),
            font_size="21sp",
            bold=True,
        )

        self.status_label = Label(
            text="Scan or enter a barcode.",
            size_hint_y=None,
            height=dp(64),
            font_size="14sp",
            halign="center",
            valign="middle",
        )
        self.status_label.bind(
            size=lambda inst, val: setattr(inst, "text_size", (val[0], None))
        )

        self.barcode_input = self.make_input("Barcode (e.g., 8801234567890)")
        self.name_input = self.make_input("Product Name (e.g., Sparkling Water 500ml)")
        self.price_input = self.make_input("Price (e.g., 19.99)", input_filter="float")

        scan_btn = self.make_button("Scan Barcode (External App)", height_dp=56, font_sp="16sp")
        scan_btn.bind(on_press=self.on_scan_barcode)

        lookup_btn = self.make_button("Look Up Barcode", height_dp=52, font_sp="16sp")
        lookup_btn.bind(on_press=self.on_lookup)

        save_btn = self.make_button("Save / Update Item", height_dp=54, font_sp="16sp")
        save_btn.bind(on_press=self.on_save)

        export_btn = self.make_button("Export to CSV", height_dp=52, font_sp="16sp")
        export_btn.bind(on_press=self.on_export_csv)

        spacer = BoxLayout(size_hint_y=1)

        layout.add_widget(title_label)
        layout.add_widget(self.status_label)
        layout.add_widget(self.barcode_input)
        layout.add_widget(self.name_input)
        layout.add_widget(self.price_input)
        layout.add_widget(scan_btn)
        layout.add_widget(lookup_btn)
        layout.add_widget(save_btn)
        layout.add_widget(export_btn)
        layout.add_widget(spacer)
        return layout

    def on_stop(self):
        if hasattr(self, "db") and self.db:
            self.db.close()

    def on_scan_barcode(self, instance):
        if platform == "android":
            try:
                intent = Intent("com.google.zxing.client.android.SCAN")
                intent.putExtra("SCAN_MODE", "ONE_D_MODE,QR_CODE_MODE,PRODUCT_MODE")
                PythonActivity.mActivity.startActivityForResult(intent, self.SCAN_REQUEST_CODE)
                self.status_label.text = "Launching external barcode scanner..."
            except Exception as e:
                self.status_label.text = (
                    f"External scanner launch failed ({e}). Enter barcode manually."
                )
        else:
            self.show_desktop_scan_popup()

    def show_desktop_scan_popup(self):
        content = BoxLayout(orientation="vertical", padding=dp(16), spacing=dp(12))
        sample_input = self.make_input("Enter simulated scan result (e.g., 8801234567890)")

        btn_row = BoxLayout(size_hint_y=None, height=dp(54), spacing=dp(10))
        confirm_btn = self.make_button("Use Scanned Code", height_dp=54, font_sp="16sp")
        cancel_btn = self.make_button("Cancel", height_dp=54, font_sp="16sp")
        btn_row.add_widget(confirm_btn)
        btn_row.add_widget(cancel_btn)

        info_label = Label(
            text="External Scanner Simulator (PC)",
            size_hint_y=None,
            height=dp(34),
            font_size="16sp",
        )
        content.add_widget(info_label)
        content.add_widget(sample_input)
        content.add_widget(btn_row)

        popup = Popup(
            title="External Scan Test",
            content=content,
            size_hint=(0.9, None),
            height=dp(250),
            auto_dismiss=False,
        )

        def on_confirm(_instance):
            code = sample_input.text.strip()
            popup.dismiss()
            if code:
                self.handle_scanned_barcode(code)
            else:
                self.status_label.text = "No barcode scanned."

        def on_cancel(_instance):
            popup.dismiss()
            self.status_label.text = "Scan cancelled."

        confirm_btn.bind(on_press=on_confirm)
        cancel_btn.bind(on_press=on_cancel)
        popup.open()

    def on_activity_result(self, request_code, result_code, intent):
        if request_code != self.SCAN_REQUEST_CODE:
            return

        if result_code == -1 and intent is not None:
            contents = intent.getStringExtra("SCAN_RESULT")
            if contents:
                self.handle_scanned_barcode(str(contents).strip())
                return

        self.status_label.text = "Barcode scan cancelled or no result."

    def handle_scanned_barcode(self, code: str):
        self.barcode_input.text = code
        row = self.db.get_product(code)

        if row:
            old_name, old_price, updated_at = row
            old_price_val = float(old_price)
            typed_price_str = self.price_input.text.strip()
            typed_name_str = self.name_input.text.strip()

            if typed_price_str:
                try:
                    new_price_val = float(typed_price_str)
                    if new_price_val >= 0:
                        final_name = typed_name_str if typed_name_str else old_name
                        self.show_update_confirm_popup(
                            code, old_name, final_name, old_price_val, new_price_val
                        )
                        return
                except ValueError:
                    pass

            self.name_input.text = old_name
            self.price_input.text = format_price(old_price_val)
            name_display = old_name if old_name else "(No Name)"
            self.status_label.text = (
                f"Existing [{code}] {name_display}: {format_price(old_price_val)} "
                f"({updated_at}). Edit and tap Save."
            )
            self.price_input.focus = True
        else:
            self.price_input.text = ""
            self.status_label.text = f"New barcode [{code}]. Enter product name & price."
            self.name_input.focus = True

    def reset_for_next_scan(self, message: str):
        self.barcode_input.text = ""
        self.name_input.text = ""
        self.price_input.text = ""
        self.status_label.text = message
        self.barcode_input.focus = True

    def show_update_confirm_popup(
        self,
        barcode: str,
        old_name: str,
        new_name: str,
        old_price: float,
        new_price: float,
    ):
        content = BoxLayout(orientation="vertical", padding=dp(16), spacing=dp(12))
        old_name_disp = old_name if old_name else "(No Name)"
        new_name_disp = new_name if new_name else "(No Name)"
        msg = Label(
            text=(
                f"Barcode [{barcode}] already exists.\n"
                f"Current: {old_name_disp} / {format_price(old_price)}\n"
                f"New: {new_name_disp} / {format_price(new_price)}\n\n"
                "Do you want to update this item?"
            ),
            font_size="15sp",
            halign="center",
            valign="middle",
        )
        msg.bind(size=lambda inst, val: setattr(inst, "text_size", (val[0], None)))

        btn_row = BoxLayout(size_hint_y=None, height=dp(56), spacing=dp(12))
        yes_btn = self.make_button("YES", height_dp=56, font_sp="17sp")
        no_btn = self.make_button("NO", height_dp=56, font_sp="17sp")
        btn_row.add_widget(yes_btn)
        btn_row.add_widget(no_btn)

        content.add_widget(msg)
        content.add_widget(btn_row)

        popup = Popup(
            title="Item Already Registered",
            content=content,
            size_hint=(0.9, None),
            height=dp(310),
            auto_dismiss=False,
        )

        def on_yes(_instance):
            popup.dismiss()
            self.db.save_product(barcode, new_name, new_price)
            self.reset_for_next_scan(
                f"Updated: [{barcode}] {new_name_disp} -> {format_price(new_price)}."
            )

        def on_no(_instance):
            popup.dismiss()
            self.reset_for_next_scan("Item unchanged. Scan or enter the next barcode.")

        yes_btn.bind(on_press=on_yes)
        no_btn.bind(on_press=on_no)
        popup.open()

    def on_lookup(self, instance):
        code = self.barcode_input.text.strip()
        if not code:
            self.status_label.text = "Please enter or scan a barcode first."
            return

        row = self.db.get_product(code)
        if row:
            name, price, updated_at = row
            formatted = format_price(float(price))
            self.name_input.text = name
            self.price_input.text = formatted
            name_disp = name if name else "(No Name)"
            self.status_label.text = f"[{name_disp}] {formatted} (Updated: {updated_at})"
            self.price_input.focus = True
        else:
            self.price_input.text = ""
            self.status_label.text = "Barcode not found. Enter product name and price."
            self.name_input.focus = True

    def on_save(self, instance):
        code = self.barcode_input.text.strip()
        name = self.name_input.text.strip()
        price_str = self.price_input.text.strip()
        if not code or not price_str:
            self.status_label.text = "Please enter a barcode and a price."
            return

        try:
            new_price = float(price_str)
        except ValueError:
            self.status_label.text = "Invalid price format. Enter a valid number."
            return

        if new_price < 0:
            self.status_label.text = "Price cannot be negative."
            return

        existing = self.db.get_product(code)
        if existing:
            old_name, old_price, _ = existing
            final_name = name if name else old_name
            self.show_update_confirm_popup(
                code, old_name, final_name, float(old_price), new_price
            )
            return

        self.db.save_product(code, name, new_price)
        name_disp = name if name else "(No Name)"
        self.reset_for_next_scan(
            f"Saved: [{code}] {name_disp} -> {format_price(new_price)}."
        )

    def on_export_csv(self, instance):
        rows = self.db.get_all_products()
        if not rows:
            self.status_label.text = "No saved items to export."
            return

        last_error = None
        for output_path in self.get_export_candidates():
            try:
                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                with open(output_path, mode="w", newline="", encoding="utf-8-sig") as f:
                    writer = csv.writer(f)
                    writer.writerow(["Barcode", "Product Name", "Price", "Updated At"])
                    formatted_rows = [
                        [barcode, name, format_price(float(price)), updated_at]
                        for barcode, name, price, updated_at in rows
                    ]
                    writer.writerows(formatted_rows)
                self.status_label.text = f"Exported {len(rows)} items to: {output_path}"
                return
            except Exception as e:
                last_error = e

        self.status_label.text = f"Export failed: {last_error}"


if __name__ == "__main__":
    BarcodePriceApp().run()
