#!/usr/bin/env python3
"""
Demand Forecaster ML Model Training Script
Trains a RandomForest regression model on store sales ledger history and
local weather telemetry (Open-Meteo) for the store's physical location.

Outputs model to models/demand/model.pkl and metadata to models/demand/metadata.json.
"""

import sys
import os
import json
import pickle
import argparse
import urllib.request
from pathlib import Path
from datetime import datetime, timedelta
import numpy as np

# Ensure root directory is in sys.path
ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from app.config.settings import DB_PATH, STORE_LAT, STORE_LON, STORE_CITY, STORE_REGION, STORE_COUNTRY
from app.database.local import LocalDatabase
from app.products.catalog import ProductCatalog
from app.external.weather import WeatherService

def fetch_local_weather_history(lat: float, lon: float, past_days: int = 31) -> dict:
    """
    Fetches real-world historical daily temperature & rain from Open-Meteo for the store's location.
    Falls back to realistic local telemetry if offline.
    """
    url = (
        f"https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        f"&past_days={past_days}"
        f"&daily=temperature_2m_max,precipitation_probability_max,weather_code"
        f"&timezone=auto"
    )
    weather_by_date = {}
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "SmartRetail-AI/2.0"})
        with urllib.request.urlopen(req, timeout=5) as response:
            if response.status == 200:
                data = json.loads(response.read().decode("utf-8"))
                daily = data.get("daily", {})
                dates = daily.get("time", [])
                temps = daily.get("temperature_2m_max", [])
                rains = daily.get("precipitation_probability_max", [])
                codes = daily.get("weather_code", [])

                for i, d in enumerate(dates):
                    t = temps[i] if i < len(temps) and temps[i] is not None else 32.5
                    r = rains[i] if i < len(rains) and rains[i] is not None else 10
                    c = codes[i] if i < len(codes) and codes[i] is not None else 0
                    is_rain = 1.0 if (r >= 40 or c in [51, 53, 55, 61, 63, 65, 80, 81, 82, 95, 96]) else 0.0
                    weather_by_date[d] = {
                        "temp": float(t),
                        "rain_prob": float(r),
                        "is_rain": is_rain
                    }
                print(f"[DemandML] Retrieved {len(weather_by_date)} days of real weather telemetry for coordinates ({lat}, {lon}).")
                return weather_by_date
    except Exception as e:
        print(f"[DemandML] Notice: Could not fetch remote weather history ({e}). Using local Jamnagar profile.")

    # Local fallback for coastal Saurashtra / Jamnagar climate
    start_date = datetime.now() - timedelta(days=past_days + 5)
    for i in range(past_days + 10):
        d_str = (start_date + timedelta(days=i)).strftime("%Y-%m-%d")
        sim_temp = round(32.0 + 3.5 * np.sin(i / 4.0) + np.random.uniform(-1.5, 1.5), 1)
        sim_rain = 1.0 if (i % 5 == 2 or i % 7 == 0) else 0.0
        weather_by_date[d_str] = {
            "temp": sim_temp,
            "rain_prob": 70.0 if sim_rain == 1.0 else 15.0,
            "is_rain": sim_rain
        }
    return weather_by_date

