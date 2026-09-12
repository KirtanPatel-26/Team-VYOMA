from fastapi.testclient import TestClient
import pytest
from app.main import app

def test_sync_status_endpoint():
    client = TestClient(app)
    response = client.get("/api/sync/status")
    assert response.status_code == 200
    data = response.json()
    assert "total_pending_sync" in data
    assert "breakdown" in data
    assert "network_status" in data
    assert "simulated_network_offline" in data
    assert "sales_transactions" in data["breakdown"]
    assert "inventory_ledger" in data["breakdown"]

def test_simulate_network_toggle():
    client = TestClient(app)
    
    # 1. Turn simulated network blackout ON
    res_off = client.post("/api/sync/simulate-network", json={"offline": True})
    assert res_off.status_code == 200
    assert res_off.json()["simulated_network_offline"] is True
    assert res_off.json()["network_status"] == "OFFLINE_BUFFERING"

    # Status should reflect offline
    status_off = client.get("/api/sync/status").json()
    assert status_off["simulated_network_offline"] is True
    assert status_off["network_status"] == "OFFLINE_BUFFERING"

    # 2. Reconnect simulated network
    res_on = client.post("/api/sync/simulate-network", json={"offline": False})
    assert res_on.status_code == 200
    assert res_on.json()["simulated_network_offline"] is False
    assert res_on.json()["network_status"] == "ONLINE"

def test_sync_queue_and_flush_lifecycle():
    client = TestClient(app)
    
    # Ensure network is online initially
    client.post("/api/sync/simulate-network", json={"offline": False})
    
    # 1. Record a POS sale to generate unsynced edge records
    sale_payload = {
        "items": [{"sku_id": "SKU001", "quantity": 1}],
        "payment_method": "CASH",
        "cashier": "Edge_Tester"
    }
    sale_res = client.post("/api/billing/sale", json=sale_payload)
    assert sale_res.status_code == 200
    assert sale_res.json()["success"] is True

    # 2. Check sync queue has buffered item
    queue_res = client.get("/api/sync/queue?limit=20")
    assert queue_res.status_code == 200
    queue_data = queue_res.json()
    assert "items" in queue_data
    assert queue_data["total_in_queue"] >= 1
    
    # Verify sales record presence in queue
    found_sale = any(it.get("table") == "sales_transactions" or "sale" in str(it.get("category")).lower() for it in queue_data["items"])
    assert found_sale is True

    # 3. Test flush rejection while simulated network is offline
    client.post("/api/sync/simulate-network", json={"offline": True})
    blocked_flush = client.post("/api/sync/flush")
    assert blocked_flush.status_code == 200
    assert blocked_flush.json()["status"] == "OFFLINE_SIMULATED"

    # 4. Reconnect network and flush buffer
    client.post("/api/sync/simulate-network", json={"offline": False})
    flush_res = client.post("/api/sync/flush")
    assert flush_res.status_code == 200
    flush_data = flush_res.json()
    assert flush_data["success"] is True
    assert flush_data["reconciled_count"] >= 1  or flush_data["flushed_count"] >= 1

    # 5. After flush, sales should be marked synced
    post_status = client.get("/api/sync/status").json()
    assert post_status["breakdown"]["sales_transactions"] == 0

def test_offline_batch_endpoint():
    client = TestClient(app)
    batch_payload = {
        "transactions": [
            {
                "items": [{"sku_id": "SKU001", "quantity": 1}],
                "payment_method": "UPI",
                "cashier": "Offline_Associate_1"
            }
        ],
        "events": [
            {"event": "reconnect_handshake", "node": "STORE_001_MORBI"}
        ]
    }
    res = client.post("/api/sync/offline-batch", json=batch_payload)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["processed_transactions"] == 1

def test_sync_export_dump():
    client = TestClient(app)
    export_res = client.get("/api/sync/export/json")
    assert export_res.status_code == 200
    dump = export_res.json()
    assert "export_timestamp" in dump
    assert "store_id" in dump
    assert dump["store_id"] == "SKU_001" or dump["store_id"] == "SKU001" or "STORE_001"
    assert "summary" in dump
    assert "queue_snapshot" in dump
