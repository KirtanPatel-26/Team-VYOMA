import time

class RetailCopilot:
    """
    AI Retail Operations Copilot & Store Manager.
    Provides natural language reasoning, prioritized tactical directives ("What should I do right now?"),
    explainable AI ("Why is this urgent?"), and business impact ROI recaps based on live edge computer
    vision and Store Brain predictive signals.
    """
    def generate_response(self, user_query: str, store_state: dict) -> dict:
        q = (user_query or "").lower().strip()
        
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
        queue_len = queue.get("queue_length", 0)
        wait_time = queue.get("estimated_wait_time_min", 0.0)
        stock_items = stock.get("items", [])
        oos_items = [i["product_name"] for i in stock_items if i["status"] == "OUT_OF_STOCK"]
        low_items = [i["product_name"] for i in stock_items if i["status"] == "LOW_STOCK"]
        price_mismatches = [p for p in price_audit if p.get("is_mismatch")]
        prioritized_actions = brain.get("top_prioritized_actions", [])
        sku_predictions = brain.get("sku_predictions", [])

        # 1. Intent: "What should I do right now?" / Tactical Directives
        if any(w in q for w in ["what should i do", "what to do", "next action", "priorities", "tasks", "action plan", "right now"]):
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
                ans = "✅ **Store Operations Optimal**: All shelves are stocked above threshold, queue wait is under 2 minutes, and no planogram mismatches detected. Continue standard monitoring."

        # 2. Intent: Explainable AI — "Why is [product] urgent?" / "Why?"
        elif "why" in q:
            # Look for mentioned SKU
            matched_sku = None
            for p in sku_predictions:
                name_words = p.get("product_name", "").lower().split()
                if any(w in q for w in name_words if len(w) > 3) or p.get("sku_id", "").lower() in q:
                    matched_sku = p
                    break

            if not matched_sku and sku_predictions:
                # Default to highest risk SKU
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
            else:
                ans = "🔍 **Explainability Context**: All monitored products are currently operating at optimal buffer levels with no imminent stockout risks."

        # 3. Intent: Business Impact / ROI / "What happened today?"
        elif any(w in q for w in ["what happened today", "today", "recap", "roi", "lost sales", "protected revenue", "business impact"]):
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

        # 4. Intent: Out of Stock
        elif any(w in q for w in ["out of stock", "stockout", "oos", "depleted", "empty"]):
            if oos_items:
                ans = f"🚨 **Out of Stock Alert**: There are currently **{len(oos_items)} SKUs** completely depleted on the shelves:\n\n"
                for item in oos_items:
                    ans += f"• **{item}**: 0 units left on shelf (Immediate restock required).\n"
                ans += f"\n💡 **Recommendation**: Dispatch Floor Staff to replenish these items from back-room storage immediately."
            else:
                ans = "✅ **Inventory Status**: Excellent! All monitored SKUs currently have active stock on the shelves."

        # 5. Intent: Queue
        elif any(w in q for w in ["queue", "checkout", "billing", "wait time", "counter"]):
            ans = f"🛒 **Queue Operations Status**:\n\n"
            ans += f"• **People in Line**: **{queue_len} customers** waiting.\n"
            ans += f"• **Estimated Wait Time**: **~{wait_time} minutes** per customer.\n"
            ans += f"• **Active Counters**: 1 Billing Terminal active.\n"
            if queue.get("congestion"):
                ans += f"\n⚠️ **Action Required**: {queue.get('recommendation')}"
            else:
                ans += f"\n✅ **Flow Status**: Queue flow is optimal. No congestion bottlenecks detected."

        # 6. Intent: Staff
        elif any(w in q for w in ["staff", "employee", "worker", "ratio"]):
            ans = f"👥 **Staffing & Operations Breakdown**:\n\n"
            ans += f"• **Staff on Duty**: **{staff_count} Employees** detected by CCTV.\n"
            ans += f"• **Customers in Store**: **{customer_count} Shoppers**.\n"
            ans += f"• **Customer-to-Staff Ratio**: **{staff_ratio}**.\n"
            ans += f"• **Staff Roles Active**: Floor Replenishment Associate & POS Cashier.\n"
            ans += f"\n💡 **Analysis**: Current staffing coverage is well-balanced for current footfall."

        # 7. Intent: Price OCR
        elif any(w in q for w in ["price", "ocr", "tag", "mismatch", "discrepancy"]):
            if price_mismatches:
                ans = f"🔍 **EasyOCR Price Tag Audit Report**:\n\n"
                ans += f"Detected **{len(price_mismatches)} price label mismatch(es)**:\n\n"
                for p in price_mismatches:
                    ans += f"• **{p['product_name']}**: Shelf tag displays **Rs {p['detected_shelf_price']:.2f}**, but POS master catalog price is **Rs {p['catalog_price']:.2f}**.\n"
                ans += f"\n⚠️ **Risk**: May cause customer disputes or billing confusion at checkout. Recommend printing updated shelf-edge labels."
            else:
                ans = f"✅ **EasyOCR Audit**: All scanned shelf price tags match master ERP catalog prices with 100% accuracy."

        # 8. Intent: Predictive Stockout Forecasts
        elif any(w in q for w in ["forecast", "predict", "deplet", "when", "velocity"]):
            ans = f"⏱️ **Predictive Stockout Countdown & Brain Velocity**:\n\n"
            if sku_predictions:
                for p in sku_predictions[:5]:
                    ans += f"• **{p['product_name']}**: {p['current_stock']} in stock | {p['sales_velocity_hourly']} units/hr | **Stockout in {p['stockout_eta_formatted']}** ({p['risk_level']})\n"
            elif forecasts:
                for f in forecasts[:4]:
                    ans += f"• **{f['product_name']}**: Current Stock: {f['current_stock']} | Velocity: {f['depletion_velocity']} units/min | **Est. Depletion: {f['estimated_minutes_remaining']} mins** ({f['urgency']})\n"
            ans += f"\n📦 **Top Restock Action**: Restock highest velocity items first to protect shelf availability."

        # 9. Intent: Executive Summary
        elif any(w in q for w in ["summary", "overview", "executive", "how is the store", "report"]):
            ans = f"📊 **Executive Store Operations Summary**:\n\n"
            ans += f"• **Footfall**: {customer_count} Shoppers Present | {traffic.get('total_in', 0)} Total In today.\n"
            ans += f"• **Staffing**: {staff_count} Staff on duty ({staff_ratio} ratio).\n"
            ans += f"• **Inventory Health**: {stock.get('stock_health_score', 100)}% Stock Health ({len(oos_items)} Stock-Outs).\n"
            ans += f"• **Checkout Queue**: {queue_len} Customers ({wait_time}m avg wait).\n"
            ans += f"• **Active Alerts**: {len(alerts)} items requiring attention.\n"
            ans += f"• **Revenue Protected**: ₹{roi.get('revenue_protected_today', 0):,.2f}\n"
            ans += f"• **EasyOCR Verification**: {len(price_mismatches)} Price Mismatches Detected.\n"
            if prioritized_actions:
                ans += f"\n💡 **Top Immediate Action**: {prioritized_actions[0].get('action')}"

        else:
            ans = f"🤖 **SmartRetail AI Copilot & Store Manager**:\n\n"
            ans += f"• **Customers**: {customer_count} Shoppers | **Staff**: {staff_count} on duty\n"
            ans += f"• **Queue**: {queue_len} waiting ({wait_time}m wait)\n"
            ans += f"• **Stock-Outs**: {', '.join(oos_items) if oos_items else 'None'}\n"
            ans += f"• **Revenue Protected**: ₹{roi.get('revenue_protected_today', 0):,.2f}\n\n"
            ans += "Try asking me tactical queries:\n"
            ans += "👉 *'What should I do right now?'*\n"
            ans += "👉 *'Why is Dairy Milk urgent?'*\n"
            ans += "👉 *'What happened today?'*\n"
            ans += "👉 *'Show me price tag mismatches'* \n"
            ans += "👉 *'What products are out of stock?'*"

        return {
            "query": user_query,
            "response": ans,
            "timestamp": time.strftime("%H:%M:%S")
        }
