/**
 * AI-Powered Anomaly Detection & Custom Trigger Engine
 * Central Orchestrator executing all 13 retail anomalies across CV telemetry,
 * POS transaction logs, and inventory ledger streams.
 */

import { SupabaseClient } from '@supabase/supabase-js';
import {
  CVTelemetryFrame,
  Anomaly,
  POSSaleEvent,
  InventoryLedgerEvent,
  ZoneConfig,
  AnomalyTriggerRule,
} from '../types/anomaly';
import { ActivityMonitoringService } from './ActivityMonitoringService';
import { ShelfMonitoringService } from './ShelfMonitoringService';
import { QueueIntelligenceService } from './QueueIntelligenceService';
import { SecurityMonitoringService } from './SecurityMonitoringService';
import { AlertService } from './AlertService';

export class AnomalyDetectionEngine {
  private activityService: ActivityMonitoringService;
  private shelfService: ShelfMonitoringService;
  private queueService: QueueIntelligenceService;
  private securityService: SecurityMonitoringService;
  private alertService: AlertService;

  // Caches for fast in-memory lookups
  private zonesMap: Map<string, ZoneConfig> = new Map();
  private triggerRulesMap: Map<string, AnomalyTriggerRule> = new Map();
  private previousShelfCounts: Map<string, number> = new Map(); // `${zoneId}:${productId}` -> count
  private erpStockExpected: Map<string, number> = new Map();     // `${productId}` -> expected count

  constructor(supabaseClient: SupabaseClient) {
    this.activityService = new ActivityMonitoringService();
    this.shelfService = new ShelfMonitoringService();
    this.queueService = new QueueIntelligenceService();
    this.securityService = new SecurityMonitoringService();
    this.alertService = new AlertService(supabaseClient);
  }

  /**
   * Loads or refreshes active zones and custom trigger rules
   */
  public updateConfigurations(zones: ZoneConfig[], rules: AnomalyTriggerRule[]) {
    this.zonesMap.clear();
    zones.forEach((z) => this.zonesMap.set(z.id, z));

    this.triggerRulesMap.clear();
    rules.forEach((r) => this.triggerRulesMap.set(r.anomaly_type, r));
  }

  public setErpExpectedStock(stockMap: Map<string, number>) {
    this.erpStockExpected = stockMap;
  }

