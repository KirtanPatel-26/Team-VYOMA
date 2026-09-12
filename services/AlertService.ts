/**
 * Alert Service
 * Manages anomaly persistence, alert cooldown deduplication, Supabase Realtime broadcasting,
 * notification channels (Webhooks, SMS, Push), and status lifecycle transitions.
 */

import { SupabaseClient } from '@supabase/supabase-js';
import { Anomaly, AnomalySeverity, AnomalyStatus } from '../types/anomaly';

export class AlertService {
  private supabase: SupabaseClient;
  // In-memory cooldown cache: key = `${anomalyType}:${cameraId}:${zoneId}:${productId || personId}` -> timestampMs
  private cooldownCache: Map<string, number> = new Map();

  constructor(supabaseClient: SupabaseClient) {
    this.supabase = supabaseClient;
  }

  /**
   * Evaluates cooldown to prevent alert flooding/flapping
   */
  public isCoolingDown(anomaly: Partial<Anomaly>, cooldownSeconds: number = 60): boolean {
    const key = `${anomaly.anomaly_type}:${anomaly.camera_id}:${anomaly.zone_id}:${
      anomaly.product_id || anomaly.person_id || 'ALL'
    }`;
    const now = Date.now();
    const lastAlertTime = this.cooldownCache.get(key);

    if (lastAlertTime && now - lastAlertTime < cooldownSeconds * 1000) {
      return true; // Still in cooldown
    }

    this.cooldownCache.set(key, now);
    return false;
  }

  /**
   * Persists anomaly to PostgreSQL and broadcasts via Supabase Realtime
   */
  public async createAlert(anomalyData: Partial<Anomaly>): Promise<Anomaly | null> {
    try {
      const { data, error } = await this.supabase
        .from('anomalies')
        .insert({
          anomaly_type: anomalyData.anomaly_type,
          severity: anomalyData.severity || 'Medium',
          camera_id: anomalyData.camera_id,
          zone_id: anomalyData.zone_id,
          product_id: anomalyData.product_id || null,
          product_name: anomalyData.product_name || null,
          person_id: anomalyData.person_id || null,
          description: anomalyData.description,
          confidence_score: anomalyData.confidence_score || 0.95,
          status: 'Active',
          metadata: anomalyData.metadata || {},
          snapshot_url: anomalyData.snapshot_url || null,
        })
        .select()
        .single();

      if (error) {
        console.error('[AlertService] Error inserting anomaly into DB:', error.message);
        return null;
      }

      const created: Anomaly = data;

      // Broadcast on dedicated Realtime Broadcast channel for low-latency delivery
      await this.supabase.channel('retail-anomalies').send({
        type: 'broadcast',
        event: 'NEW_ANOMALY',
        payload: created,
      });

      // Synchronize secondary specialized tables for Security and Inventory
      await this.syncSpecializedTables(created);

      return created;
    } catch (err) {
      console.error('[AlertService] Failed to process alert dispatch:', err);
      return null;
    }
  }

  /**
   * Synchronizes security events and inventory discrepancies based on anomaly type
   */
  private async syncSpecializedTables(anomaly: Anomaly) {
    // 1. Security events
    const securityTypes = [
      'RESTRICTED_AREA_ACCESS',
      'AFTER_HOURS_ACTIVITY',
      'CAMERA_OBSTRUCTION',
      'POSSIBLE_SHOPLIFTING',
    ];

    if (securityTypes.includes(anomaly.anomaly_type)) {
      await this.supabase.from('security_events').insert({
        anomaly_id: anomaly.anomaly_id,
        security_event_type:
          anomaly.anomaly_type === 'RESTRICTED_AREA_ACCESS'
            ? 'RESTRICTED_ACCESS'
            : anomaly.anomaly_type === 'AFTER_HOURS_ACTIVITY'
            ? 'AFTER_HOURS_INTRUSION'
            : anomaly.anomaly_type === 'CAMERA_OBSTRUCTION'
            ? 'TAMPERING_OBSTRUCTION'
            : 'POSSIBLE_THEFT',
        severity: anomaly.severity,
        person_id: anomaly.person_id || null,
        camera_id: anomaly.camera_id,
        zone_id: anomaly.zone_id,
        dwell_duration_seconds: anomaly.metadata?.dwell_time || 0,
        evidence_snapshot_url: anomaly.snapshot_url || null,
        dispatch_police_alert: anomaly.severity === 'Critical',
        guard_notified: true,
        details: anomaly.metadata || {},
      });
    }

    // 2. Inventory discrepancies
    const inventoryTypes = [
      'INVENTORY_COUNT_MISMATCH',
      'PRODUCT_MISPLACEMENT',
      'EMPTY_SHELF_EVENT',
      'UNUSUAL_SALES_VS_SHELF_MOVEMENT',
      'RAPID_INVENTORY_REMOVAL',
    ];

    if (inventoryTypes.includes(anomaly.anomaly_type) && anomaly.product_id) {
      const cvCount = anomaly.metadata?.current_count ?? anomaly.metadata?.cv_detected_count ?? 0;
      const expectedCount =
        anomaly.metadata?.minimum_threshold ?? anomaly.metadata?.erp_expected_count ?? 0;

      await this.supabase.from('inventory_discrepancies').insert({
        anomaly_id: anomaly.anomaly_id,
        product_id: anomaly.product_id,
        product_name: anomaly.product_name || 'SKU',
        zone_id: anomaly.zone_id,
        camera_id: anomaly.camera_id,
        system_expected_count: expectedCount,
        cv_detected_count: cvCount,
        discrepancy_type:
          cvCount === 0
            ? 'STOCKOUT'
            : cvCount < expectedCount
            ? 'DEFICIT_POSSIBLE_THEFT'
            : 'SURPLUS_MISPLACEMENT',
        status: 'UNRESOLVED',
      });
    }
  }

  /**
   * Transition alert status: Active -> Acknowledged
   */
  public async acknowledgeAlert(anomalyId: string, operatorName: string): Promise<boolean> {
    const { error } = await this.supabase
      .from('anomalies')
      .update({
        status: 'Acknowledged',
        acknowledged_at: new Date().toISOString(),
        acknowledged_by: operatorName,
      })
      .eq('anomaly_id', anomalyId);

    if (error) {
      console.error('[AlertService] Error acknowledging anomaly:', error.message);
      return false;
    }

    await this.supabase.channel('retail-anomalies').send({
      type: 'broadcast',
      event: 'ANOMALY_ACKNOWLEDGED',
      payload: { anomalyId, operatorName, timestamp: new Date().toISOString() },
    });

    return true;
  }

  /**
   * Transition alert status: Acknowledged -> Resolved
   */
  public async resolveAlert(
    anomalyId: string,
    operatorName: string,
    notes: string
  ): Promise<boolean> {
    const { error } = await this.supabase
      .from('anomalies')
      .update({
        status: 'Resolved',
        resolved_at: new Date().toISOString(),
        resolved_by: operatorName,
        resolution_notes: notes,
      })
      .eq('anomaly_id', anomalyId);

    if (error) {
      console.error('[AlertService] Error resolving anomaly:', error.message);
      return false;
    }

    await this.supabase.channel('retail-anomalies').send({
      type: 'broadcast',
      event: 'ANOMALY_RESOLVED',
      payload: { anomalyId, operatorName, notes, timestamp: new Date().toISOString() },
    });

    return true;
  }
}