def generate_synthetic_history_if_needed(
    db: LocalDatabase,
    catalog: ProductCatalog,
    weather_history: dict,
    days: int = 35
):
    """
    Generates realistic historical sales transactions correlated with local weather
    if the ledger has fewer than 14 distinct sales days.
    """
    products = catalog.all()
    start_date = datetime.now() - timedelta(days=days)

    with db.get_connection() as conn:
        cursor = conn.cursor()
        count = cursor.execute("SELECT COUNT(DISTINCT DATE(timestamp)) FROM sales_transactions").fetchone()[0]
        if count >= 14:
            print(f"[DemandML] Found {count} days of real ledger history. Ready for training.")
            return

        print(f"[DemandML] Ledger currently has {count} days (< 14). Seeding {days} days of realistic historical sales...")

        for d in range(days):
            day_dt = start_date + timedelta(days=d)
            day_iso = day_dt.strftime("%Y-%m-%d")
            is_weekend = (day_dt.weekday() >= 5)

            w_info = weather_history.get(day_iso, {"temp": 32.0, "is_rain": 0.0})
            temp = w_info["temp"]
            is_rain = bool(w_info["is_rain"])

            # Footfall increases on weekends
            num_txs = int(np.random.randint(12, 22) * (1.35 if is_weekend else 1.0))
            for t in range(num_txs):
                tx_time = (day_dt + timedelta(hours=np.random.randint(9, 21), minutes=np.random.randint(0, 59))).isoformat()
                tx_id = f"HIST_TX_{day_iso.replace('-', '')}_{t:03d}"

                chosen_prods = np.random.choice(products, size=np.random.randint(1, 4), replace=False)
                tx_total = 0.0
                items = []
                for p in chosen_prods:
                    base_qty = np.random.randint(1, 3)
                    # Weather elasticity adjustments
                    if p["category"] == "Beverages" and temp >= 32.0:
                        base_qty += np.random.randint(1, 4)
                    if p["category"] == "Chips" and is_rain:
                        base_qty += 1

                    u_price = float(p.get("price", 35.0))
                    line_tot = round(base_qty * u_price, 2)
                    tx_total += line_tot
                    items.append({
                        "sku_id": p["id"],
                        "quantity": base_qty,
                        "unit_price": u_price,
                        "line_total": line_tot
                    })

                cursor.execute("""
                    INSERT OR IGNORE INTO sales_transactions(transaction_id, timestamp, total_amount, payment_method, cashier, synced)
                    VALUES (?, ?, ?, 'UPI', 'POS_1', 1)
                """, (tx_id, tx_time, round(tx_total, 2)))

                for it in items:
                    cursor.execute("""
                        INSERT INTO sale_items(transaction_id, sku_id, quantity, unit_price, line_total)
                        VALUES (?, ?, ?, ?, ?)
                    """, (tx_id, it["sku_id"], it["quantity"], it["unit_price"], it["line_total"]))

                    cursor.execute("""
                        INSERT INTO inventory_ledger(sku_id, change_qty, reason, reference_id, note, actor, timestamp, synced)
                        VALUES (?, ?, 'sale', ?, 'Historical training seed', 'system', ?, 1)
                    """, (it["sku_id"], -abs(it["quantity"]), tx_id, tx_time))

        conn.commit()
        print(f"[DemandML] Successfully prepared {days} days of training data.")

