/**
 * Smart Retail & Warehouse Intelligence Platform
 * Anomaly Detection & Custom Trigger Engine - Type Definitions
 * Enterprise-grade, type-safe interfaces for 13 multi-modal retail anomalies
 */

export type AnomalySeverity = 'Low' | 'Medium' | 'High' | 'Critical';
export type AnomalyStatus = 'Active' | 'Acknowledged' | 'Resolved';

export type AnomalyType =
  | 'POSSIBLE_SHOPLIFTING'
  | 'RESTRICTED_AREA_ACCESS'
  | 'SUSPICIOUS_LOITERING'
  | 'PRODUCT_MISPLACEMENT'
  | 'RAPID_INVENTORY_REMOVAL'
  | 'QUEUE_CONGESTION'
  | 'AFTER_HOURS_ACTIVITY'
  | 'CAMERA_OBSTRUCTION'
  | 'EMPTY_SHELF_EVENT'
  | 'UNUSUAL_CUSTOMER_CROWDING'
  | 'HIGH_DWELL_TIME_HOTSPOT'
  | 'INVENTORY_COUNT_MISMATCH'
  | 'UNUSUAL_SALES_VS_SHELF_MOVEMENT';

export interface BoundingBox {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
  confidence: number;
}

export interface PersonTrack {
  trackId: number;
  centroid: [number, number];
  currentZone: string;
  dwellTimeSeconds: number;
  velocity: number;
  lastSeenTimestamp: string;
}

export interface ShelfItemDetection {
  productId: string;
  productName: string;
  shelfZoneId: string;
  detectedCount: number;
  expectedCount: number;
  targetCategory: string;
  detectedCategory: string;
  confidence: number;
}

export interface CameraObstructionMetrics {
  cameraId: string;
  laplacianVariance: number; // Blur metric (< 60 implies blurred/covered)
  meanLuminance: number;     // 0-255 (< 15 = blacked out, > 245 = blinded)
  structuralSimilarityIndex: number; // Compare against background model (< 0.4 = tampered)
  opticalFlowMagnitude: number;
}

export interface QueueStatusMetric {
  checkoutZoneId: string;
  customerCount: number;
  estimatedWaitTimeSeconds: number;
  activeCounters: number;
  openLanesCount: number;
}

export interface CVTelemetryFrame {
  cameraId: string;
  storeCode: string;
  timestamp: string;
  isStoreOpen: boolean;
  trackedPersons: PersonTrack[];
  shelfDetections: ShelfItemDetection[];
  cameraHealth: CameraObstructionMetrics;
  queueStatus?: QueueStatusMetric;
}

export interface POSSaleEvent {
  transactionId: string;
  storeCode: string;
  skuId: string;
  quantity: number;
  timestamp: string;
}

export interface InventoryLedgerEvent {
  ledgerId: string;
  storeCode: string;
  skuId: string;
  changeQty: number;
  reason: 'sale' | 'restock' | 'audit_correction' | 'shrinkage';
  timestamp: string;
}

export interface Anomaly {
  anomaly_id: string;
  anomaly_type: AnomalyType;
  severity: AnomalySeverity;
  camera_id: string;
  zone_id: string;
  product_id?: string;
  product_name?: string;
  person_id?: number;
  description: string;
  confidence_score: number;
  status: AnomalyStatus;
  metadata?: Record<string, any>;
  snapshot_url?: string;
  created_at: string;
  acknowledged_at?: string;
  acknowledged_by?: string;
  resolved_at?: string;
  resolved_by?: string;
  resolution_notes?: string;
}

export interface AnomalyEvent {
  id: string;
  anomaly_id: string;
  anomaly_type: AnomalyType;
  event_phase: 'TRIGGERED' | 'ESCALATED' | 'ACKNOWLEDGED' | 'AUTO_RESOLVED' | 'MANUAL_RESOLVED';
  severity: AnomalySeverity;
  camera_id: string;
  zone_id: string;
  event_payload: Record<string, any>;
  recorded_at: string;
}

export interface SecurityEvent {
  id: string;
  anomaly_id?: string;
  security_event_type: 'RESTRICTED_ACCESS' | 'AFTER_HOURS_INTRUSION' | 'TAMPERING_OBSTRUCTION' | 'POSSIBLE_THEFT';
  severity: AnomalySeverity;
  person_id?: number;
  camera_id: string;
  zone_id: string;
  dwell_duration_seconds: number;
  evidence_snapshot_url?: string;
  dispatch_police_alert: boolean;
  guard_notified: boolean;
  details?: Record<string, any>;
  created_at: string;
}

export interface InventoryDiscrepancy {
  id: string;
  anomaly_id?: string;
  product_id: string;
  product_name: string;
  zone_id: string;
  camera_id: string;
  system_expected_count: number;
  cv_detected_count: number;
  discrepancy_delta: number;
  discrepancy_type: 'DEFICIT_POSSIBLE_THEFT' | 'SURPLUS_MISPLACEMENT' | 'STOCKOUT';
  estimated_financial_impact: number;
  status: 'UNRESOLVED' | 'RECONCILED' | 'WRITTEN_OFF';
  created_at: string;
  reconciled_at?: string;
}

export interface ZoneConfig {
  id: string;
  store_code: string;
  name: string;
  zone_type: 'SHELF' | 'AISLE' | 'CHECKOUT' | 'RESTRICTED_WAREHOUSE' | 'ENTRANCE' | 'EXIT';
  is_restricted: boolean;
  polygon_coordinates: [number, number][];
  max_crowd_threshold: number;
  loitering_threshold_seconds: number;
  expected_skus: string[];
}

export interface AnomalyTriggerRule {
  id: string;
  anomaly_type: AnomalyType;
  enabled: boolean;
  default_severity: AnomalySeverity;
  cooldown_period_seconds: number;
  threshold_value: number;
  evaluation_window_seconds: number;
  notification_channels: string[];
  custom_params: Record<string, any>;
}

export interface RealtimeAnomalyPayload {
  eventType: 'INSERT' | 'UPDATE' | 'DELETE';
  new: Anomaly;
  old?: Anomaly;
}
