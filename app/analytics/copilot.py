import time
import json
import urllib.request
import urllib.error
from pathlib import Path
from typing import Optional, Dict, Any, List

from app.analytics.rag import StoreRAGPipeline
from app.config.settings import KNOWLEDGE_DIR, GEMINI_API_KEY, COPILOT_DEFAULT_MODE, GEMINI_MODEL, DATA_DIR


class RetailCopilot:
    """
    AI Retail Operations Copilot & Store Manager.
    Supports dual operating modes:
    1. OFFLINE MODE: Sub-50ms on-device Edge RAG synthesizer utilizing local store SOPs,
       product catalog specs, margins, inventory status, and live CCTV vision telemetry.
       100% private, zero internet required.
    2. ONLINE MODE: Cloud LLM powered by Google Gemini (gemini-3.6-flash / gemini-flash-latest)
       via API Key, performing deep natural language reasoning over the augmented RAG store context.
       Automatically falls back to offline mode if internet or API key is unavailable.
    """
    def __init__(
        self,
        knowledge_dir: Optional[Path] = None,
        api_key: Optional[str] = None,
        default_mode: Optional[str] = None,
        model: Optional[str] = None
    ):
        self.knowledge_dir = knowledge_dir or KNOWLEDGE_DIR
        self.api_key = api_key or GEMINI_API_KEY
        self.default_mode = default_mode or COPILOT_DEFAULT_MODE
        self.model = model or GEMINI_MODEL or "gemini-3.5-flash"

        
        # Initialize RAG Pipeline
        self.rag = StoreRAGPipeline(knowledge_dir=self.knowledge_dir)

        # Load Product Catalog Master Data for instant offline lookup
        self.catalog_products = []
        prod_path = (self.knowledge_dir.parent / "products.json") if self.knowledge_dir else (DATA_DIR / "products.json")
        if prod_path.exists():
            try:
                self.catalog_products = json.loads(prod_path.read_text(encoding="utf-8"))
            except Exception:
                self.catalog_products = []

    def generate_response(
        self,
        user_query: str,
        store_state: dict,
        mode: Optional[str] = None,
        api_key: Optional[str] = None,
        model: Optional[str] = None
    ) -> dict:
        """
        Routes query to either Offline Edge RAG or Online Gemini LLM based on user selection.
        """
        active_mode = (mode or self.default_mode or "offline").lower().strip()
        active_key = api_key or self.api_key
        active_model = model or self.model or "gemini-3.5-flash"
        print(f"[generate_response] active_mode={active_mode}, has_key={bool(active_key)}, active_model={active_model}", flush=True)
        
        t0 = time.time()

        if active_mode == "online":
            if not active_key:
                # Key missing -> inform and fallback to offline
                offline_res = self._generate_offline_response(user_query, store_state)
                latency = round((time.time() - t0) * 1000)
                offline_res["response"] = (
                    "⚠️ *Online Mode selected, but no Gemini API Key is configured. "
                    "Falling back to Offline Edge RAG Copilot.*\n\n" + offline_res["response"]
                )
                offline_res["mode"] = "offline_fallback"
                offline_res["latency_ms"] = latency
                return offline_res

            try:
                online_res = self._generate_online_response(user_query, store_state, active_key, active_model)
                online_res["latency_ms"] = round((time.time() - t0) * 1000)
                return online_res
            except Exception as err:
                print(f"[RetailCopilot] Online Gemini error: {err}. Falling back to offline.")
                offline_res = self._generate_offline_response(user_query, store_state)
                latency = round((time.time() - t0) * 1000)
                offline_res["response"] = (
                    f"⚠️ *Google Gemini online call encountered an issue ({str(err)[:80]}). "
                    f"Fell back seamlessly to Offline Edge RAG Copilot.*\n\n" + offline_res["response"]
                )
                offline_res["mode"] = "offline_fallback"
                offline_res["latency_ms"] = latency
                return offline_res

        # Default: Pure Offline Edge RAG
        offline_res = self._generate_offline_response(user_query, store_state)
        offline_res["latency_ms"] = round((time.time() - t0) * 1000)
        return offline_res

    def _match_catalog_product(self, query: str) -> Optional[dict]:
        """Finds if a specific monitored SKU was referenced in user query."""
        q = query.lower()
        
        # Product nickname mappings
        aliases = {
            "coke": "Coca Cola",
            "fanta": "Fanta Orange",
            "oreo": "Oreo",
            "pringles": "Pringles Original",
            "amul": "Amul Taaza",
            "taaza": "Amul Taaza",
            "milk": "Amul Taaza",
            "real": "Real Orange Juice",
            "orange juice": "Real Orange Juice",
            "dove": "Dove Soap",
            "soap": "Dove Soap",
            "lays": "Lays Classic",
            "chips": "Lays Classic",
            "dairy milk": "Dairy Milk",
            "chocolate": "Dairy Milk",
            "cadbury": "Dairy Milk",
            "colgate": "Colgate Paste",
            "toothpaste": "Colgate Paste",
            "paste": "Colgate Paste"
        }
        
        for alias in sorted(aliases.keys(), key=len, reverse=True):
            if alias in q:
                target_name = aliases[alias]
                for prod in self.catalog_products:
                    if prod.get("name", "").lower() == target_name.lower():
                        return prod

        for prod in self.catalog_products:
            p_name = prod.get("name", "").lower()
            p_id = prod.get("id", "").lower()
            if p_id in q or p_name in q:
                return prod
            # Check individual long words
            for w in p_name.split():
                if len(w) >= 4 and w in q:
                    return prod
        return None

    def _generate_offline_response(self, user_query: str, store_state: dict) -> dict:
        q = (user_query or "").lower().strip()
        words = set(q.split())
        
        traffic = store_state.get("traffic", {})
        queue = store_state.get("queue", {})
        stock = store_state.get("stock", {})
        alerts = store_state.get("alerts", [])
        price_audit = store_state.get("price_audit", [])
        shelf_audit = store_state.get("shelf_audit", {})
        forecasts = store_state.get("forecasts", [])
        brain = store_state.get("brain", {})
        roi = store_state.get("business_impact", {})

        # Extract core metrics
        customer_count = traffic.get("current_customers", 0)
        staff_count = traffic.get("current_staff", 0)
        staff_ratio = traffic.get("customer_to_staff_ratio", "N/A")
        total_in = traffic.get("total_in", 0)
        queue_len = queue.get("queue_length", 0)
        wait_time = queue.get("estimated_wait_time_min", 0.0)
        stock_items = stock.get("items", [])
        oos_items = [i["product_name"] for i in stock_items if i.get("status") == "OUT_OF_STOCK"]
        low_items = [i["product_name"] for i in stock_items if i.get("status") == "LOW_STOCK"]
        price_mismatches = [p for p in price_audit if p.get("is_mismatch")]
        prioritized_actions = brain.get("top_prioritized_actions", [])
        sku_predictions = brain.get("sku_predictions", [])

        # Retrieve relevant RAG knowledge chunks
        rag_data = self.rag.build_rag_context(user_query, store_state, top_k=3)
        sources = rag_data["sources"]
        retrieved_chunks = rag_data["chunks"]

        ans = None

        # 1. Intent: Greetings, Identity, Help, Capabilities
        greetings = {"hi", "hello", "hey", "namaste", "greetings", "good morning", "good afternoon", "good evening"}
        identity_phrases = ["who are you", "what can you do", "help", "about you", "what are you", "introduce"]
        if (words & greetings) or any(p in q for p in identity_phrases):
            ans = "👋 **Namaste! I am your SmartRetail AI Copilot & Store General Manager.**\n\n"
            ans += "I am directly connected to your on-device computer vision cameras, 10-SKU inventory tracker, checkout queue sensors, EasyOCR price auditing, and store Standard Operating Procedures (SOPs).\n\n"
            ans += "📊 **Live Store Snapshot Right Now**:\n"
            ans += f"• **Shoppers on Floor**: {customer_count} active ({total_in} total today)\n"
            ans += f"• **Staff Active**: {staff_count} on duty ({staff_ratio} ratio)\n"
            ans += f"• **Checkout Queue**: {queue_len} waiting (~{wait_time:.1f}m wait)\n"
            ans += f"• **Stock Health**: {stock.get('stock_health_score', 100)}% ({len(oos_items)} Stockouts)\n"
            ans += f"• **Revenue Protected Today**: ₹{roi.get('revenue_protected_today', 0):,.2f}\n\n"
            ans += "💡 **You can ask me questions like**:\n"
            ans += "• *'What should I do right now?'* (Prioritized tactical action plan)\n"
            ans += "• *'Tell me about Dairy Milk'* (Live stock, margin, category & shelf zone)\n"
            ans += "• *'What is our queue policy?'* (Escalation thresholds & Counter 2 dispatch rules)\n"
            ans += "• *'What are the profit margins on all products?'* (10-SKU financial breakdown)\n"
            ans += "• *'How many customers visited today?'* (Footfall & conversion rates)\n"
            ans += "• *'Show price mismatches'* (EasyOCR tag verification)"
            return {
                "query": user_query,
                "response": ans,
                "timestamp": time.strftime("%H:%M:%S"),
                "mode": "offline",
                "model": "Edge-RAG-Synthesizer",
                "sources": ["Live CCTV Vision Sensor — Store Overview", "Store Operations Standard Operating Procedures (SOP)"]
            }

        # 2. Intent: Out of Stock / Depleted Items (Checked first so 'out of stock right now' matches here)
        if any(w in q for w in ["out of stock", "stockout", "stock-out", "oos", "depleted", "empty shelf", "empty shelves"]):
            if oos_items:
                ans = f"🚨 **Out of Stock Alert**: There are currently **{len(oos_items)} SKUs** completely depleted on the shelves:\n\n"
                for item in oos_items:
                    prod_info = next((p for p in self.catalog_products if p.get("name") == item or p.get("id") == item), None)
                    zone_str = f" | Designated Zone: `{prod_info.get('target_shelf_zone')}`" if prod_info else ""
                    ans += f"• **{item}**: **0 units left on shelf**{zone_str}. SLA: Refill from back-room storage within **15 minutes**.\n"
                ans += f"\n💡 **Immediate Directive**: Dispatch Floor Staff to retrieve units from storage immediately to prevent lost sales."
            else:
                ans = "✅ **Inventory Status**: Excellent! All monitored SKUs currently have active stock on the shelves (0 stockouts detected)."
            return {
                "query": user_query,
                "response": ans,
                "timestamp": time.strftime("%H:%M:%S"),
                "mode": "offline",
                "model": "Edge-RAG-Synthesizer",
                "sources": ["Live CCTV Vision Sensor — Shelf Inventory", "store_sop_operations.md §2"]
            }

        # 3. Intent: EasyOCR Price Tag Mismatch / Audit
        if any(w in q for w in ["mismatch", "tag mismatch", "price mismatch", "price audit", "discrepancy", "easyocr", "tag error", "price tags", "price tag"]):
            if price_mismatches:
                ans = f"🔍 **EasyOCR Price Tag Audit Report**:\n\n"
                ans += f"Detected **{len(price_mismatches)} price label mismatch(es)**:\n\n"
                for p in price_mismatches:
                    p_name = p.get('product_name') or p.get('sku_name') or p.get('product_id') or p.get('sku_id', 'Product')
                    shelf_p = float(p.get('detected_shelf_price') or p.get('shelf_label_price') or 0.0)
                    pos_p = float(p.get('catalog_price') or p.get('pos_master_price') or 0.0)
                    ans += f"• **{p_name}**: Shelf tag displays **₹{shelf_p:.2f}**, but POS master catalog price is **₹{pos_p:.2f}**.\n"
                ans += f"\n⚠️ **Risk**: May cause customer disputes or billing delays at checkout. Recommend printing updated shelf-edge labels."
            else:
                ans = f"✅ **EasyOCR Audit**: All scanned shelf price tags match master ERP catalog prices with 100% accuracy."
            return {
                "query": user_query,
                "response": ans,
                "timestamp": time.strftime("%H:%M:%S"),
                "mode": "offline",
                "model": "Edge-RAG-Synthesizer",
                "sources": ["EasyOCR Vision Sensor — Shelf Price Tags", "store_sop_operations.md §4"]
            }

        # 4. Intent: Specific Product Inquiry & Explainability (e.g. "Tell me about Dairy Milk", "Why is Dairy Milk urgent?")
        matched_catalog_prod = self._match_catalog_product(user_query)
        if matched_catalog_prod and not any(w in q for w in ["what should i do", "what happened today", "all products", "catalog", "margins", "increase sales"]):
            prod_name = matched_catalog_prod.get("name")
            prod_id = matched_catalog_prod.get("id")
            cat = matched_catalog_prod.get("category")
            price = matched_catalog_prod.get("price", 0.0)
            cost = matched_catalog_prod.get("cost_price", 0.0)
            margin_pct = round(((price - cost) / price) * 100.0, 1) if price > 0 else 0.0
            zone = matched_catalog_prod.get("target_shelf_zone", "Shelves")
            min_buf = matched_catalog_prod.get("minimum_stock", 2)

            # Live stock telemetry
            live_item = next((i for i in stock_items if i.get("product_id") == prod_id or i.get("product_name") == prod_name or prod_name.lower() in i.get("product_name", "").lower()), None)
            curr_stock = live_item.get("stock", 0) if live_item else 0
            status = live_item.get("status", "OUT_OF_STOCK" if curr_stock == 0 else "IN_STOCK") if live_item else "IN_STOCK"
            status_badge = "🚨 OUT OF STOCK" if status == "OUT_OF_STOCK" else "⚠️ LOW STOCK" if status == "LOW_STOCK" else "✅ OPTIMAL"

            # Store Brain Velocity
            pred = next((p for p in sku_predictions if p.get("sku_id") == prod_id or p.get("product_name") == prod_name), None)

            ans = f"📦 **Product Intelligence — {prod_name}** (`{prod_id}`)\n\n"
            ans += f"• **Category**: {cat} | **Designated Zone**: `{zone}`\n"
            ans += f"• **Pricing & Profitability**: POS Price: **₹{price:.2f}** | Cost: ₹{cost:.2f} | **Gross Margin: {margin_pct}%**\n"
            ans += f"• **Live Shelf Status**: **{curr_stock} units on shelf** ({status_badge})\n"
            ans += f"• **Minimum Buffer Threshold**: {min_buf} units\n"
            
            # If user asked why it is urgent or explainability
            if any(k in q for k in ["why", "urgent", "reason", "stockout", "risk"]):
                if pred and pred.get("why_reasoning"):
                    ans += f"• 🧠 **Urgency Diagnosis**: {pred.get('why_reasoning')}\n"
                elif status == "OUT_OF_STOCK":
                    ans += f"• 🧠 **Urgency Diagnosis**: The shelf is completely empty (0 units). Customers seeking {prod_name} face immediate purchase failure, risking basket abandonment. Immediate restock from storage is required.\n"
                elif status == "LOW_STOCK":
                    ans += f"• 🧠 **Urgency Diagnosis**: Shelf count is below the {min_buf}-unit safety threshold with active floor traffic.\n"
                else:
                    ans += f"• 🧠 **Urgency Diagnosis**: Currently stable with {curr_stock} units on display. No immediate operational risk.\n"
            
            if pred:
                ans += f"• **Sales Velocity**: {pred.get('sales_velocity_hourly', 1.0)} units/hr\n"
                ans += f"• **Stockout ETA**: **{pred.get('stockout_eta_formatted', 'Stable')}** (Confidence: {pred.get('confidence_score', 90)}%)\n"
                if pred.get('revenue_at_risk', 0) > 0:
                    ans += f"• **Revenue at Risk**: **₹{pred.get('revenue_at_risk'):.2f}**\n"
                ans += f"• **Recommended Action**: {pred.get('recommended_action', 'Monitor shelf buffer.')}\n"
            elif status == "OUT_OF_STOCK":
                ans += "• **Immediate Action**: Refill from back-room storage within **15 minutes** (Critical SLA).\n"
            else:
                ans += "• **Status**: Stock level is healthy. No immediate restock required.\n"

            return {
                "query": user_query,
                "response": ans,
                "timestamp": time.strftime("%H:%M:%S"),
                "mode": "offline",
                "model": "Edge-RAG-Synthesizer",
                "sources": [f"product_catalog_guide.md — {prod_id} {prod_name}", "Live CCTV Vision Sensor — Shelf Inventory"]
            }

        # 5. Intent: Explainable AI — "Why is [product] urgent?" / "Why?" (if not caught above)
        if "why" in q and ("urgent" in q or "risk" in q or "priority" in q):
            matched_sku = None
            for p in sku_predictions:
                name_words = p.get("product_name", "").lower().split()
                if any(w in q for w in name_words if len(w) > 3) or p.get("sku_id", "").lower() in q:
                    matched_sku = p
                    break

            if not matched_sku and sku_predictions:
                critical_skus = [s for s in sku_predictions if s.get("risk_level") in ["CRITICAL", "HIGH"]]
                if critical_skus:
                    matched_sku = critical_skus[0]

            if matched_sku:
                ans = f"🧠 **Explainable AI Reasoning — {matched_sku.get('product_name')}** ({matched_sku.get('risk_level')} Risk):\n\n"
                ans += f"{matched_sku.get('why_reasoning')}\n\n"
                ans += f"• **Current Stock**: {matched_sku.get('current_stock')} units (Min buffer: {matched_sku.get('min_stock')})\n"
                ans += f"• **Sales Velocity**: {matched_sku.get('sales_velocity_hourly')} units/hour\n"
                ans += f"• **Stockout ETA**: {matched_sku.get('stockout_eta_formatted')} ({matched_sku.get('confidence_score')}% model confidence)\n"
                ans += f"• **Revenue Protected if Restocked**: ₹{matched_sku.get('revenue_at_risk', 0):.2f}\n"
                ans += f"\n👉 **Prescriptive Directive**: {matched_sku.get('recommended_action')}"
                return {
                    "query": user_query,
                    "response": ans,
                    "timestamp": time.strftime("%H:%M:%S"),
                    "mode": "offline",
                    "model": "Edge-RAG-Synthesizer",
                    "sources": ["Store Brain Predictive Engine", "store_sop_operations.md §2"]
                }

        # 6. Intent: Tactical Directives ("What should I do right now?", "Action plan", "Next tasks")
        if any(w in q for w in ["what should i do", "what to do", "next action", "priorities", "tasks", "action plan", "immediate directive"]):
            if prioritized_actions:
                ans = "🎯 **AI Store Manager — Top Immediate Directives**:\n\n"
                for idx, act in enumerate(prioritized_actions[:4], start=1):
                    badge = "🚨 URGENT" if act.get("priority") == 1 else "⚠️ HIGH" if act.get("priority") == 2 else "ℹ️ ROUTINE"
                    rev = f" | ₹{act['revenue_at_risk']:.0f} at risk" if act.get("revenue_at_risk") else ""
                    ans += f"**{idx}. [{act.get('type')}] {act.get('action')}**\n"
                    ans += f"   • Target: `{act.get('target')}` in `{act.get('zone')}`\n"
                    ans += f"   • Status: {badge} | Complete within **{act.get('deadline_mins')} mins**{rev}\n\n"
                ans += "💡 *Directives are ranked autonomously by revenue impact and customer walkout probability.*"
            else:
                actions = []
                if oos_items:
                    actions.append(f"**🚨 [RESTOCK SLA]** Restock {len(oos_items)} depleted SKU(s) from back-room storage: **{', '.join(oos_items[:3])}**. (Critical 15-minute replenishment SLA).")
                if queue_len >= 4 or wait_time > 3.0 or queue.get("congestion"):
                    actions.append(f"**🛒 [LINE-BUSTING]** Dispatch floor associate to open **Counter 2 (Express Checkout)** within 90 seconds to eliminate customer wait times ({wait_time:.1f}m current wait).")
                if price_mismatches:
                    actions.append(f"**🔍 [PRICE AUDIT]** Replace **{len(price_mismatches)} mismatched shelf-edge price labels** scanned by EasyOCR to prevent checkout billing disputes.")
                if low_items:
                    actions.append(f"**⚠️ [BUFFER REPLENISH]** Prepare back-room replenishment for low-stock items: **{', '.join(low_items[:3])}**.")

                if actions:
                    ans = "🎯 **AI Store Manager — Prioritized Operational Directives**:\n\n"
                    for idx, a in enumerate(actions, start=1):
                        ans += f"{idx}. {a}\n\n"
                    ans += "💡 *Generated from live CCTV cameras, queue sensors, and stock telemetry.*"
                else:
                    ans = "✅ **Store Operations Optimal**: All shelves are stocked above threshold, checkout wait is under 2 minutes, and no price mismatches detected. Continue standard monitoring."
            return {
                "query": user_query,
                "response": ans,
                "timestamp": time.strftime("%H:%M:%S"),
                "mode": "offline",
                "model": "Edge-RAG-Synthesizer",
                "sources": ["Live Store Brain Directive Engine", "Live CCTV Vision Sensor", "store_sop_operations.md"]
            }

        # 7. Intent: Commercial Strategy & Sales Growth ("How do I increase sales?", "How to boost revenue?")
        if any(w in q for w in ["increase sales", "how do i increase sales", "how to increase sales", "boost revenue", "growth", "grow sales", "improve profit", "sell more", "commercial strategy", "upsell", "cross-sell"]):
            ans = "🚀 **Commercial Revenue Growth & Margin Optimization Playbook**:\n\n"
            ans += "1. **Protect High-Margin SKU Facings**:\n"
            ans += "   • Prioritize prime eye-level display for top-margin items: **Oreo (40.0%)**, **Lays Classic (40.0%)**, **Coca Cola (37.5%)**, and **Fanta (37.1%)**.\n"
            ans += "   • Maintain 100% on-shelf availability for these 4 SKUs to capture high-margin impulse purchases.\n\n"
            ans += "2. **Eliminate Queue Abandonment Revenue Leaks**:\n"
            ans += "   • Average retail basket in our store is **₹350**.\n"
            ans += f"   • When line reaches ≥ 4 people, customers walk out. Current queue wait is **~{wait_time:.1f} mins**.\n"
            ans += "   • Dispatching Counter 2 within 90 seconds recovers an estimated ₹12,000+ monthly in retained revenue.\n\n"
            ans += "3. **Cross-Merchandising Synergy**:\n"
            ans += "   • Place savory snacks (Lays & Pringles) directly adjacent to cold beverage coolers (Coke & Fanta) to increase multi-item basket conversion by ~18%.\n\n"
            ans += "4. **Ensure 100% Price Tag Accuracy**:\n"
            ans += "   • Discrepancies between shelf tags and POS scanners cause friction and basket drop-offs. Run daily morning EasyOCR sweeps.\n\n"
            ans += f"📊 *Live Store Metric: Protected ₹{roi.get('revenue_protected_today', 0):,.2f} today via automated stockout and queue interventions.*"
            return {
                "query": user_query,
                "response": ans,
                "timestamp": time.strftime("%H:%M:%S"),
                "mode": "offline",
                "model": "Edge-RAG-Synthesizer",
                "sources": ["loss_prevention_roi.md §4", "product_catalog_guide.md", "queue_and_checkout_policy.md"]
            }

        # 8. Intent: Loss Prevention, Shoplifting & Security Protocol
        if any(w in q for w in ["shoplifting", "theft", "steal", "pilferage", "security", "loss prevention", "shrinkage", "suspicious"]):
            ans = "🛡️ **Retail Loss Prevention & Security SOP**:\n\n"
            ans += "1. **CCTV Vision Dwell Alerts**:\n"
            ans += "   • The camera system monitors high-shrink bays (Chocolates & Personal Care).\n"
            ans += "   • Prolonged dwell (>4 minutes) without shelf interaction triggers an associate notification.\n\n"
            ans += "2. **Non-Confrontational Deterrence**:\n"
            ans += "   • Associates must provide immediate friendly customer service: *'Namaste! May I help you find something today?'*\n"
            ans += "   • Proactive staff presence deters over 90% of opportunistic pilferage without confrontation.\n\n"
            ans += "3. **Concealment & Restraint Rules**:\n"
            ans += "   • Floor staff must **NEVER** physically touch or restrain shoppers.\n"
            ans += "   • Discretely notify the Duty Manager and review POS checkout logs at the exit counter.\n\n"
            ans += "4. **High-Value Item Headcounts**:\n"
            ans += "   • High-unit cost items (Pringles ₹110, Colgate ₹55, Dairy Milk ₹50) undergo continuous hourly AI headcounts to detect bulk shelf sweeps.\n\n"
            ans += "🔍 *Source: `loss_prevention_roi.md §3` (Store Loss Prevention & Security Guidelines)*"
            return {
                "query": user_query,
                "response": ans,
                "timestamp": time.strftime("%H:%M:%S"),
                "mode": "offline",
                "model": "Edge-RAG-Synthesizer",
                "sources": ["loss_prevention_roi.md — 3. Shoplifting, Theft Prevention & Security Protocol"]
            }

        # 9. Intent: Product Margins / Full Catalog Breakdown
        if any(w in q for w in ["margin", "margins", "profit margin", "all products", "catalog", "product list", "skus", "cost price", "catalog pricing"]):
            ans = "📊 **Monitored 10-SKU Profit Margins & Catalog Pricing Guide**:\n\n"
            ans += "| SKU ID | Product Name | Category | Retail POS | Cost Price | Gross Margin |\n"
            ans += "| :--- | :--- | :--- | :--- | :--- | :--- |\n"
            for p in self.catalog_products:
                pr = p.get("price", 0.0)
                cp = p.get("cost_price", 0.0)
                mg = round(((pr - cp) / pr) * 100.0, 1) if pr > 0 else 0.0
                ans += f"| `{p.get('id')}` | **{p.get('name')}** | {p.get('category')} | ₹{pr:.2f} | ₹{cp:.2f} | **{mg}%** |\n"
            ans += "\n💡 *Top margin products: Oreo (40.0%), Lays (40.0%), Fanta (37.1%), Coca Cola (37.5%). Prioritize shelf availability on these high-margin impulse items.*"
            return {
                "query": user_query,
                "response": ans,
                "timestamp": time.strftime("%H:%M:%S"),
                "mode": "offline",
                "model": "Edge-RAG-Synthesizer",
                "sources": ["product_catalog_guide.md — SKU Master Specifications & Margins"]
            }

        # 10. Intent: Queue / Checkout
        if any(w in q for w in ["queue", "checkout", "billing", "wait time", "counter", "line"]):
            ans = f"🛒 **Queue Operations Status & Policy**:\n\n"
            ans += f"• **People in Line**: **{queue_len} customers** waiting.\n"
            ans += f"• **Estimated Wait Time**: **~{wait_time:.1f} minutes** per customer.\n"
            ans += f"• **Active Counters**: 1 Billing Terminal active.\n"
            if queue.get("congestion") or queue_len >= 4 or wait_time > 3.0:
                ans += f"\n⚠️ **Action Required**: {queue.get('recommendation', 'Open Counter 2 immediately.')}\n"
                ans += f"📜 *SOP Rule*: Dispatch floor associate to open **Counter 2 (Express Checkout)** within **90 seconds** when queue ≥ 4 or wait time > 3.5 mins."
            else:
                ans += f"\n✅ **Flow Status**: Queue flow is optimal. No congestion bottlenecks detected."
            return {
                "query": user_query,
                "response": ans,
                "timestamp": time.strftime("%H:%M:%S"),
                "mode": "offline",
                "model": "Edge-RAG-Synthesizer",
                "sources": ["Live Queue Sensor", "queue_and_checkout_policy.md §1-§2"]
            }

        # 11. Intent: Staffing / Who is on duty / Ratio
        if any(w in q for w in ["staff", "employee", "worker", "associate", "cashier", "coverage", "who is on duty", "who is working", "duty", "team"]):
            ans = f"👥 **Staffing & Operations Breakdown**:\n\n"
            ans += f"• **Staff on Duty**: **{staff_count} Employees** detected by CCTV.\n"
            ans += f"• **Customers in Store**: **{customer_count} Shoppers**.\n"
            ans += f"• **Customer-to-Staff Ratio**: **{staff_ratio}** (Target SLA: 1 staff per 4 to 6 shoppers).\n"
            ans += f"• **Active Roles**: Floor Replenishment Associate & POS Cashier.\n"
            if staff_count == 0 and customer_count > 0:
                ans += f"\n⚠️ **Alert**: No staff detected on sales floor with {customer_count} active customers. Ensure floor coverage."
            else:
                ans += f"\n💡 **Analysis**: Current staffing coverage is well-balanced for current footfall."
            return {
                "query": user_query,
                "response": ans,
                "timestamp": time.strftime("%H:%M:%S"),
                "mode": "offline",
                "model": "Edge-RAG-Synthesizer",
                "sources": ["Live CCTV Vision Sensor — Staffing", "queue_and_checkout_policy.md §3"]
            }

        # 12. Intent: Live Footfall / Customers / Shoppers
        if any(w in q for w in ["customer", "shopper", "footfall", "people", "crowd", "traffic", "visitor", "visitors", "how many people", "how many customers", "in store"]):
            ans = "👥 **Live Shopper Footfall & Store Occupancy**:\n\n"
            ans += f"• **Shoppers on Floor Right Now**: **{customer_count} Customers** actively browsing.\n"
            ans += f"• **Total Footfall Today**: **{total_in} Total Shoppers** entered the store.\n"
            ans += f"• **Staff on Duty**: **{staff_count} Employees** detected by CCTV.\n"
            ans += f"• **Customer-to-Staff Ratio**: **{staff_ratio}** (Target SLA: 1 staff per 4 to 6 shoppers).\n"
            ans += f"• **Queue Occupancy**: {queue_len} shoppers in checkout line (~{wait_time:.1f}m wait time).\n"
            if customer_count > 8:
                ans += "\n⚠️ **Staffing Advisory**: Elevated footfall detected. Direct floor associates to assist customers and ensure shelf facings remain tidy."
            else:
                ans += "\n✅ **Flow Status**: Store occupancy is comfortable and well-balanced."
            return {
                "query": user_query,
                "response": ans,
                "timestamp": time.strftime("%H:%M:%S"),
                "mode": "offline",
                "model": "Edge-RAG-Synthesizer",
                "sources": ["Live Store Footfall Sensor — Shopper Footfall & Staffing", "queue_and_checkout_policy.md §3"]
            }

        # 13. Intent: Business Impact / ROI / "What happened today?"
        if any(w in q for w in ["what happened today", "financial impact", "roi", "lost sales", "protected revenue", "business impact", "daily recap", "today summary", "today's recap"]):
            lost_stockout = roi.get("lost_sales_stockout_today", 0.0)
            lost_queue = roi.get("lost_sales_queue_today", 0.0)
            total_lost = roi.get("total_estimated_lost_sales_today", 0.0)
            prot_rev = roi.get("revenue_protected_today", 0.0)
            hrs_saved = roi.get("staff_hours_saved_today", 0.0)
            stockout_red = roi.get("stockout_reduction_pct", 0.0)

            ans = f"📈 **Daily Executive Financial & Operational Impact**:\n\n"
            ans += f"• **Revenue Protected Today**: **₹{prot_rev:,.2f}** (via real-time restock & queue dispatches)\n"
            ans += f"• **Estimated Lost Sales Today**: **₹{total_lost:,.2f}**\n"
            ans += f"   - Depleted Shelf Stockouts: ₹{lost_stockout:,.2f}\n"
            ans += f"   - Long Checkout Queue Abandonment: ₹{lost_queue:,.2f}\n"
            ans += f"• **Store Efficiency**: **{hrs_saved} staff hours saved** via automated vision audits\n"
            ans += f"• **Stockout Reduction Rate**: **+{stockout_red}%** vs unmonitored store baseline\n"
            ans += f"• **Footfall Served**: {traffic.get('total_in', 0)} total visitors today ({customer_count} currently active)"
            return {
                "query": user_query,
                "response": ans,
                "timestamp": time.strftime("%H:%M:%S"),
                "mode": "offline",
                "model": "Edge-RAG-Synthesizer",
                "sources": ["Edge ROI Engine — Financial Metrics", "loss_prevention_roi.md §1"]
            }

        # 14. Intent: Executive Summary / Store Overview
        if any(w in q for w in ["summary", "overview", "executive", "how is the store", "report", "store status", "overall status"]):
            ans = f"📊 **Executive Store Operations Summary**:\n\n"
            ans += f"• **Footfall**: {customer_count} Shoppers Present | {traffic.get('total_in', 0)} Total In today.\n"
            ans += f"• **Staffing**: {staff_count} Staff on duty ({staff_ratio} ratio).\n"
            ans += f"• **Inventory Health**: {stock.get('stock_health_score', 100)}% Stock Health ({len(oos_items)} Stock-Outs).\n"
            ans += f"• **Checkout Queue**: {queue_len} Customers ({wait_time:.1f}m avg wait).\n"
            ans += f"• **Active Alerts**: {len(alerts)} items requiring attention.\n"
            ans += f"• **Revenue Protected**: ₹{roi.get('revenue_protected_today', 0):,.2f}\n"
            ans += f"• **EasyOCR Verification**: {len(price_mismatches)} Price Mismatches Detected.\n"
            if prioritized_actions:
                ans += f"\n💡 **Top Immediate Action**: {prioritized_actions[0].get('action')}"
            elif oos_items:
                ans += f"\n💡 **Top Immediate Action**: Replenish depleted items: {', '.join(oos_items[:2])}."
            return {
                "query": user_query,
                "response": ans,
                "timestamp": time.strftime("%H:%M:%S"),
                "mode": "offline",
                "model": "Edge-RAG-Synthesizer",
                "sources": ["Live CCTV Vision Sensor", "Store Brain Predictive Engine", "EasyOCR Price Tags"]
            }

        # 15. Intent: Store Hours / Routines / Opening & Closing
        if any(w in q for w in ["hour", "hours", "opening", "closing", "routine", "schedule", "shift", "when open", "when close"]):
            ans = "⏰ **Store Operating Hours & Daily Routines SOP**:\n\n"
            ans += "• **Morning Store Opening**: **08:00 AM**\n"
            ans += "   - *Opening Audit*: Initial computer vision shelf audit must be completed by **08:30 AM** before doors unlock.\n"
            ans += "• **Mid-Day Shift Handover**: **03:00 PM**\n"
            ans += "   - Cash drawer balance check and replenishment priority review.\n"
            ans += "• **Evening Store Closing**: **10:00 PM**\n"
            ans += "   - *Closing Audit*: Physical shelf count verification and inventory reconciliation occur between **10:00 PM and 10:45 PM**.\n\n"
            ans += "🔍 *Source: `store_sop_operations.md` §1 (Store Daily Operating Hours & Routines)*"
            return {
                "query": user_query,
                "response": ans,
                "timestamp": time.strftime("%H:%M:%S"),
                "mode": "offline",
                "model": "Edge-RAG-Synthesizer",
                "sources": ["store_sop_operations.md — 1. Store Daily Operating Hours & Routines"]
            }

        # 16. Intent: Predictive Stockout Forecasts
        if any(w in q for w in ["forecast", "predict", "deplet", "when stockout", "velocity"]):
            ans = f"⏱️ **Predictive Stockout Countdown & Brain Velocity**:\n\n"
            if sku_predictions:
                for p in sku_predictions[:5]:
                    ans += f"• **{p['product_name']}**: {p['current_stock']} in stock | {p['sales_velocity_hourly']} units/hr | **Stockout in {p['stockout_eta_formatted']}** ({p['risk_level']})\n"
            elif forecasts:
                for f in forecasts[:4]:
                    ans += f"• **{f['product_name']}**: Current Stock: {f['current_stock']} | Velocity: {f['depletion_velocity']} units/min | **Est. Depletion: {f['estimated_minutes_remaining']} mins** ({f['urgency']})\n"
            ans += f"\n📦 **Top Restock Action**: Restock highest velocity items first to protect shelf availability."
            return {
                "query": user_query,
                "response": ans,
                "timestamp": time.strftime("%H:%M:%S"),
                "mode": "offline",
                "model": "Edge-RAG-Synthesizer",
                "sources": ["Store Brain Predictive Engine", "store_sop_operations.md §2"]
            }

        # 17. RAG Synthesis for Store SOPs, Policy & Knowledge Inquiries (threshold lowered to 0.2)
        knowledge_chunks = [c for c in retrieved_chunks if c.get("chunk_type") == "knowledge" and c.get("score", 0) >= 0.2]
        if knowledge_chunks:
            top_match = knowledge_chunks[0]
            ans = f"📖 **Store Knowledge Base — {top_match['title']}** ({top_match['section']}):\n\n"
            ans += f"{top_match['content']}\n\n"
            if len(knowledge_chunks) > 1:
                second_match = knowledge_chunks[1]
                ans += f"📌 **Related Guidance — {second_match['section']}**:\n"
                snippet = "\n".join(second_match['content'].splitlines()[:4])
                ans += f"{snippet}\n\n"
            ans += f"🔍 *Source: `{top_match['source']}` (Retrieved via Offline RAG)*"
            return {
                "query": user_query,
                "response": ans,
                "timestamp": time.strftime("%H:%M:%S"),
                "mode": "offline",
                "model": "Edge-RAG-Synthesizer",
                "sources": sources
            }

        # 18. Polite Scope-Grounded Fallback
        ans = f"🤖 **SmartRetail AI Copilot (Offline Edge RAG)**:\n\n"
        ans += f"I am your on-device store assistant specializing in real-time camera vision telemetry, inventory monitoring, queue management, and retail SOPs.\n"
        ans += f"I don't have external data on *'{user_query}'*, but here is your current store status:\n\n"
        ans += f"• **Live Store Status**: {customer_count} shoppers, {staff_count} staff, {queue_len} in queue.\n"
        ans += f"• **Shelf Inventory**: {stock.get('stock_health_score', 100)}% health score.\n"
        if oos_items:
            ans += f"• **Out of Stock**: {', '.join(oos_items)}\n"
        ans += f"• **Revenue Protected Today**: ₹{roi.get('revenue_protected_today', 0):,.2f}\n\n"
        ans += "💡 **Recommended Retail Questions**:\n"
        ans += "👉 *'What should I do right now?'*\n"
        ans += "👉 *'Tell me about Dairy Milk'* (or any monitored product)\n"
        ans += "👉 *'What products are out of stock right now?'*\n"
        ans += "👉 *'What is our checkout queue policy?'*\n"
        ans += "👉 *'What are the profit margins on all products?'*\n"
        ans += "👉 *'How do I increase sales?'*"

        return {
            "query": user_query,
            "response": ans,
            "timestamp": time.strftime("%H:%M:%S"),
            "mode": "offline",
            "model": "Edge-RAG-Synthesizer",
            "sources": sources
        }

    def _generate_online_response(self, user_query: str, store_state: dict, api_key: str, model: str) -> dict:
        """
        Executes an augmented query against Google Gemini LLM via REST API.
        """
        rag_data = self.rag.build_rag_context(user_query, store_state, top_k=4)
        rag_context = rag_data["context_str"]
        sources = rag_data["sources"]

        system_instruction = (
            "You are the SmartRetail AI Copilot & General Manager for an intelligent edge retail store located in Morbi, Gujarat, India.\n"
            "You are directly connected to live CCTV computer vision edge cameras, an inventory ledger, queue tracking sensors, "
            "EasyOCR shelf price audits, and official store Standard Operating Procedures (SOPs).\n\n"
            "Personality & Guidelines:\n"
            "- Speak professionally, concisely, helpfully, and actionably like an expert retail store manager.\n"
            "- When greeted (e.g. 'hi', 'hello', 'who are you'), warmly introduce yourself, summarize the live store state in 3-4 bullet points, and offer tactical options.\n"
            "- When asked about any product (e.g. 'Dairy Milk', 'Fanta', 'Pringles', 'Oreo', 'Coke'), provide its price in ₹, cost, margin, target zone, and current live shelf stock.\n"
            "- When asked strategic questions ('How to increase sales?', 'Loss prevention'), provide clear numbered operational recommendations.\n"
            "- Always prioritize revenue protection, avoiding checkout walkouts, and maintaining shelf availability.\n"
            "- Strictly ground factual store numbers in the provided Live Sensors Telemetry and Store SOP Knowledge.\n"
            "- Format responses cleanly with GitHub Markdown: bold key numbers, bullet points, and alert badges (🚨, ⚠️, ✅, 🎯, 💡).\n"
            "- Always use ₹ (Indian Rupee) for all pricing and monetary figures."
        )

        user_prompt = (
            f"=== LIVE STORE SENSORS & TELEMETRY ===\n"
            f"{rag_context}\n\n"
            f"=== STORE MANAGER QUERY ===\n"
            f"{user_query}\n\n"
            f"Provide a thorough, tactical, and contextually grounded response:"
        )

        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": user_prompt}
                    ]
                }
            ],
            "systemInstruction": {
                "parts": [
                    {"text": system_instruction}
                ]
            },
            "generationConfig": {
                "temperature": 0.2,
                "topP": 0.8,
                "maxOutputTokens": 1500
            }
        }

        # Multi-model resilient generation (tries requested model first, then high-quota fallbacks)
        models_to_try = [model]
        for fallback_m in ["gemini-3.5-flash", "gemini-3.7-flash", "gemini-flash-latest", "gemini-2.5-flash"]:
            if fallback_m not in models_to_try:
                models_to_try.append(fallback_m)

        last_error = None
        for candidate_model in models_to_try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{candidate_model}:generateContent?key={api_key}"
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            try:
                with urllib.request.urlopen(req, timeout=14) as response:
                    resp_data = json.loads(response.read().decode("utf-8"))

                candidates = resp_data.get("candidates", [])
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    reply_text = "".join(p.get("text", "") for p in parts if "text" in p).strip()
                    if reply_text:
                        return {
                            "query": user_query,
                            "response": reply_text,
                            "timestamp": time.strftime("%H:%M:%S"),
                            "mode": "online",
                            "model": candidate_model,
                            "sources": sources
                        }
            except Exception as e:
                last_error = e
                print(f"[RetailCopilot] Online candidate {candidate_model} failed: {e}. Trying next...")
                continue

        raise last_error or RuntimeError("All online Gemini candidate models failed.")

    def test_gemini_connection(self, api_key: Optional[str] = None, model: Optional[str] = None) -> dict:
        """
        Validates Gemini API connectivity and measures response latency with automatic model fallback.
        """
        key = api_key or self.api_key
        mod = model or self.model or "gemini-3.5-flash"

        if not key:
            return {"success": False, "error": "No API key configured."}

        models_to_try = [mod]
        for fallback_m in ["gemini-3.5-flash", "gemini-3.7-flash", "gemini-flash-latest"]:
            if fallback_m not in models_to_try:
                models_to_try.append(fallback_m)

        last_err_msg = ""
        for candidate_mod in models_to_try:
            t0 = time.time()
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{candidate_mod}:generateContent?key={key}"
            payload = {
                "contents": [{"parts": [{"text": "Reply with ONLINE_OK"}]}],
                "generationConfig": {
                    "maxOutputTokens": 100,
                    "temperature": 0.0,
                    "thinkingConfig": {"thinkingBudget": 0}
                }
            }
            try:
                req = urllib.request.Request(
                    url,
                    data=json.dumps(payload).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST"
                )
                with urllib.request.urlopen(req, timeout=8) as response:
                    resp_data = json.loads(response.read().decode("utf-8"))
                
                latency_ms = round((time.time() - t0) * 1000)
                candidates = resp_data.get("candidates", [])
                text = ""
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    text = "".join(p.get("text", "") for p in parts if "text" in p).strip()
                
                if not text:
                    text = "ONLINE_OK"
                
                return {
                    "success": True,
                    "latency_ms": latency_ms,
                    "model": candidate_mod,
                    "reply": text,
                    "message": f"Successfully connected to Google Gemini ({candidate_mod}) in {latency_ms}ms"
                }
            except urllib.error.HTTPError as e:
                err_body = e.read().decode("utf-8", errors="ignore")
                try:
                    err_json = json.loads(err_body)
                    last_err_msg = err_json.get("error", {}).get("message", str(e))
                except Exception:
                    last_err_msg = f"HTTP {e.code}: {e.reason}"
                continue
            except Exception as e:
                last_err_msg = str(e)
                continue

        return {"success": False, "error": last_err_msg or "Failed to connect to Google Gemini models."}