  /**
   * Ingests a new CV telemetry frame and processes all 13 anomaly rules
   */
  public async processTelemetryFrame(
    telemetry: CVTelemetryFrame,
    recentSales: POSSaleEvent[] = [],
    recentLedger: InventoryLedgerEvent[] = []
  ): Promise<Anomaly[]> {
    const rawAnomalies: Partial<Anomaly>[] = [];

    // ------------------------------------------------------------------------
    // 1. SECURITY & ACCESS EVALUATION (Anomalies 1, 2, 7, 8)
    // ------------------------------------------------------------------------
    // Anomaly 1: Possible Shoplifting (Disappearance without POS/Ledger)
    const shopliftingAlerts = this.securityService.detectPossibleShoplifting(
      telemetry,
      this.previousShelfCounts,
      recentSales,
      recentLedger
    );
    rawAnomalies.push(...shopliftingAlerts);

    // Anomaly 2: Restricted Area Access
    const restrictedAlerts = this.securityService.detectRestrictedAreaAccess(
      telemetry,
      this.zonesMap
    );
    rawAnomalies.push(...restrictedAlerts);

    // Anomaly 7: After Hours Activity
    const afterHoursAlerts = this.securityService.detectAfterHoursActivity(telemetry);
    rawAnomalies.push(...afterHoursAlerts);

    // Anomaly 8: Camera Obstruction
    const cameraAlerts = this.securityService.detectCameraObstruction(telemetry);
    rawAnomalies.push(...cameraAlerts);

    // ------------------------------------------------------------------------
    // 2. SHOPPER ACTIVITY & BEHAVIOR (Anomalies 3, 10, 11)
    // ------------------------------------------------------------------------
    // Anomaly 3: Suspicious Loitering (> 5 mins vs normal 30s)
    const loiteringAlerts = this.activityService.detectSuspiciousLoitering(
      telemetry,
      this.zonesMap
    );
    rawAnomalies.push(...loiteringAlerts);

    // Anomaly 10: Unusual Customer Crowding (> 15 in aisle)
    const crowdAlerts = this.activityService.detectCrowdFormation(
      telemetry,
      this.zonesMap
    );
    rawAnomalies.push(...crowdAlerts);

    // Anomaly 11: High Dwell Time Hotspot
    const hotspotAlerts = this.activityService.detectHighDwellTimeHotspot(telemetry);
    rawAnomalies.push(...hotspotAlerts);

    // ------------------------------------------------------------------------
    // 3. SHELF & INVENTORY COMPLIANCE (Anomalies 4, 5, 9, 12, 13)
    // ------------------------------------------------------------------------
    // Anomaly 4: Product Misplacement (Wrong shelf category)
    const misplacementAlerts = this.shelfService.detectProductMisplacement(
      telemetry,
      this.zonesMap
    );
    rawAnomalies.push(...misplacementAlerts);

    // Anomaly 5: Rapid Inventory Removal (> 10 items in 5 mins)
    const rapidRemovalAlerts = this.shelfService.detectRapidInventoryRemoval(telemetry);
    rawAnomalies.push(...rapidRemovalAlerts);

    // Anomaly 9: Empty Shelf Event (Stockout or below threshold)
    const emptyShelfAlerts = this.shelfService.detectEmptyShelf(telemetry);
    rawAnomalies.push(...emptyShelfAlerts);

    // Anomaly 12: Inventory Count Mismatch (CV count != ERP expected)
    const mismatchAlerts = this.shelfService.detectInventoryCountMismatch(
      telemetry,
      this.erpStockExpected
    );
    rawAnomalies.push(...mismatchAlerts);

    // Anomaly 13: Unusual Sales vs Shelf Movement (Shelf clears, POS flat)
    const salesDiscrepancyAlerts = this.shelfService.detectSalesVsShelfDiscrepancy(
      telemetry,
      recentSales
    );
    rawAnomalies.push(...salesDiscrepancyAlerts);

    // ------------------------------------------------------------------------
    // 4. QUEUE CONGESTION (Anomaly 6)
    // ------------------------------------------------------------------------
    const queueAlerts = this.queueService.evaluateQueueCongestion(telemetry);
    rawAnomalies.push(...queueAlerts);

    // ------------------------------------------------------------------------
    // 5. CACHE STATE UPDATE (Tracking shelf counts for subsequent cycles)
    // ------------------------------------------------------------------------
    for (const item of telemetry.shelfDetections) {
      this.previousShelfCounts.set(`${item.shelfZoneId}:${item.productId}`, item.detectedCount);
    }

    // ------------------------------------------------------------------------
    // 6. FILTER THROUGH DYNAMIC TRIGGER RULES & PERSIST / BROADCAST ALERTS
    // ------------------------------------------------------------------------
    const savedAnomalies: Anomaly[] = [];

    for (const raw of rawAnomalies) {
      const rule = this.triggerRulesMap.get(raw.anomaly_type!);

      // Check if rule is disabled
      if (rule && !rule.enabled) {
        continue;
      }

      // Check cooldown deduplication
      const cooldownSec = rule?.cooldown_period_seconds || 60;
      if (this.alertService.isCoolingDown(raw, cooldownSec)) {
        continue;
      }

      // If rule specifies default severity, apply it
      if (rule?.default_severity) {
        raw.severity = rule.default_severity;
      }

      const created = await this.alertService.createAlert(raw);
      if (created) {
        savedAnomalies.push(created);
      }
    }

    return savedAnomalies;
  }

  public getAlertService(): AlertService {
    return this.alertService;
  }
}
