/**
 * Security Monitoring Service
 * Analyzes physical store security: Shoplifting correlation, restricted zone breaches,
 * after-hours intrusion, and camera tampering/obstruction.
 */

import {
  CVTelemetryFrame,
  Anomaly,
  POSSaleEvent,
  InventoryLedgerEvent,
  ZoneConfig,
} from '../types/anomaly';

export class SecurityMonitoringService {
  /**
   * Detects Possible Shoplifting:
   * - Product disappears from shelf (detected count decreases)
   * - No billing record exists for that SKU in the recent window
   * - No inventory transaction exists (not an employee audit or restock return)
   */
  public detectPossibleShoplifting(
    telemetry: CVTelemetryFrame,
    previousShelfCounts: Map<string, number>, // key = `${zoneId}:${productId}`
    recentSales: POSSaleEvent[],
    recentLedger: InventoryLedgerEvent[]
  ): Partial<Anomaly>[] {
    const anomalies: Partial<Anomaly>[] = [];

    for (const item of telemetry.shelfDetections) {
      const key = `${item.shelfZoneId}:${item.productId}`;
      const prevCount = previousShelfCounts.get(key);

      if (prevCount !== undefined && item.detectedCount < prevCount) {
        const unitsMissing = prevCount - item.detectedCount;

        // Check if billing record exists
        const posRecord = recentSales.find((s) => s.skuId === item.productId);

        // Check if authorized inventory transaction exists (e.g. damaged write-off or transfer)
        const ledgerRecord = recentLedger.find((l) => l.skuId === item.productId);

        if (!posRecord && !ledgerRecord) {
          anomalies.push({
            anomaly_type: 'POSSIBLE_SHOPLIFTING',
            severity: 'Critical',
            camera_id: telemetry.cameraId,
            zone_id: item.shelfZoneId,
            product_id: item.productId,
            product_name: item.productName,
            confidence_score: 0.97,
            description: `Possible Shoplifting Detected: ${unitsMissing} units of ${item.productName} removed from ${item.shelfZoneId} without corresponding billing or inventory adjustment.`,
            metadata: {
              product_name: item.productName,
              camera_id: telemetry.cameraId,
              zone_id: item.shelfZoneId,
              previous_count: prevCount,
              current_count: item.detectedCount,
              timestamp: telemetry.timestamp,
              missing_units: unitsMissing,
              has_pos_record: false,
              has_ledger_record: false,
            },
          });
        }
      }
    }

    return anomalies;
  }

  /**
   * Detects Restricted Area Access:
   * Person enters restricted warehouse or staff-only zone.
   */
  public detectRestrictedAreaAccess(
    telemetry: CVTelemetryFrame,
    zonesMap: Map<string, ZoneConfig>
  ): Partial<Anomaly>[] {
    const anomalies: Partial<Anomaly>[] = [];

    for (const person of telemetry.trackedPersons) {
      const zone = zonesMap.get(person.currentZone);
      if (zone?.is_restricted || person.currentZone.toUpperCase().includes('RESTRICTED')) {
        anomalies.push({
          anomaly_type: 'RESTRICTED_AREA_ACCESS',
          severity: 'High',
          camera_id: telemetry.cameraId,
          zone_id: person.currentZone,
          person_id: person.trackId,
          confidence_score: 0.98,
          description: `Unauthorized Access Detected: Person #${person.trackId} entered restricted zone ${zone?.name || person.currentZone}.`,
          metadata: {
            person_id: person.trackId,
            camera_id: telemetry.cameraId,
            zone_id: person.currentZone,
            timestamp: telemetry.timestamp,
            dwell_seconds: person.dwellTimeSeconds,
          },
        });
      }
    }

    return anomalies;
  }

  /**
   * Detects After Hours Activity:
   * Store is closed AND a human centroid is detected.
   */
  public detectAfterHoursActivity(telemetry: CVTelemetryFrame): Partial<Anomaly>[] {
    const anomalies: Partial<Anomaly>[] = [];

    if (!telemetry.isStoreOpen && telemetry.trackedPersons.length > 0) {
      anomalies.push({
        anomaly_type: 'AFTER_HOURS_ACTIVITY',
        severity: 'Critical',
        camera_id: telemetry.cameraId,
        zone_id: telemetry.trackedPersons[0].currentZone || 'MAIN_FLOOR',
        person_id: telemetry.trackedPersons[0].trackId,
        confidence_score: 0.99,
        description: `After Hours Activity Detected: Store is closed but ${telemetry.trackedPersons.length} human(s) detected inside.`,
        metadata: {
          store_status: 'CLOSED',
          detected_humans_count: telemetry.trackedPersons.length,
          camera_id: telemetry.cameraId,
          timestamp: telemetry.timestamp,
        },
      });
    }

    return anomalies;
  }

  /**
   * Detects Camera Obstruction:
   * Camera covered, blocked, lens sprayed, or view angle drastically changed.
   */
  public detectCameraObstruction(telemetry: CVTelemetryFrame): Partial<Anomaly>[] {
    const anomalies: Partial<Anomaly>[] = [];
    const health = telemetry.cameraHealth;

    const isBlurredOrCovered = health.laplacianVariance < 50.0;
    const isBlackedOutOrBlinded = health.meanLuminance < 15.0 || health.meanLuminance > 245.0;
    const isAngleTampered = health.structuralSimilarityIndex < 0.40;

    if (isBlurredOrCovered || isBlackedOutOrBlinded || isAngleTampered) {
      let reason = 'View obstructed or lens covered';
      if (isAngleTampered) reason = 'Camera physical view angle changed / tampered';
      if (isBlackedOutOrBlinded) reason = 'Camera sensor blinded or blacked out';

      anomalies.push({
        anomaly_type: 'CAMERA_OBSTRUCTION',
        severity: 'High',
        camera_id: telemetry.cameraId,
        zone_id: 'CAMERA_HARDWARE',
        confidence_score: 0.95,
        description: `Camera Obstruction Detected on ${telemetry.cameraId}: ${reason}.`,
        metadata: {
          camera_id: telemetry.cameraId,
          laplacian_variance: health.laplacianVariance,
          mean_luminance: health.meanLuminance,
          ssim: health.structuralSimilarityIndex,
          timestamp: telemetry.timestamp,
        },
      });
    }

    return anomalies;
  }
}
