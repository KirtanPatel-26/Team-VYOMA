/**
 * Shelf Monitoring Service
 * Analyzes SKU-level planogram compliance, stock depletion rates,
 * misplacement, empty shelves, and cross-checks with POS/ERP data.
 */

import { CVTelemetryFrame, ShelfItemDetection, Anomaly, POSSaleEvent, ZoneConfig } from '../types/anomaly';

interface HistoricShelfCount {
  count: number;
  timestamp: number;
}

export class ShelfMonitoringService {
  // In-memory temporal window store for rate-of-removal calculations: key = `${storeCode}:${shelfZoneId}:${productId}`
  private historicalCounts: Map<string, HistoricShelfCount[]> = new Map();

  /**
   * Records current shelf snapshot into sliding window
   */
  public recordShelfSnapshot(storeCode: string, detection: ShelfItemDetection, timestampMs: number) {
    const key = `${storeCode}:${detection.shelfZoneId}:${detection.productId}`;
    const history = this.historicalCounts.get(key) || [];
    history.push({ count: detection.detectedCount, timestamp: timestampMs });

    // Keep only observations within last 15 minutes
    const cutoff = timestampMs - 15 * 60 * 1000;
    const pruned = history.filter((h) => h.timestamp >= cutoff);
    this.historicalCounts.set(key, pruned);
  }

  /**
   * Detects Product Misplacement: Product detected in wrong shelf zone.
   * Examples: Toothpaste in Soap Zone, Soap in Beverage Zone.
   */
  public detectProductMisplacement(
    telemetry: CVTelemetryFrame,
    zonesMap: Map<string, ZoneConfig>
  ): Partial<Anomaly>[] {
    const anomalies: Partial<Anomaly>[] = [];

    for (const item of telemetry.shelfDetections) {
      const zone = zonesMap.get(item.shelfZoneId);
      if (!zone) continue;

      const isExpectedSku = zone.expected_skus && zone.expected_skus.length > 0
        ? zone.expected_skus.includes(item.productId)
        : true;

      const isCategoryMismatch =
        item.targetCategory &&
        item.detectedCategory &&
        item.targetCategory.toLowerCase() !== item.detectedCategory.toLowerCase();

      if (!isExpectedSku || isCategoryMismatch) {
        anomalies.push({
          anomaly_type: 'PRODUCT_MISPLACEMENT',
          severity: 'Medium',
          camera_id: telemetry.cameraId,
          zone_id: item.shelfZoneId,
          product_id: item.productId,
          product_name: item.productName,
          confidence_score: item.confidence || 0.91,
          description: `Product Misplacement Detected: ${item.productName} (${item.detectedCategory}) found in ${zone.name} (${item.targetCategory} Zone).`,
          metadata: {
            product_id: item.productId,
            product_name: item.productName,
            detected_in_zone: item.shelfZoneId,
            expected_category: item.targetCategory,
            detected_category: item.detectedCategory,
            timestamp: telemetry.timestamp,
          },
        });
      }
    }

    return anomalies;
  }

  /**
   * Detects Empty Shelf Event: Shelf becomes empty (count = 0) OR stock below minimum threshold.
   */
  public detectEmptyShelf(telemetry: CVTelemetryFrame): Partial<Anomaly>[] {
    const anomalies: Partial<Anomaly>[] = [];

    for (const item of telemetry.shelfDetections) {
      if (item.detectedCount === 0) {
        anomalies.push({
          anomaly_type: 'EMPTY_SHELF_EVENT',
          severity: 'High',
          camera_id: telemetry.cameraId,
          zone_id: item.shelfZoneId,
          product_id: item.productId,
          product_name: item.productName,
          confidence_score: 0.98,
          description: `Out Of Stock Alert: Shelf ${item.shelfZoneId} for ${item.productName} is completely empty.`,
          metadata: {
            product_id: item.productId,
            product_name: item.productName,
            shelf_zone: item.shelfZoneId,
            current_count: 0,
            minimum_threshold: item.expectedCount,
            timestamp: telemetry.timestamp,
          },
        });
      } else if (item.detectedCount < item.expectedCount) {
        anomalies.push({
          anomaly_type: 'EMPTY_SHELF_EVENT',
          severity: 'Medium',
          camera_id: telemetry.cameraId,
          zone_id: item.shelfZoneId,
          product_id: item.productId,
          product_name: item.productName,
          confidence_score: 0.93,
          description: `Low Stock Alert: ${item.productName} count is ${item.detectedCount} (below minimum threshold of ${item.expectedCount}).`,
          metadata: {
            product_id: item.productId,
            product_name: item.productName,
            shelf_zone: item.shelfZoneId,
            current_count: item.detectedCount,
            minimum_threshold: item.expectedCount,
            timestamp: telemetry.timestamp,
          },
        });
      }
    }

    return anomalies;
  }

