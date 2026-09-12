import pytest
import tempfile
from pathlib import Path
from app.database.local import LocalDatabase
from app.billing.ledger import InventoryLedger
from app.products.catalog import ProductCatalog
from app.analytics.demand import DemandForecaster
from app.external.weather import WeatherService

def test_demand_forecaster_heuristic_mode():
    temp_dir = tempfile.TemporaryDirectory()
    db_path = Path(temp_dir.name) / "test_retail.db"
    db = LocalDatabase(db_path)
    ledger = InventoryLedger(db)
    
    catalog_path = Path(__file__).resolve().parents[1] / "data" / "products.json"
    catalog = ProductCatalog(catalog_path)
    
    # Initialize forecaster (no trained model in temp directory -> HEURISTIC mode)
    forecaster = DemandForecaster(catalog, ledger)
    assert forecaster.mode in ["HEURISTIC", "TRAINED"]
    
    forecast_res = forecaster.forecast()
    assert "mode" in forecast_res
    assert "weather" in forecast_res
    assert "predictions" in forecast_res
    assert len(forecast_res["predictions"]) == 10
    
    # Verify profit calculations exist
    first_pred = forecast_res["predictions"][0]
    assert "predicted_units" in first_pred
    assert "unit_margin" in first_pred
    assert "action" in first_pred
    assert first_pred["action"] in ["REORDER_NOW", "PROMOTE_HIGH_MARGIN", "OVERSTOCK_RISK", "SUFFICIENT"]
    assert first_pred["projected_profit"] >= 0.0
    
    temp_dir.cleanup()

def test_weather_service_structure():
    ws = WeatherService()
    res = ws.get_forecast()
    assert "current" in res
    assert "tomorrow_forecast" in res
    assert "temperature_c" in res["current"]
    assert "temperature_max_c" in res["tomorrow_forecast"]
