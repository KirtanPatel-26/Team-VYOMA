import re
import math
from pathlib import Path
from typing import List, Dict, Any, Optional
from collections import Counter


class RAGDocumentChunk:
    def __init__(self, chunk_id: str, title: str, section: str, content: str, source: str, chunk_type: str = "knowledge"):
        self.chunk_id = chunk_id
        self.title = title
        self.section = section
        self.content = content.strip()
        self.source = source
        self.chunk_type = chunk_type  # "knowledge", "telemetry", "catalog"
        self.tokens = self._tokenize(self.content + " " + title + " " + section)
        self.term_freqs = Counter(self.tokens)

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        cleaned = re.sub(r"[^\w\s-]", " ", text.lower())
        words = cleaned.split()
        stopwords = {
            "a", "an", "the", "in", "on", "at", "to", "for", "of", "and", "or", "is", "are",
            "was", "were", "be", "this", "that", "it", "with", "as", "by", "from", "how", "what",
            "which", "who", "when", "where", "can", "you", "tell", "me", "about", "give", "our"
        }
        tokens = [w for w in words if len(w) > 1 and w not in stopwords]
        synonyms = {
            "theft": ["shrinkage", "shoplifting", "loss", "prevention"],
            "shoplifting": ["theft", "shrinkage", "loss", "security", "concealment"],
            "steal": ["theft", "shrinkage", "shoplifting"],
            "pilferage": ["theft", "shrinkage", "loss"],
            "sales": ["revenue", "margin", "margins", "profit"],
            "grow": ["sales", "revenue", "strategy"],
            "profit": ["margin", "margins", "pricing"],
            "duty": ["staff", "associate", "employee", "cashier"],
            "working": ["staff", "duty", "associate"],
            "tag": ["price", "label", "ocr", "mismatch"],
            "counter": ["queue", "checkout", "billing", "terminal"]
        }
        expanded = list(tokens)
        for t in tokens:
            if t in synonyms:
                expanded.extend(synonyms[t])
        return list(set(expanded))


from app.config.settings import KNOWLEDGE_DIR, DATA_DIR