  /**
   * Detects Rapid Inventory Removal: Inventory decreases faster than normal.
   * Example: Normally 2 products/hour, Current 20 products / 5 minutes.
   */
  public detectRapidInventoryRemoval(
    telemetry: CVTelemetryFrame,
    maxAllowedDropIn5Min: number = 10
  ): Partial<Anomaly>[] {
    const anomalies: Partial<Anomaly>[] = [];
    const now = new Date(telemetry.timestamp).getTime();

    for (const item of telemetry.shelfDetections) {
      this.recordShelfSnapshot(telemetry.storeCode, item, now);
      const key = `${telemetry.storeCode}:${item.shelfZoneId}:${item.productId}`;
      const history = this.historicalCounts.get(key) || [];

      if (history.length >= 2) {
        // Find observation closest to 5 minutes ago
        const fiveMinAgo = now - 5 * 60 * 1000;
        const past = history.find((h) => h.timestamp <= fiveMinAgo) || history[0];
        const countDiff = past.count - item.detectedCount;

        if (countDiff >= maxAllowedDropIn5Min) {
          anomalies.push({
            anomaly_type: 'RAPID_INVENTORY_REMOVAL',
            severity: 'High',
            camera_id: telemetry.cameraId,
            zone_id: item.shelfZoneId,
            product_id: item.productId,
            product_name: item.productName,
            confidence_score: 0.95,
            description: `Abnormal Inventory Movement: ${item.productName} dropped by ${countDiff} units within 5 minutes in zone ${item.shelfZoneId}.`,
            metadata: {
              product_id: item.productId,
              product_name: item.productName,
              shelf_zone: item.shelfZoneId,
              previous_count: past.count,
              current_count: item.detectedCount,
              dropped_units: countDiff,
              elapsed_seconds: Math.round((now - past.timestamp) / 1000),
              timestamp: telemetry.timestamp,
            },
          });
        }
      }
    }

    return anomalies;
  }

  /**
   * Detects Inventory Count Mismatch: Detected inventory count ≠ Expected inventory count in ERP.
   */
  public detectInventoryCountMismatch(
    telemetry: CVTelemetryFrame,
    erpExpectedMap: Map<string, number>
  ): Partial<Anomaly>[] {
    const anomalies: Partial<Anomaly>[] = [];

    for (const item of telemetry.shelfDetections) {
      const erpExpected = erpExpectedMap.get(item.productId);
      if (erpExpected !== undefined && erpExpected !== item.detectedCount) {
        const delta = item.detectedCount - erpExpected;
        anomalies.push({
          anomaly_type: 'INVENTORY_COUNT_MISMATCH',
          severity: 'High',
          camera_id: telemetry.cameraId,
          zone_id: item.shelfZoneId,
          product_id: item.productId,
          product_name: item.productName,
          confidence_score: 0.92,
          description: `Inventory Count Mismatch: Detected ${item.detectedCount} units for ${item.productName} vs ${erpExpected} units in ERP (Discrepancy: ${delta > 0 ? `+${delta}` : delta}).`,
          metadata: {
            product_id: item.productId,
            product_name: item.productName,
            shelf_zone: item.shelfZoneId,
            cv_detected_count: item.detectedCount,
            erp_expected_count: erpExpected,
            discrepancy_delta: delta,
            timestamp: telemetry.timestamp,
          },
        });
      }
    }

    return anomalies;
  }

  /**
   * Detects Unusual Sales vs Shelf Movement: Products disappear from shelf BUT sales records remain low.
   */
  public detectSalesVsShelfDiscrepancy(
    telemetry: CVTelemetryFrame,
    posSalesInWindow: POSSaleEvent[]
  ): Partial<Anomaly>[] {
    const anomalies: Partial<Anomaly>[] = [];
    const now = new Date(telemetry.timestamp).getTime();

    for (const item of telemetry.shelfDetections) {
      const key = `${telemetry.storeCode}:${item.shelfZoneId}:${item.productId}`;
      const history = this.historicalCounts.get(key) || [];
      if (history.length < 2) continue;

      const initial = history[0];
      const shelfDrop = initial.count - item.detectedCount;

      if (shelfDrop >= 5) {
        // Sum POS sales for this SKU in the same time window
        const posSoldUnits = posSalesInWindow
          .filter((p) => p.skuId === item.productId)
          .reduce((sum, p) => sum + p.quantity, 0);

        // Discrepancy if products removed exceed registered sales significantly
        if (shelfDrop - posSoldUnits >= 4) {
          anomalies.push({
            anomaly_type: 'UNUSUAL_SALES_VS_SHELF_MOVEMENT',
            severity: 'Critical',
            camera_id: telemetry.cameraId,
            zone_id: item.shelfZoneId,
            product_id: item.productId,
            product_name: item.productName,
            confidence_score: 0.96,
            description: `Sales and Inventory Discrepancy: ${shelfDrop} units of ${item.productName} disappeared from shelf, but only ${posSoldUnits} registered at POS registers.`,
            metadata: {
              product_id: item.productId,
              product_name: item.productName,
              shelf_zone: item.shelfZoneId,
              shelf_units_removed: shelfDrop,
              pos_registered_sales: posSoldUnits,
              unaccounted_difference: shelfDrop - posSoldUnits,
              timestamp: telemetry.timestamp,
            },
          });
        }
      }
    }

    return anomalies;
  }
}
