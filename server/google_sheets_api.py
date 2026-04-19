import os
import time
from datetime import datetime, timezone
import gspread
from google.oauth2.service_account import Credentials
from dotenv import load_dotenv

load_dotenv()

CACHE_TTL_MS = 5 * 60 * 1000  # 5 minutes in milliseconds

class GoogleSheetsDB:
    def __init__(self):
        self.client = None
        self.doc = None
        
        self.product_cache = None
        self.last_product_cache_time = 0
        
        self.user_cache = None
        self.last_user_cache_time = 0
        
        self.order_cache = None
        self.last_order_cache_time = 0
        
        self.read_request_timestamps = []
        self.write_request_timestamps = []

    def _record_read_request(self):
        self.read_request_timestamps.append(time.time() * 1000)

    def _record_write_request(self):
        self.write_request_timestamps.append(time.time() * 1000)

    def get_usage_metrics(self):
        now = time.time() * 1000
        one_minute_ago = now - 60000
        
        reads = [ts for ts in self.read_request_timestamps if ts > one_minute_ago]
        writes = [ts for ts in self.write_request_timestamps if ts > one_minute_ago]
        
        self.read_request_timestamps = reads
        self.write_request_timestamps = writes
        
        return {
            "readsPerMinute": len(reads),
            "writesPerMinute": len(writes)
        }

    def initialize(self):
        try:
            scopes = ['https://www.googleapis.com/auth/spreadsheets']
            
            # Reconstruct private key since it might contain escaped newlines
            private_key = os.environ.get("GOOGLE_PRIVATE_KEY", "").replace('\\n', '\n')
            
            credentials_dict = {
                "type": "service_account",
                "private_key": private_key,
                "client_email": os.environ.get("GOOGLE_SERVICE_ACCOUNT_EMAIL"),
                "token_uri": "https://oauth2.googleapis.com/token"
            }
            
            creds = Credentials.from_service_account_info(credentials_dict, scopes=scopes)
            self.client = gspread.authorize(creds)
            
            self._record_read_request()
            self.doc = self.client.open_by_key(os.environ.get("GOOGLE_SHEETS_ID"))
            print(f"✅ Google Sheets connected successfully")
            print(f"Document title: {self.doc.title}")
            return True
        except Exception as e:
            print(f"❌ Google Sheets connection failed: {e}")
            raise e

    def _get_products(self, force_refresh=False):
        now = time.time() * 1000
        if not force_refresh and self.product_cache is not None and (now - self.last_product_cache_time < CACHE_TTL_MS):
            print("📦 Using cached product data.")
            return self.product_cache

        print("🔄 Fetching fresh product data from Google Sheets...")
        sheet = self.doc.worksheet("products")
        self._record_read_request()
        rows = sheet.get_all_records()
        self.product_cache = rows
        self.last_product_cache_time = now
        print(f"🛍️ Cached {len(rows)} products.")
        return rows

    def _get_users(self, force_refresh=False):
        now = time.time() * 1000
        if not force_refresh and self.user_cache is not None and (now - self.last_user_cache_time < CACHE_TTL_MS):
            print("📦 Using cached user data.")
            return self.user_cache

        print("🔄 Fetching fresh user data from Google Sheets...")
        sheet = self.doc.worksheet("users")
        self._record_read_request()
        rows = sheet.get_all_records()
        self.user_cache = rows
        self.last_user_cache_time = now
        print(f"👥 Cached {len(rows)} users.")
        return rows

    def _get_orders(self, force_refresh=False):
        now = time.time() * 1000
        if not force_refresh and self.order_cache is not None and (now - self.last_order_cache_time < CACHE_TTL_MS):
            print("📦 Using cached order data.")
            return self.order_cache

        print("🔄 Fetching fresh order data from Google Sheets...")
        sheet = self.doc.worksheet("orders")
        self._record_read_request()
        rows = sheet.get_all_records()
        self.order_cache = rows
        self.last_order_cache_time = now
        print(f"🧾 Cached {len(rows)} orders.")
        return rows

    def create_user(self, user_data: dict):
        sheet = self.doc.worksheet("users")
        self._record_write_request()
        
        user_id = str(int(time.time() * 1000))
        new_row = {
            "id": user_id,
            **user_data,
            "createdAt": datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.000Z')
        }
        
        headers = sheet.row_values(1)
        row_values = [new_row.get(h, "") for h in headers]
        
        sheet.append_row(row_values)
        self.last_user_cache_time = 0
        return new_row

    def find_user_by_email(self, email: str):
        rows = self._get_users()
        for row in rows:
            if row.get("email") == email:
                return row
        return None

    def get_all_users(self):
        return self._get_users()

    def create_product(self, product_data: dict):
        sheet = self.doc.worksheet("products")
        self._record_write_request()
        
        product_id = str(int(time.time() * 1000))
        new_row = {
            "id": product_id,
            **product_data,
            "sales": 0,
            "createdAt": datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.000Z')
        }
        
        headers = sheet.row_values(1)
        row_values = [new_row.get(h, "") for h in headers]
        
        sheet.append_row(row_values)
        self.last_product_cache_time = 0
        return new_row

    def get_all_products(self):
        return self._get_products()

    def get_products_by_seller(self, seller_id: str):
        rows = self._get_products()
        return [row for row in rows if str(row.get("sellerId")) == str(seller_id)]

    def update_product(self, product_id: str, updates: dict):
        sheet = self.doc.worksheet("products")
        rows = self._get_products(force_refresh=True)
        
        for i, row in enumerate(rows):
            if str(row.get("id")) == str(product_id):
                updated_row = {**row, **updates}
                headers = sheet.row_values(1)
                
                # gspread indexes from 1, headers are row 1, data starts at row 2
                row_index = i + 2
                
                # Create list of updates
                cases = []
                for j, h in enumerate(headers):
                    col = j + 1
                    cases.append({
                        'range': gspread.utils.rowcol_to_a1(row_index, col),
                        'values': [[str(updated_row.get(h, ""))]]
                    })
                
                self._record_write_request()
                sheet.batch_update(cases)
                self.last_product_cache_time = 0
                return updated_row
                
        return None

    def delete_product(self, product_id: str):
        sheet = self.doc.worksheet("products")
        rows = self._get_products(force_refresh=True)
        
        for i, row in enumerate(rows):
            if str(row.get("id")) == str(product_id):
                self._record_write_request()
                sheet.delete_rows(i + 2)
                self.last_product_cache_time = 0
                return True
        return False

    def add_to_cart(self, buyer_id: str, product_id: str, quantity: int = 1):
        sheet = self.doc.worksheet("cart")
        self._record_read_request()
        rows = sheet.get_all_records()
        
        # Check if item exists
        for i, row in enumerate(rows):
            if str(row.get("buyerId")) == str(buyer_id) and str(row.get("productId")) == str(product_id):
                new_qty = int(row.get("quantity", 0)) + quantity
                # Try to find quantity column
                headers = sheet.row_values(1)
                try:
                    qty_col = headers.index("quantity") + 1
                    row_idx = i + 2
                    self._record_write_request()
                    sheet.update_cell(row_idx, qty_col, str(new_qty))
                    
                    row["quantity"] = new_qty
                    return row
                except ValueError:
                    pass
        
        # Add new item
        self._record_write_request()
        new_row = {
            "id": str(int(time.time() * 1000)),
            "buyerId": buyer_id,
            "productId": product_id,
            "quantity": quantity,
            "addedAt": time.strftime('%Y-%m-%dT%H:%M:%S.000Z')
        }
        
        headers = sheet.row_values(1)
        row_values = [new_row.get(h, "") for h in headers]
        
        sheet.append_row(row_values)
        return new_row

    def get_cart_items(self, buyer_id: str):
        sheet = self.doc.worksheet("cart")
        self._record_read_request()
        rows = sheet.get_all_records()
        return [row for row in rows if str(row.get("buyerId")) == str(buyer_id)]

    def remove_from_cart(self, cart_id: str):
        sheet = self.doc.worksheet("cart")
        self._record_read_request()
        rows = sheet.get_all_records()
        
        for i, row in enumerate(rows):
            if str(row.get("id")) == str(cart_id):
                self._record_write_request()
                sheet.delete_rows(i + 2)
                return True
        return False

    def create_order(self, order_data: dict):
        sheet = self.doc.worksheet("orders")
        self._record_write_request()
        
        order_id = str(int(time.time() * 1000))
        new_row = {
            "id": order_id,
            **order_data,
            "status": "pending",
            "createdAt": datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'
        }
        
        headers = sheet.row_values(1)
        row_values = [str(new_row.get(h, "")) for h in headers]
        
        sheet.append_row(row_values)
        self.last_order_cache_time = 0
        return new_row

    def get_orders_by_buyer(self, buyer_id: str):
        rows = self._get_orders()
        return [row for row in rows if str(row.get("buyerId")) == str(buyer_id)]

    def get_orders_by_seller(self, seller_id: str):
        rows = self._get_orders()
        return [row for row in rows if str(row.get("sellerId")) == str(seller_id)]

    def update_cart_item(self, cart_id: str, quantity: int):
        sheet = self.doc.worksheet("cart")
        self._record_read_request()
        rows = sheet.get_all_records()
        for i, row in enumerate(rows):
            if str(row.get("id")) == str(cart_id):
                if quantity <= 0:
                    self._record_write_request()
                    sheet.delete_rows(i + 2)
                    return None
                else:
                    self._record_write_request()
                    sheet.update_cell(i + 2, sheet.row_values(1).index("quantity") + 1, str(quantity))
                    row["quantity"] = quantity
                    return row
        return None

    def update_order_status(self, order_id: str, status: str):
        sheet = self.doc.worksheet("orders")
        self._record_read_request()
        rows = sheet.get_all_records()
        for i, row in enumerate(rows):
            if str(row.get("id")) == str(order_id):
                self._record_write_request()
                sheet.update_cell(i + 2, sheet.row_values(1).index("status") + 1, status)
                self.last_order_cache_time = 0
                row["status"] = status
                return row
        return None

# We instantiate a single DB to use across the app
db = GoogleSheetsDB()