class StoreRAGPipeline:
    """
    On-Device Edge Retrieval-Augmented Generation (RAG) Pipeline.
    Indexes retail store SOPs, policies, product guides, and synthesizes them
    with dynamic real-time computer vision and Store Brain telemetry.
    Runs 100% offline with zero external vector database dependencies.
    """
    def __init__(self, knowledge_dir: Optional[Path] = None, data_dir: Optional[Path] = None):
        self.knowledge_dir = knowledge_dir or KNOWLEDGE_DIR
        self.data_dir = data_dir or DATA_DIR
        self.chunks: List[RAGDocumentChunk] = []
        self.doc_count = 0
        self.idf: Dict[str, float] = {}
        
        self.index_knowledge_base()

    def index_knowledge_base(self):
        """Index all markdown files from knowledge_dir."""
        self.chunks = []
        
        if self.knowledge_dir and Path(self.knowledge_dir).exists():
            for md_file in sorted(Path(self.knowledge_dir).glob("*.md")):
                try:
                    text = md_file.read_text(encoding="utf-8")
                    self._chunk_markdown_file(md_file.name, text)
                except Exception as e:
                    print(f"[StoreRAGPipeline] Warning indexing {md_file.name}: {e}")

        self._compute_idf()

    def _chunk_markdown_file(self, filename: str, text: str):
        lines = text.splitlines()
        doc_title = filename.replace(".md", "").replace("_", " ").title()
        current_section = "Overview"
        current_content: List[str] = []
        chunk_idx = 0

        for line in lines:
            if line.startswith("# "):
                doc_title = line[2:].strip()
            elif line.startswith("## ") or line.startswith("### "):
                if current_content:
                    c_text = "\n".join(current_content).strip()
                    if len(c_text) > 20:
                        chunk_id = f"{filename}#{chunk_idx}"
                        self.chunks.append(RAGDocumentChunk(
                            chunk_id=chunk_id,
                            title=doc_title,
                            section=current_section,
                            content=c_text,
                            source=filename,
                            chunk_type="knowledge"
                        ))
                        chunk_idx += 1
                    current_content = []
                current_section = line.lstrip("#").strip()
            else:
                current_content.append(line)

        if current_content:
            c_text = "\n".join(current_content).strip()
            if len(c_text) > 20:
                chunk_id = f"{filename}#{chunk_idx}"
                self.chunks.append(RAGDocumentChunk(
                    chunk_id=chunk_id,
                    title=doc_title,
                    section=current_section,
                    content=c_text,
                    source=filename,
                    chunk_type="knowledge"
                ))

    def _compute_idf(self):
        self.doc_count = len(self.chunks)
        if self.doc_count == 0:
            self.idf = {}
            return

        df: Counter = Counter()
        for chunk in self.chunks:
            unique_terms = set(chunk.tokens)
            for term in unique_terms:
                df[term] += 1

        self.idf = {
            term: math.log(1.0 + (self.doc_count - count + 0.5) / (count + 0.5))
            for term, count in df.items()
        }

    def build_telemetry_chunks(self, store_state: dict) -> List[RAGDocumentChunk]:
        """Convert live dynamic store state into contextual RAG chunks."""
        telemetry_chunks = []
        traffic = store_state.get("traffic", {})
        queue = store_state.get("queue", {})
        stock = store_state.get("stock", {})
        alerts = store_state.get("alerts", [])
        price_audit = store_state.get("price_audit", [])
        brain = store_state.get("brain", {})
        roi = store_state.get("business_impact", {})

        # 1. Live Inventory & Stockouts
        stock_items = stock.get("items", [])
        oos = [i["product_name"] for i in stock_items if i.get("status") == "OUT_OF_STOCK"]
        low = [f"{i['product_name']} ({i.get('stock', 0)} left)" for i in stock_items if i.get("status") == "LOW_STOCK"]
        
        inv_text = f"Live Shelf Inventory Telemetry:\n"
        inv_text += f"• Out of Stock Depleted Items ({len(oos)}): {', '.join(oos) if oos else 'None'}\n"
        inv_text += f"• Low Stock Items ({len(low)}): {', '.join(low) if low else 'None'}\n"
        inv_text += f"• Total Shelf Stock Health Score: {stock.get('stock_health_score', 100)}%\n"
        inv_text += f"• Monitored SKU Count: {len(stock_items)}"
        telemetry_chunks.append(RAGDocumentChunk(
            chunk_id="telemetry_inventory",
            title="Live CCTV Telemetry",
            section="Shelf Inventory & Out of Stock",
            content=inv_text,
            source="Live CCTV Vision Sensor",
            chunk_type="telemetry"
        ))

        # 2. Live Queue & Checkout State
        q_len = queue.get("queue_length", 0)
        wait_m = queue.get("estimated_wait_time_min", 0.0)
        congestion = queue.get("congestion", False)
        rec = queue.get("recommendation", "Normal queue speed.")
        queue_text = f"Live Queue Telemetry:\n"
        queue_text += f"• Shoppers Waiting in Line: {q_len} customers\n"
        queue_text += f"• Estimated Waiting Time: {wait_m:.1f} minutes\n"
        queue_text += f"• Congestion Status: {'CONGESTED (Level 2 Alert)' if congestion else 'Optimal (Level 1 Flow)'}\n"
        queue_text += f"• Prescriptive System Recommendation: {rec}"
        telemetry_chunks.append(RAGDocumentChunk(
            chunk_id="telemetry_queue",
            title="Live CCTV Telemetry",
            section="Billing Queue & Checkout Flow",
            content=queue_text,
            source="Live Queue Vision Sensor",
            chunk_type="telemetry"
        ))

        # 3. Live Shopper Traffic & Staffing
        cust_cnt = traffic.get("current_customers", 0)
        staff_cnt = traffic.get("current_staff", 0)
        ratio = traffic.get("customer_to_staff_ratio", "N/A")
        total_in = traffic.get("total_in", 0)
        traffic_text = f"Live Shopper Footfall & Staffing:\n"
        traffic_text += f"• Active Customers on Floor: {cust_cnt}\n"
        traffic_text += f"• Active Staff Detected: {staff_cnt}\n"
        traffic_text += f"• Customer to Staff Ratio: {ratio}\n"
        traffic_text += f"• Total Visitors Served Today: {total_in}"
        telemetry_chunks.append(RAGDocumentChunk(
            chunk_id="telemetry_traffic",
            title="Live CCTV Telemetry",
            section="Shopper Footfall & Staffing",
            content=traffic_text,
            source="Live Store Footfall Sensor",
            chunk_type="telemetry"
        ))

        # 4. EasyOCR Price Tag Discrepancies
        mismatches = [p for p in price_audit if p.get("is_mismatch")]
        if mismatches:
            ocr_text = f"EasyOCR Shelf Price Discrepancies Detected ({len(mismatches)}):\n"
            for p in mismatches:
                ocr_text += f"• {p.get('product_name')}: Shelf Tag shows ₹{p.get('detected_shelf_price', 0):.2f}, Master ERP POS price is ₹{p.get('catalog_price', 0):.2f}\n"
            telemetry_chunks.append(RAGDocumentChunk(
                chunk_id="telemetry_ocr",
                title="Live OCR Audit",
                section="Price Tag Mismatches",
                content=ocr_text,
                source="Live EasyOCR Camera Engine",
                chunk_type="telemetry"
            ))

        # 5. Store Brain Predictive Directives & ROI
        actions = brain.get("top_prioritized_actions", [])
        if actions:
            brain_text = f"Store Brain Top Prioritized Directives:\n"
            for idx, act in enumerate(actions[:4], start=1):
                brain_text += f"{idx}. [{act.get('type')}] {act.get('action')} (Zone: {act.get('zone')}, Deadline: {act.get('deadline_mins')} mins, Risk: ₹{act.get('revenue_at_risk', 0):.0f})\n"
            telemetry_chunks.append(RAGDocumentChunk(
                chunk_id="telemetry_brain",
                title="Store Brain Predictive Engine",
                section="Tactical Directives",
                content=brain_text,
                source="Edge Store Brain",
                chunk_type="telemetry"
            ))

        prot_rev = roi.get("revenue_protected_today", 0.0)
        lost_sales = roi.get("total_estimated_lost_sales_today", 0.0)
        if prot_rev > 0 or lost_sales > 0:
            roi_text = f"Store Financial ROI Today:\n"
            roi_text += f"• Revenue Protected: ₹{prot_rev:,.2f}\n"
            roi_text += f"• Estimated Lost Sales: ₹{lost_sales:,.2f}\n"
            roi_text += f"• Staff Hours Saved: {roi.get('staff_hours_saved_today', 0.0)} hrs\n"
            roi_text += f"• Stockout Reduction: +{roi.get('stockout_reduction_pct', 0.0)}%"
            telemetry_chunks.append(RAGDocumentChunk(
                chunk_id="telemetry_roi",
                title="Business Impact Engine",
                section="Financial ROI",
                content=roi_text,
                source="Edge ROI Engine",
                chunk_type="telemetry"
            ))

        return telemetry_chunks

    def retrieve(self, query: str, store_state: Optional[dict] = None, top_k: int = 4) -> List[Dict[str, Any]]:
        """
        Hybrid retrieval across store knowledge documents and live telemetry.
        Returns top relevant chunks with scores and citations.
        """
        q_tokens = RAGDocumentChunk._tokenize(query)
        if not q_tokens:
            q_tokens = query.lower().split()

        # Combine static knowledge chunks with dynamic telemetry chunks
        all_candidate_chunks = list(self.chunks)
        if store_state:
            telemetry_chunks = self.build_telemetry_chunks(store_state)
            all_candidate_chunks.extend(telemetry_chunks)

        scored_results = []

        for chunk in all_candidate_chunks:
            score = 0.0
            matched_terms = 0

            # 1. TF-IDF & term matching
            for token in q_tokens:
                tf = chunk.term_freqs.get(token, 0)
                if tf > 0:
                    idf_val = self.idf.get(token, 1.5)
                    score += (tf * idf_val)
                    matched_terms += 1
                elif token in chunk.content.lower():
                    score += 0.5
                    matched_terms += 1

            # 2. Entity keyword boosting
            q_lower = query.lower()
            if chunk.chunk_type == "telemetry":
                # High priority for live operational intents
                if any(k in q_lower for k in ["now", "right now", "status", "current", "what should i do", "today", "live", "queue", "stock", "ratio", "urgent"]):
                    score += 2.5
            
            # Boost section or title matches
            if any(token in chunk.title.lower() or token in chunk.section.lower() for token in q_tokens):
                score += 1.5

            if score > 0:
                scored_results.append({
                    "chunk_id": chunk.chunk_id,
                    "title": chunk.title,
                    "section": chunk.section,
                    "content": chunk.content,
                    "source": chunk.source,
                    "chunk_type": chunk.chunk_type,
                    "score": round(score, 3)
                })

        # Sort descending by score
        scored_results.sort(key=lambda x: x["score"], reverse=True)
        return scored_results[:top_k]

    def build_rag_context(self, query: str, store_state: dict, top_k: int = 4) -> Dict[str, Any]:
        """
        Prepares structured RAG context block and citations list for prompt synthesis.
        """
        retrieved_chunks = self.retrieve(query, store_state, top_k=top_k)
        
        context_blocks = []
        sources = []

        for c in retrieved_chunks:
            source_tag = f"{c['source']} — {c['section']}"
            if source_tag not in sources:
                sources.append(source_tag)
            
            context_blocks.append(
                f"### [{c['title'].upper()}: {c['section']}] (Source: {c['source']})\n{c['content']}"
            )

        rag_context_str = "\n\n".join(context_blocks)
        return {
            "context_str": rag_context_str,
            "chunks": retrieved_chunks,
            "sources": sources
        }

    def list_knowledge_documents(self) -> List[Dict[str, Any]]:
        """Returns metadata of all indexed documents in the knowledge base."""
        docs_summary: Dict[str, Dict[str, Any]] = {}
        for c in self.chunks:
            if c.source not in docs_summary:
                docs_summary[c.source] = {
                    "filename": c.source,
                    "title": c.title,
                    "chunk_count": 0,
                    "sections": []
                }
            docs_summary[c.source]["chunk_count"] += 1
            if c.section not in docs_summary[c.source]["sections"]:
                docs_summary[c.source]["sections"].append(c.section)

        return list(docs_summary.values())
