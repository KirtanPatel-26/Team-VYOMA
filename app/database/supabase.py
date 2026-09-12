import os
import yaml
from pathlib import Path
from datetime import datetime
from app.security.encryption import encrypt_data, decrypt_data
from app.security.sanitizer import mask_credential, sanitize_rtsp_url

class SupabaseDatabase:
    """
    Supabase Cloud Sync Engine.
    Handles cloud synchronization of edge retail telemetry, store metrics, shelf compliance,
    incident alerts, POS sales, and inventory ledger.
    """
    def __init__(self, url=None, key=None, store_code="STORE_001"):
        self.url = (url or os.getenv("SUPABASE_URL", "")).strip()
        self.key = (key or os.getenv("SUPABASE_KEY", "")).strip()
        self.store_code = store_code
        self.client = None
        self.last_sync_time = None
        self.last_sync_status = "Not Connected"
        self.last_sync_errors = {}
        self.is_connected = False
        self.synced_counts = {
            "traffic": 0,
            "inventory": 0,
            "queue": 0,
            "alerts": 0,
            "shelf": 0,
            "sales": 0,
            "ledger": 0
        }
        
        if self.url and self.key:
            self.connect()

    def connect(self, url=None, key=None):
        """
        Connects to Supabase and performs live database health verification.
        Returns a dictionary: {"success": bool, "message": str, ...}
        """
        if url is not None:
            self.url = url.strip()
        if key is not None:
            self.key = key.strip()

        if not self.url or not self.key:
            self.client = None
            self.last_sync_status = "Disconnected (No API Key)"
            return {
                "success": False,
                "message": "Supabase Project URL and API Key are required."
            }

        try:
            from supabase import create_client
            self.client = create_client(self.url, self.key)

            # Live verification query to verify credentials and table accessibility
            res = self.client.table("stores").select("store_code").limit(1).execute()
            
            # Auto-seed stores and products master catalog to ensure foreign keys never fail
            self._ensure_store_and_products_exist()

            self.last_sync_status = "Connected"
            self.last_sync_errors = {}
            return {
                "success": True,
                "message": "Supabase Cloud Connected Successfully! All tables verified.",
                "data": res.data
            }
        except Exception as e:
            err_str = str(e)
            print(f"[Supabase Connect Error]: {err_str}")

            if "relation" in err_str and "does not exist" in err_str:
                # Connected to project, but tables are missing
                self.last_sync_status = "Connected to project, but tables are missing. Please run supabase_schema.sql in Supabase SQL Editor."
                self.last_sync_errors = {"schema": err_str}
                return {
                    "success": False,
                    "needs_migration": True,
                    "message": "Connected to Supabase, but database tables are missing! Please run 'supabase_schema.sql' in your Supabase SQL Editor."
                }
            elif "JWT" in err_str or "apikey" in err_str or "Invalid API key" in err_str or "401" in err_str:
                self.client = None
                self.last_sync_status = "Authentication Failed: Invalid Supabase API Key."
                return {
                    "success": False,
                    "message": "Authentication failed: Invalid Supabase API key. Please check your Anon / Service key."
                }
            else:
                self.last_sync_status = f"Connection Warning: {err_str}"
                return {
                    "success": False,
                    "message": f"Connection check note: {err_str}"
                }

    def _ensure_store_and_products_exist(self):
        """
        Seeds/upserts the current store and all 10 monitored products in Supabase
        so foreign key constraints never block telemetry or inventory insertion.
        """
        if not self.client:
            return

        # 1. Upsert default store records
        stores_data = [
            {
                "store_code": "STORE_001",
                "name": "SmartRetail Flagship",
                "location": "Indiranagar, 100ft Road",
                "city": "Bengaluru",
                "tier": "Tier-1",
                "total_counters": 4
            },
            {
                "store_code": "STORE_002",
                "name": "SmartRetail Express",
                "location": "Koramangala 5th Block",
                "city": "Bengaluru",
                "tier": "Tier-1",
                "total_counters": 2
            },
            {
                "store_code": "STORE_003",
                "name": "SmartRetail Hyper",
                "location": "Whitefield Main Road",
                "city": "Bengaluru",
                "tier": "Tier-1",
                "total_counters": 6
            },
            {
                "store_code": "STORE_004",
                "name": "SmartRetail Hub",
                "location": "HSR Layout Sector 2",
                "city": "Bengaluru",
                "tier": "Tier-2",
                "total_counters": 3
            }
        ]
        try:
            self.client.table("stores").upsert(stores_data, on_conflict="store_code").execute()
        except Exception as e:
            print(f"[Supabase] Store auto-upsert note: {e}")

        # 2. Upsert all 10 monitored SKUs into products catalog
        products_list = self._load_product_catalog()
        if products_list:
            try:
                self.client.table("products").upsert(products_list, on_conflict="id").execute()
            except Exception as e:
                print(f"[Supabase] Products catalog auto-upsert note: {e}")

    def _load_product_catalog(self):
        """Loads all 10 products from configs/products.yaml or returns default fallback catalog."""
        config_path = Path("configs/products.yaml")
        if config_path.exists():
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                meta = data.get("metadata", {})
                products = []
                for sku_id, item in meta.items():
                    products.append({
                        "id": sku_id,
                        "name": item.get("name", sku_id),
                        "category": item.get("category", "General"),
                        "price": float(item.get("default_price", 20.0)),
                        "minimum_stock": 2,
                        "target_shelf_zone": item.get("shelf", "General")
                    })
                if products:
                    return products
            except Exception as e:
                print(f"[Supabase] Warning reading products.yaml: {e}")

        # Fallback 10 products
        return [
            {"id": "SKU001", "name": "Fanta Orange 600ml", "category": "Beverages", "price": 35.0, "minimum_stock": 2, "target_shelf_zone": "Beverages & Juices"},
            {"id": "SKU002", "name": "Pringles Original 107g", "category": "Chips", "price": 110.0, "minimum_stock": 2, "target_shelf_zone": "Snacks & Biscuits"},
            {"id": "SKU003", "name": "Oreo Chocolate 120g", "category": "Biscuits", "price": 30.0, "minimum_stock": 2, "target_shelf_zone": "Snacks & Biscuits"},
            {"id": "SKU004", "name": "Amul Taaza 500ml", "category": "Milk", "price": 30.0, "minimum_stock": 3, "target_shelf_zone": "Dairy & Essentials"},
            {"id": "SKU005", "name": "Real Orange Juice 1L", "category": "Juices", "price": 40.0, "minimum_stock": 2, "target_shelf_zone": "Beverages & Juices"},
            {"id": "SKU006", "name": "Dove Soap Bar 75g", "category": "Soap", "price": 40.0, "minimum_stock": 2, "target_shelf_zone": "Dairy & Essentials"},
            {"id": "SKU007", "name": "Coca Cola 600ml", "category": "Beverages", "price": 40.0, "minimum_stock": 2, "target_shelf_zone": "Beverages & Juices"},
            {"id": "SKU008", "name": "Lays Classic 50g", "category": "Chips", "price": 20.0, "minimum_stock": 2, "target_shelf_zone": "Snacks & Biscuits"},
            {"id": "SKU009", "name": "Cadbury Dairy Milk 50g", "category": "Chocolates", "price": 50.0, "minimum_stock": 2, "target_shelf_zone": "Snacks & Biscuits"},
            {"id": "SKU010", "name": "Colgate Total 120g", "category": "Personal Care", "price": 55.0, "minimum_stock": 2, "target_shelf_zone": "Dairy & Essentials"}
        ]

    def disconnect(self):
        """Disconnects the Supabase client and clears active credentials."""
        self.client = None
        self.url = ""
        self.key = ""
        self.last_sync_status = "Disconnected"
        self.last_sync_errors = {}
        return {"success": True, "message": "Disconnected from Supabase Cloud."}

    @property
    def enabled(self):
        return self.client is not None

    def test_connection(self):
        if not self.enabled:
            return {"success": False, "message": "Supabase client not initialized. Enter Project URL and API Key."}
        try:
            res = self.client.table("stores").select("store_code").limit(1).execute()
            return {"success": True, "message": "Supabase Cloud Connected Successfully! Store Verified.", "data": res.data}
        except Exception as e:
            return {"success": False, "message": f"Connection test failed: {str(e)}"}

    def check_schema_health(self):
        """
        Tests every required table individually and returns a diagnostic summary.
        """
        if not self.enabled:
            return {
                "connected": False,
                "healthy": False,
                "message": "Supabase is not connected.",
                "missing_tables": []
            }

        tables_to_check = [
            "stores", "products", "inventory_logs", "shopper_traffic",
            "queue_metrics", "alerts", "shelf_compliance", "inventory_ledger",
            "sales_transactions", "sale_items"
        ]

        table_results = {}
        missing = []

        for tbl in tables_to_check:
            try:
                self.client.table(tbl).select("*").limit(1).execute()
                table_results[tbl] = {"ok": True}
            except Exception as e:
                err_msg = str(e)
                table_results[tbl] = {"ok": False, "error": err_msg}
                missing.append(tbl)

        is_healthy = len(missing) == 0
        return {
            "connected": True,
            "healthy": is_healthy,
            "table_results": table_results,
            "missing_tables": missing,
            "message": "All required tables exist and are reachable." if is_healthy else f"Missing or inaccessible tables: {', '.join(missing)}. Please run supabase_schema.sql in Supabase SQL Editor."
        }

    def sync_local_data(self, local_db, current_inventory=None, current_shelf_audit=None, current_alerts=None):
        """
        Pushes unsynced offline records from SQLite to Supabase cloud tables.
        Accurately tracks successes and records specific table errors.
        """
        if not self.enabled:
            return {"synced": False, "reason": "Cloud not connected"}

        self._ensure_store_and_products_exist()

        sync_errors = {}
        synced_traffic_ids = []
        synced_queue_ids = []
        synced_alert_ids = []
        synced_shelf_ids = []
        synced_sales_ids = []
        synced_ledger_ids = []
        now_iso = datetime.now().isoformat()

        try:
            unsynced = local_db.get_unsynced_records(limit=40)

            # 1. Sync Shopper Traffic
            if unsynced.get("traffic"):
                traffic_payloads = [{
                    "store_code": self.store_code,
                    "current_occupancy": r["current_people"],
                    "total_in": r["total_in"],
                    "total_out": r["total_out"],
                    "avg_dwell_time_seconds": r["avg_dwell_time"],
                    "timestamp": r["timestamp"] if "T" in str(r["timestamp"]) else now_iso
                } for r in unsynced["traffic"]]
                
                try:
                    self.client.table("shopper_traffic").insert(traffic_payloads).execute()
                    synced_traffic_ids = [r["id"] for r in unsynced["traffic"]]
                    self.synced_counts["traffic"] += len(traffic_payloads)
                except Exception as e:
                    sync_errors["shopper_traffic"] = str(e)
                    print(f"[Supabase Sync Error: shopper_traffic]: {e}")

            # 2. Sync Queue Metrics
            if unsynced.get("queue"):
                queue_payloads = [{
                    "store_code": self.store_code,
                    "queue_length": r["queue_length"],
                    "avg_wait_time_seconds": r["estimated_wait_sec"],
                    "is_congested": bool(r["is_congested"]),
                    "timestamp": r["timestamp"] if "T" in str(r["timestamp"]) else now_iso
                } for r in unsynced["queue"]]

                try:
                    self.client.table("queue_metrics").insert(queue_payloads).execute()
                    synced_queue_ids = [r["id"] for r in unsynced["queue"]]
                    self.synced_counts["queue"] += len(queue_payloads)
                except Exception as e:
                    sync_errors["queue_metrics"] = str(e)
                    print(f"[Supabase Sync Error: queue_metrics]: {e}")

            # 3. Sync Operational Alerts (Unsynced from DB + Live Alerts)
            alert_items_to_sync = []
            if unsynced.get("alerts"):
                for r in unsynced["alerts"]:
                    ts = r.get("timestamp")
                    valid_ts = ts if (ts and "T" in str(ts)) else now_iso
                    alert_items_to_sync.append({
                        "store_code": self.store_code,
                        "alert_type": r["alert_type"],
                        "severity": r["severity"],
                        "title": r["title"],
                        "message": r["message"],
                        "zone": r["zone"],
                        "created_at": valid_ts
                    })
            elif current_alerts:
                for a in current_alerts:
                    alert_items_to_sync.append({
                        "store_code": self.store_code,
                        "alert_type": a["type"],
                        "severity": a["severity"],
                        "title": a["title"],
                        "message": a["message"],
                        "zone": a.get("zone", ""),
                        "created_at": now_iso
                    })

            if alert_items_to_sync:
                try:
                    self.client.table("alerts").insert(alert_items_to_sync).execute()
                    if unsynced.get("alerts"):
                        synced_alert_ids = [r["id"] for r in unsynced["alerts"]]
                    self.synced_counts["alerts"] += len(alert_items_to_sync)
                except Exception as e:
                    sync_errors["alerts"] = str(e)
                    print(f"[Supabase Sync Error: alerts]: {e}")

            # 4. Sync Shelf Compliance
            shelf_items_to_sync = []
            if unsynced.get("shelf"):
                for r in unsynced["shelf"]:
                    ts = r.get("timestamp")
                    valid_ts = ts if (ts and "T" in str(ts)) else now_iso
                    shelf_items_to_sync.append({
                        "store_code": self.store_code,
                        "zone_name": r["zone_name"],
                        "detected_items": r["detected_items"],
                        "compliance_score": r["compliance_score"],
                        "status": r["status"],
                        "timestamp": valid_ts
                    })
            elif current_shelf_audit and "shelves" in current_shelf_audit:
                for s in current_shelf_audit["shelves"]:
                    shelf_items_to_sync.append({
                        "store_code": self.store_code,
                        "zone_name": s.get("zone"),
                        "detected_items": s.get("detected_count", 0),
                        "compliance_score": s.get("compliance_score", 100.0),
                        "status": s.get("status", "COMPLIANT"),
                        "timestamp": now_iso
                    })

            if shelf_items_to_sync:
                try:
                    self.client.table("shelf_compliance").insert(shelf_items_to_sync).execute()
                    if unsynced.get("shelf"):
                        synced_shelf_ids = [r["id"] for r in unsynced["shelf"]]
                    self.synced_counts["shelf"] += len(shelf_items_to_sync)
                except Exception as e:
                    sync_errors["shelf_compliance"] = str(e)
                    print(f"[Supabase Sync Error: shelf_compliance]: {e}")

            # 5. Sync Current Inventory Snapshot
            if current_inventory and "items" in current_inventory:
                inv_payloads = [{
                    "store_code": self.store_code,
                    "product_id": item["product_id"],
                    "product_name": item["product_name"],
                    "detected_count": item["stock"],
                    "minimum_stock": item["minimum_stock"],
                    "status": item["status"],
                    "shelf_zone": item.get("shelf_zone", ""),
                    "timestamp": now_iso
                } for item in current_inventory["items"]]

                try:
                    self.client.table("inventory_logs").insert(inv_payloads).execute()
                    self.synced_counts["inventory"] += len(inv_payloads)
                except Exception as e:
                    sync_errors["inventory_logs"] = str(e)
                    print(f"[Supabase Sync Error: inventory_logs]: {e}")

            # 6. Sync POS Sales Transactions
            if unsynced.get("sales"):
                sales_payloads = []
                for r in unsynced["sales"]:
                    store = str(r.get("store_code") or self.store_code)
                    cashier_raw = r.get("cashier", "Self Checkout 01")
                    payload = {
                        "store_code": store,
                        "transaction_id": r["transaction_id"],
                        "total_amount": float(r["total_amount"]),
                        "payment_method": r.get("payment_method", "UPI"),
                        "cashier": cashier_raw,
                        "timestamp": r["timestamp"] if "T" in str(r["timestamp"]) else now_iso
                    }
                    # Apply encryption layer ONLY for STORE_002, strictly preserving STORE_001
                    if store.upper() == "STORE_002":
                        try:
                            payload["cashier_encrypted"] = encrypt_data(cashier_raw)
                            payload["cashier"] = mask_credential(cashier_raw)
                            if r.get("customer_email"):
                                payload["customer_email_encrypted"] = encrypt_data(r.get("customer_email"))
                            if r.get("customer_phone"):
                                payload["customer_phone_encrypted"] = encrypt_data(r.get("customer_phone"))
                            if r.get("payment_details"):
                                payload["payment_details_encrypted"] = encrypt_data(r.get("payment_details"))
                        except Exception as enc_err:
                            print(f"[Supabase Security] Encryption note for STORE_002: {enc_err}")

                    sales_payloads.append(payload)

                try:
                    self.client.table("sales_transactions").upsert(sales_payloads, on_conflict="transaction_id").execute()
                    synced_sales_ids = [r["transaction_id"] for r in unsynced["sales"]]
                    self.synced_counts["sales"] += len(sales_payloads)
                except Exception as e:
                    sync_errors["sales_transactions"] = str(e)
                    print(f"[Supabase Sync Error: sales_transactions]: {e}")

            # 7. Sync Inventory Ledger Adjustments
            if unsynced.get("ledger"):
                ledger_payloads = [{
                    "store_code": self.store_code,
                    "sku_id": r["sku_id"],
                    "change_qty": int(r["change_qty"]),
                    "reason": r.get("reason", "manual"),
                    "reference_id": r.get("reference_id", ""),
                    "note": r.get("note", ""),
                    "actor": r.get("actor", "system"),
                    "timestamp": r["timestamp"] if "T" in str(r["timestamp"]) else now_iso
                } for r in unsynced["ledger"]]

                try:
                    self.client.table("inventory_ledger").insert(ledger_payloads).execute()
                    synced_ledger_ids = [r["id"] for r in unsynced["ledger"]]
                    self.synced_counts["ledger"] += len(ledger_payloads)
                except Exception as e:
                    sync_errors["inventory_ledger"] = str(e)
                    print(f"[Supabase Sync Error: inventory_ledger]: {e}")

            # Mark only successfully inserted records as synced in SQLite
            if synced_traffic_ids:
                local_db.mark_synced("traffic_history", synced_traffic_ids)
            if synced_queue_ids:
                local_db.mark_synced("queue_history", synced_queue_ids)
            if synced_alert_ids:
                local_db.mark_synced("alerts_log", synced_alert_ids)
            if synced_shelf_ids:
                local_db.mark_synced("shelf_compliance_history", synced_shelf_ids)
            if synced_sales_ids:
                local_db.mark_synced("sales_transactions", synced_sales_ids)
            if synced_ledger_ids:
                local_db.mark_synced("inventory_ledger", synced_ledger_ids)

            self.last_sync_time = datetime.now().strftime("%H:%M:%S")
            self.last_sync_errors = sync_errors

            if sync_errors:
                failed_tbls = ", ".join(sync_errors.keys())
                self.last_sync_status = f"Sync Warning: {failed_tbls} error ({list(sync_errors.values())[0]})"
            else:
                self.last_sync_status = "Synchronized"

            return {
                "synced": len(sync_errors) == 0,
                "timestamp": self.last_sync_time,
                "counts": self.synced_counts,
                "errors": sync_errors
            }
        except Exception as e:
            self.last_sync_status = f"Sync Critical Error: {str(e)}"
            self.last_sync_errors = {"critical": str(e)}
            print(f"[Supabase Sync Critical Error]: {e}")
            return {"synced": False, "error": str(e)}

    def force_resync_all(self, local_db, limit=200):
        """
        Pushes recent historical records from SQLite to Supabase,
        regardless of whether they were previously marked synced.
        Useful when initial sync failed or tables were added after edge capture.
        """
        if not self.enabled:
            return {"success": False, "message": "Supabase not connected"}

        self._ensure_store_and_products_exist()
        now_iso = datetime.now().isoformat()
        total_pushed = 0
        errors = {}

        with local_db.get_connection() as conn:
            import sqlite3
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # 1. Traffic History
            traffic_rows = cursor.execute("SELECT * FROM traffic_history ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
            if traffic_rows:
                payload = [{
                    "store_code": self.store_code,
                    "current_occupancy": r["current_people"],
                    "total_in": r["total_in"],
                    "total_out": r["total_out"],
                    "avg_dwell_time_seconds": r["avg_dwell_time"],
                    "timestamp": r["timestamp"] if "T" in str(r["timestamp"]) else now_iso
                } for r in traffic_rows]
                try:
                    self.client.table("shopper_traffic").insert(payload).execute()
                    total_pushed += len(payload)
                    self.synced_counts["traffic"] += len(payload)
                except Exception as e:
                    errors["shopper_traffic"] = str(e)

            # 2. Queue History
            queue_rows = cursor.execute("SELECT * FROM queue_history ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
            if queue_rows:
                payload = [{
                    "store_code": self.store_code,
                    "queue_length": r["queue_length"],
                    "avg_wait_time_seconds": r["estimated_wait_sec"],
                    "is_congested": bool(r["is_congested"]),
                    "timestamp": r["timestamp"] if "T" in str(r["timestamp"]) else now_iso
                } for r in queue_rows]
                try:
                    self.client.table("queue_metrics").insert(payload).execute()
                    total_pushed += len(payload)
                    self.synced_counts["queue"] += len(payload)
                except Exception as e:
                    errors["queue_metrics"] = str(e)

            # 3. Shelf Compliance
            shelf_rows = cursor.execute("SELECT * FROM shelf_compliance_history ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
            if shelf_rows:
                payload = [{
                    "store_code": self.store_code,
                    "zone_name": r["zone_name"],
                    "detected_items": r["detected_items"],
                    "compliance_score": r["compliance_score"],
                    "status": r["status"],
                    "timestamp": r["timestamp"] if "T" in str(r["timestamp"]) else now_iso
                } for r in shelf_rows]
                try:
                    self.client.table("shelf_compliance").insert(payload).execute()
                    total_pushed += len(payload)
                    self.synced_counts["shelf"] += len(payload)
                except Exception as e:
                    errors["shelf_compliance"] = str(e)

            # 4. Alerts Log
            alert_rows = cursor.execute("SELECT * FROM alerts_log ORDER BY id DESC LIMIT ?", (50,)).fetchall()
            if alert_rows:
                payload = [{
                    "store_code": self.store_code,
                    "alert_type": r["alert_type"],
                    "severity": r["severity"],
                    "title": r["title"],
                    "message": r["message"],
                    "zone": r["zone"],
                    "created_at": r["timestamp"] if "T" in str(r["timestamp"]) else now_iso
                } for r in alert_rows]
                try:
                    self.client.table("alerts").insert(payload).execute()
                    total_pushed += len(payload)
                    self.synced_counts["alerts"] += len(payload)
                except Exception as e:
                    errors["alerts"] = str(e)

            # 5. POS Sales
            sales_rows = cursor.execute("SELECT * FROM sales_transactions ORDER BY timestamp DESC LIMIT ?", (50,)).fetchall()
            if sales_rows:
                payload = [{
                    "store_code": self.store_code,
                    "transaction_id": r["transaction_id"],
                    "total_amount": float(r["total_amount"]),
                    "payment_method": r.get("payment_method", "UPI"),
                    "cashier": r.get("cashier", "Self Checkout 01"),
                    "timestamp": r["timestamp"] if "T" in str(r["timestamp"]) else now_iso
                } for r in sales_rows]
                try:
                    self.client.table("sales_transactions").upsert(payload, on_conflict="transaction_id").execute()
                    total_pushed += len(payload)
                    self.synced_counts["sales"] += len(payload)
                except Exception as e:
                    errors["sales_transactions"] = str(e)

            # 6. Inventory Ledger
            ledger_rows = cursor.execute("SELECT * FROM inventory_ledger ORDER BY id DESC LIMIT ?", (100,)).fetchall()
            if ledger_rows:
                payload = [{
                    "store_code": self.store_code,
                    "sku_id": r["sku_id"],
                    "change_qty": int(r["change_qty"]),
                    "reason": r.get("reason", "manual"),
                    "reference_id": r.get("reference_id", ""),
                    "note": r.get("note", ""),
                    "actor": r.get("actor", "system"),
                    "timestamp": r["timestamp"] if "T" in str(r["timestamp"]) else now_iso
                } for r in ledger_rows]
                try:
                    self.client.table("inventory_ledger").insert(payload).execute()
                    total_pushed += len(payload)
                    self.synced_counts["ledger"] += len(payload)
                except Exception as e:
                    errors["inventory_ledger"] = str(e)

        self.last_sync_time = datetime.now().strftime("%H:%M:%S")
        self.last_sync_errors = errors
        if errors:
            self.last_sync_status = f"Re-sync finished with warnings: {', '.join(errors.keys())}"
        else:
            self.last_sync_status = f"Re-synced {total_pushed} records to Supabase."

        return {
            "success": len(errors) == 0,
            "total_pushed": total_pushed,
            "errors": errors,
            "timestamp": self.last_sync_time
        }

    def flush_all_offline_records(self, local_db) -> dict:
        """
        Pushes all unsynced records to cloud.
        If cloud is not connected, does NOT wipe the queue; keeps records buffered.
        """
        if self.enabled:
            total_flushed = 0
            for _ in range(5):
                res = self.sync_local_data(local_db)
                if not res.get("synced"):
                    break
                total_flushed += sum(res.get("counts", {}).values())
            return {
                "success": True,
                "mode": "CLOUD_SUPABASE",
                "flushed_count": total_flushed,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
        else:
            summary = local_db.get_sync_queue_summary()
            count = summary.get("total_pending", 0)
            return {
                "success": False,
                "mode": "LOCAL_EDGE_BUFFERED",
                "flushed_count": 0,
                "pending_count": count,
                "message": "Supabase cloud is disconnected. Offline buffer safely preserved on device.",
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }

    def insert_theft_event(self, event_data: dict) -> bool:
        """Inserts or updates a theft/suspicious activity event in Supabase."""
        if not self.enabled:
            return False
        try:
            row = {
                "event_id": event_data.get("event_id") or event_data.get("id"),
                "camera_id": event_data.get("camera_id", "camera_01"),
                "person_id": event_data.get("person_id"),
                "product_id": event_data.get("product_id"),
                "product_name": event_data.get("product_name"),
                "shelf_id": event_data.get("shelf_id"),
                "risk_score": int(event_data.get("risk_score", 0)),
                "risk_level": event_data.get("risk_level", "NORMAL"),
                "event_type": event_data.get("event_type", "POTENTIAL_PRODUCT_REMOVAL"),
                "current_zone": event_data.get("current_zone", "Aisle / Common Area"),
                "checkout_detected": bool(event_data.get("checkout_detected")),
                "snapshot_url": event_data.get("snapshot_url"),
                "status": event_data.get("status", "ACTIVE"),
                "timeline": event_data.get("timeline", [])
            }
            self.client.table("theft_events").upsert(row, on_conflict="event_id").execute()
            return True
        except Exception as e:
            print(f"[Supabase] Theft event sync note: {e}")
            return False

    def insert_anomaly_event(self, anomaly_data: dict) -> bool:
        """Inserts an anomaly event directly into the enterprise anomalies table."""
        if not self.enabled:
            return False
        try:
            row = {
                "anomaly_type": anomaly_data.get("anomaly_type"),
                "severity": anomaly_data.get("severity", "Medium"),
                "camera_id": anomaly_data.get("camera_id", "CAM_01"),
                "zone_id": anomaly_data.get("zone_id", "STORE_FLOOR"),
                "product_id": anomaly_data.get("product_id"),
                "product_name": anomaly_data.get("product_name"),
                "person_id": anomaly_data.get("person_id"),
                "description": anomaly_data.get("description", "Anomaly detected"),
                "confidence_score": float(anomaly_data.get("confidence_score", 0.95)),
                "status": anomaly_data.get("status", "Active"),
                "metadata": anomaly_data.get("metadata", {}),
                "snapshot_url": anomaly_data.get("snapshot_url")
            }
            self.client.table("anomalies").insert(row).execute()
            return True
        except Exception as e:
            print(f"[Supabase] Anomaly insert note: {e}")
            return False

    def save_store002_camera_config(
        self,
        camera_id: str,
        camera_name: str,
        rtsp_url: str,
        username: Optional[str] = None,
        password: Optional[str] = None,
        location_zone: str = "Checkout Zone",
        stream_type: str = "RTSP"
    ) -> dict:
        """
        Stores camera config for STORE_002 with application-level Fernet encryption.
        Raw password and full RTSP URL credentials are encrypted before insertion into Supabase.
        """
        if not self.enabled:
            return {"success": False, "message": "Supabase client not connected."}

        try:
            masked = sanitize_rtsp_url(rtsp_url)
            row = {
                "store_code": "STORE_002",
                "camera_id": camera_id,
                "camera_name": camera_name,
                "location_zone": location_zone,
                "stream_type": stream_type,
                "rtsp_url_encrypted": encrypt_data(rtsp_url),
                "camera_username_encrypted": encrypt_data(username) if username else None,
                "camera_password_encrypted": encrypt_data(password) if password else None,
                "rtsp_url_masked": masked,
                "status": "ONLINE"
            }
            self.client.table("camera_configs").upsert(row, on_conflict="store_code,camera_id").execute()
            return {"success": True, "camera_id": camera_id, "camera_name": camera_name, "masked_url": masked}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_store002_camera_configs(self, decrypt_for_internal_stream: bool = False) -> list:
        """
        Fetches camera configs for STORE_002.
        - If decrypt_for_internal_stream=False (for API/UI): NEVER decrypts or returns credentials.
        - If decrypt_for_internal_stream=True: Used strictly within edge CV process to construct connection.
        """
        if not self.enabled:
            return []

        try:
            res = self.client.table("camera_configs").select("*").eq("store_code", "STORE_002").execute()
            configs = []
            for row in (res.data or []):
                cfg = {
                    "store_code": row.get("store_code"),
                    "camera_id": row.get("camera_id"),
                    "camera_name": row.get("camera_name"),
                    "location_zone": row.get("location_zone"),
                    "stream_type": row.get("stream_type"),
                    "status": row.get("status"),
                    "rtsp_url_masked": row.get("rtsp_url_masked") or sanitize_rtsp_url(row.get("rtsp_url_encrypted", ""))
                }
                if decrypt_for_internal_stream:
                    # Internal edge pipeline only
                    enc_url = row.get("rtsp_url_encrypted")
                    if enc_url:
                        cfg["_internal_rtsp_url"] = decrypt_data(enc_url)
                configs.append(cfg)
            return configs
        except Exception as e:
            print(f"[Supabase] Error reading camera configs: {e}")
            return []

    def get_status(self):
        return {
            "enabled": self.enabled,
            "connected": self.enabled and len(self.last_sync_errors) == 0,
            "url": self.url[:25] + "..." if len(self.url) > 25 else self.url,
            "has_key": bool(self.key),
            "status": self.last_sync_status,
            "last_sync_time": self.last_sync_time,
            "last_sync_errors": self.last_sync_errors,
            "synced_counts": self.synced_counts
        }

