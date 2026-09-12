import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from app.analytics.rag import StoreRAGPipeline, RAGDocumentChunk
from app.analytics.copilot import RetailCopilot
from app.main import app


@pytest.fixture
def mock_store_state():
    return {
        "traffic": {
            "current_customers": 6,
            "current_staff": 2,
            "customer_to_staff_ratio": "3.0 : 1",
            "total_in": 42
        },
        "queue": {
            "queue_length": 4,
            "estimated_wait_time_min": 4.8,
            "congestion": True,
            "recommendation": "Open Counter 2 (Express Checkout) immediately"
        },
        "stock": {
            "items": [
                {"product_name": "Coca Cola", "status": "OUT_OF_STOCK", "stock": 0},
                {"product_name": "Amul Taaza", "status": "LOW_STOCK", "stock": 1}
            ],
            "stock_health_score": 80
        },
        "brain": {
            "top_prioritized_actions": [
                {
                    "priority": 1,
                    "type": "RESTOCK",
                    "target": "Coca Cola",
                    "zone": "Beverages & Juices",
                    "action": "Refill Coca Cola within 15 mins",
                    "deadline_mins": 15,
                    "revenue_at_risk": 160.0
                }
            ],
            "sku_predictions": [
                {
                    "sku_id": "SKU007",
                    "product_name": "Coca Cola",
                    "risk_level": "CRITICAL",
                    "why_reasoning": "• 0 units on shelf buffer.\n• Restock SLA 15 minutes.",
                    "stockout_eta_formatted": "DEPLETED",
                    "current_stock": 0,
                    "min_stock": 2,
                    "sales_velocity_hourly": 3.0,
                    "confidence_score": 95,
                    "revenue_at_risk": 160.0,
                    "recommended_action": "Restock Coca Cola immediately"
                }
            ]
        },
        "business_impact": {
            "revenue_protected_today": 2400.0,
            "total_estimated_lost_sales_today": 480.0,
            "staff_hours_saved_today": 3.2,
            "stockout_reduction_pct": 32.0
        },
        "price_audit": [],
        "shelf_audit": {},
        "forecasts": []
    }


def test_rag_pipeline_indexing():
    knowledge_dir = Path("data/knowledge")
    rag = StoreRAGPipeline(knowledge_dir=knowledge_dir)
    
    assert len(rag.chunks) >= 8
    assert rag.doc_count >= 8
    assert len(rag.idf) > 0
    
    docs = rag.list_knowledge_documents()
    doc_files = [d["filename"] for d in docs]
    assert "store_sop_operations.md" in doc_files
    assert "queue_and_checkout_policy.md" in doc_files
    assert "product_catalog_guide.md" in doc_files


def test_rag_retrieval_and_telemetry(mock_store_state):
    knowledge_dir = Path("data/knowledge")
    rag = StoreRAGPipeline(knowledge_dir=knowledge_dir)
    
    # Query about queue
    results = rag.retrieve("What is the checkout queue policy and SLA?", store_state=mock_store_state, top_k=3)
    assert len(results) > 0
    sources = [r["source"] for r in results]
    assert any("queue" in s.lower() for s in sources)
    
    # Query with telemetry
    context_data = rag.build_rag_context("Current inventory and out of stock", mock_store_state, top_k=3)
    assert "context_str" in context_data
    assert len(context_data["sources"]) > 0
    assert "Coca Cola" in context_data["context_str"] or "Inventory" in context_data["context_str"]


def test_copilot_offline_directives(mock_store_state):
    copilot = RetailCopilot()
    
    res = copilot.generate_response("What should I do right now?", mock_store_state, mode="offline")
    assert res["mode"] == "offline"
    assert "Directives" in res["response"] or "Coca Cola" in res["response"]
    assert "latency_ms" in res
    assert res["latency_ms"] >= 0


def test_copilot_offline_policy_query(mock_store_state):
    copilot = RetailCopilot()
    
    res = copilot.generate_response("What is the FIFO rule for shelf replenishment?", mock_store_state, mode="offline")
    assert res["mode"] == "offline"
    assert "FIFO" in res["response"] or "Store Knowledge Base" in res["response"] or "SOP" in res["response"]
    assert len(res["sources"]) > 0


def test_copilot_offline_product_catalog_query(mock_store_state):
    copilot = RetailCopilot()
    
    res = copilot.generate_response("What are the profit margins on Pringles?", mock_store_state, mode="offline")
    assert res["mode"] == "offline"
    assert "Pringles" in res["response"] or "Margin" in res["response"] or "Catalog" in res["response"]


def test_copilot_online_gemini_mocked(mock_store_state):
    copilot = RetailCopilot()
    
    mock_gemini_json = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {"text": "🎯 **Mocked Gemini Retail Analysis**: Immediate attention needed for Counter 2."}
                    ]
                }
            }
        ]
    }
    
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_resp = MagicMock()
        mock_resp.read.return_value = str(mock_gemini_json).replace("'", '"').encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp
        
        res = copilot.generate_response(
            "Give me a tactical action plan",
            mock_store_state,
            mode="online",
            api_key="mock_key",
            model="gemini-3.6-flash"
        )
        
        assert res["mode"] == "online"
        assert "Mocked Gemini Retail Analysis" in res["response"]
        assert len(res["sources"]) > 0


def test_copilot_online_fallback_on_network_error(mock_store_state):
    copilot = RetailCopilot()
    
    with patch("urllib.request.urlopen", side_effect=RuntimeError("Connection dropped")):
        res = copilot.generate_response(
            "What should I do right now?",
            mock_store_state,
            mode="online",
            api_key="bad_key",
            model="gemini-3.6-flash"
        )
        
        # Must fall back gracefully without crashing
        assert res["mode"] == "offline_fallback"
        assert "Fell back seamlessly to Offline Edge RAG Copilot" in res["response"]
        assert "Directives" in res["response"] or "Coca Cola" in res["response"]


def test_copilot_api_endpoints():
    client = TestClient(app)
    
    # 1. Config endpoint
    r_cfg = client.get("/api/copilot/config")
    assert r_cfg.status_code == 200
    cfg = r_cfg.json()
    assert "default_mode" in cfg
    assert "has_api_key" in cfg
    assert "indexed_chunks" in cfg
    assert cfg["indexed_chunks"] >= 8
    
    # 2. Knowledge endpoint
    r_kno = client.get("/api/copilot/knowledge")
    assert r_kno.status_code == 200
    kno = r_kno.json()
    assert len(kno["documents"]) >= 4
    
    # 3. Chat endpoint offline
    r_chat = client.post("/api/copilot/chat", json={"message": "What should I do right now?", "mode": "offline"})
    assert r_chat.status_code == 200
    chat_res = r_chat.json()
    assert chat_res["mode"] == "offline"
    assert "response" in chat_res
    assert len(chat_res["response"]) > 20
    
    # 4. Config update
    r_upd = client.post("/api/copilot/config", json={"default_mode": "offline", "model": "gemini-3.6-flash"})
    assert r_upd.status_code == 200
    assert r_upd.json()["success"] is True
