# Store Operations Standard Operating Procedures (SOP)

## 1. Store Daily Operating Hours & Routines
- **Morning Store Opening**: 08:00 AM. Initial shelf audit must be completed by 08:30 AM before customer doors unlock.
- **Evening Store Closing**: 10:00 PM. End-of-day inventory reconciliation and physical shelf count verification occur between 10:00 PM and 10:45 PM.
- **Mid-Day Shift Handover**: 03:00 PM. Cash drawer balance check and replenishment priority review.

## 2. Shelf Replenishment & Stockout Prevention Protocols
- **Critical Stockout Definition**: Any SKU with 0 units on the physical shelf is classified as `CRITICAL_DEPLETION`.
- **Low Stock Threshold**: Any SKU falling below its configured `minimum_stock` (typically 2 to 3 units) triggers a `LOW_STOCK` advisory.
- **Replenishment SLA**:
  - `CRITICAL` items must be replenished from back-room storage within **15 minutes** of edge alert generation.
  - `HIGH` priority items must be replenished within **30 minutes**.
  - Always rotate stock using **FIFO (First In, First Out)** to avoid expired goods on customer shelves.
- **Overstocking Prohibition**: Shelves must not exceed 12 units per SKU facing to prevent product toppling and occlusion in computer vision edge cameras.

## 3. Planogram Compliance & Zone Discipline
- Monitored retail zones:
  1. `Zone 1: Beverages & Juices`: Fanta Orange, Real Orange Juice, Coca Cola.
  2. `Zone 2: Snacks & Biscuits`: Pringles Original, Oreo, Lays Classic, Dairy Milk.
  3. `Zone 3: Dairy & Essentials`: Amul Taaza, Dove Soap, Colgate Paste.
- **Misplaced Items Protocol**:
  - When CCTV detects an item in the wrong shelf zone (e.g., Dairy Milk found in Beverages), floor staff must relocate it to its home zone within **20 minutes**.
  - Misplaced items distort inventory counts and lead to false customer stockout perceptions.

## 4. EasyOCR Shelf Price Audit & Tampering SOP
- Every shelf-edge digital or printed price label must match the master ERP / Point-of-Sale (POS) database price with 100% fidelity.
- If an EasyOCR price tag discrepancy is flagged:
  1. Inspect the shelf tag immediately.
  2. If the tag is incorrect, replace it with the verified barcode tag.
  3. If the master catalog changed without tag printing, honor the lower displayed shelf price to the customer per consumer rights regulations, then immediately update the tag.