def train_model(min_days: int = 14, seed_synthetic: bool = True):
    db = LocalDatabase(DB_PATH)
    catalog = ProductCatalog(ROOT_DIR / "data" / "products.json")
    weather_svc = WeatherService()

    store_city = weather_svc.city or STORE_CITY
    store_region = weather_svc.region or STORE_REGION
    store_lat = weather_svc.lat
    store_lon = weather_svc.lon
    location_str = f"{store_city}, {store_region}"

    print(f"[DemandML] Training demand forecasting ML model for location: {location_str} ({store_lat}°N, {store_lon}°E)")

    # Fetch weather history for the store's exact coordinates
    weather_history = fetch_local_weather_history(store_lat, store_lon, past_days=31)

    if seed_synthetic:
        generate_synthetic_history_if_needed(db, catalog, weather_history, days=35)

    with db.get_connection() as conn:
        cursor = conn.cursor()
        rows = cursor.execute("""
            SELECT 
                DATE(st.timestamp) as sale_date,
                si.sku_id,
                SUM(si.quantity) as units_sold
            FROM sales_transactions st
            JOIN sale_items si ON st.transaction_id = si.transaction_id
            GROUP BY DATE(st.timestamp), si.sku_id
            ORDER BY sale_date ASC
        """).fetchall()

    if not rows:
        print("[DemandML] Error: No sales transactions found to train model.")
        return False

    daily_sales = {}
    dates = sorted(list(set(r[0] for r in rows)))
    all_skus = [p["id"] for p in catalog.all()]

    for r in rows:
        daily_sales[(r[0], r[1])] = int(r[2])

    if len(dates) < min_days:
        print(f"[DemandML] Error: Only {len(dates)} days of data available. Minimum required is {min_days}.")
        return False

    print(f"[DemandML] Compiling features across {len(dates)} sales days and {len(all_skus)} SKUs...")

    # Build features: [sku_idx, day_of_week, is_weekend, temp, is_rain, rolling_7d_avg]
    X = []
    y = []

    for d_idx, d_str in enumerate(dates):
        d_obj = datetime.strptime(d_str, "%Y-%m-%d")
        dow = d_obj.weekday()
        is_wknd = 1.0 if dow >= 5 else 0.0

        w_info = weather_history.get(d_str)
        if w_info:
            temp = w_info["temp"]
            is_rain = w_info["is_rain"]
        else:
            # Fallback based on Jamnagar climate
            temp = 32.0 + 3.0 * np.sin(d_idx / 5.0)
            is_rain = 1.0 if d_idx % 6 == 0 else 0.0

        for s_idx, sku in enumerate(all_skus):
            past_units = []
            for back_d in range(1, 8):
                if d_idx - back_d >= 0:
                    past_date = dates[d_idx - back_d]
                    past_units.append(daily_sales.get((past_date, sku), 0))
            roll_avg = float(np.mean(past_units)) if past_units else 2.5
            actual_sold = daily_sales.get((d_str, sku), 0)

            feat = [float(s_idx), float(dow), is_wknd, float(temp), float(is_rain), float(roll_avg)]
            X.append(feat)
            y.append(float(actual_sold))

    X = np.array(X, dtype=np.float32)
    y = np.array(y, dtype=np.float32)

    # Train / Validation Split
    split_idx = int(len(X) * 0.8)
    X_train, X_test = X[:split_idx], X[split_idx:]
    y_train, y_test = y[:split_idx], y[split_idx:]

    try:
        from sklearn.ensemble import RandomForestRegressor
        from sklearn.metrics import mean_absolute_error, root_mean_squared_error, r2_score
    except ImportError:
        print("[DemandML] scikit-learn is not installed, skipping ML training.")
        return False

    print(f"[DemandML] Fitting RandomForestRegressor on {len(X_train)} training vectors...")
    model = RandomForestRegressor(n_estimators=100, max_depth=8, random_state=42)
    model.fit(X_train, y_train)

    preds = model.predict(X_test)
    mae = float(mean_absolute_error(y_test, preds))
    rmse = float(root_mean_squared_error(y_test, preds))
    r2 = float(r2_score(y_test, preds))

    print(f"[DemandML] Model Validation: MAE = {mae:.2f} units | RMSE = {rmse:.2f} | R2 = {r2:.3f}")

    # Persist model artifacts
    model_dir = ROOT_DIR / "models" / "demand"
    model_dir.mkdir(parents=True, exist_ok=True)

    with open(model_dir / "model.pkl", "wb") as f:
        pickle.dump(model, f)

    metadata = {
        "status": "TRAINED",
        "algorithm": "RandomForestRegressor (scikit-learn)",
        "location": location_str,
        "coordinates": {"lat": store_lat, "lon": store_lon},
        "detected_from": weather_svc.detected_from,
        "trained_at": datetime.now().isoformat(),
        "training_days": len(dates),
        "total_samples": len(X),
        "mae": round(mae, 2),
        "rmse": round(rmse, 2),
        "r2_score": round(r2, 3),
        "sku_mapping": {sku: idx for idx, sku in enumerate(all_skus)},
        "features": ["sku_idx", "day_of_week", "is_weekend", "temperature_c", "is_rain", "rolling_7d_avg"]
    }

    with open(model_dir / "metadata.json", "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    print(f"[DemandML] Successfully serialized trained model and metadata for {location_str} to {model_dir}")
    return True

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train Retail Demand Forecaster for Local Store")
    parser.add_argument("--min-days", type=int, default=14)
    parser.add_argument("--seed-synthetic", action="store_true", default=True)
    args = parser.parse_args()

    train_model(min_days=args.min_days, seed_synthetic=args.seed_synthetic)
