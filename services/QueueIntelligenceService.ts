/**
 * Queue Intelligence Service
 * Monitors checkout bottlenecks, queue lengths, average wait times,
 * and recommends dynamic cashier counter opening/closing.
 */

import { CVTelemetryFrame, Anomaly, QueueStatusMetric } from '../types/anomaly';

export class QueueIntelligenceService {
  /**
   * Evaluates Queue Congestion: Queue length exceeds threshold (e.g., > 10 customers)
   */
  public evaluateQueueCongestion(
    telemetry: CVTelemetryFrame,
    maxQueueLengthThreshold: number = 10
  ): Partial<Anomaly>[] {
    const anomalies: Partial<Anomaly>[] = [];

    if (!telemetry.queueStatus) {
      // If queue status is not pre-computed by edge, compute from tracked persons in checkout zone
      const checkoutPersons = telemetry.trackedPersons.filter(
        (p) => p.currentZone.toUpperCase().includes('CHECKOUT') || p.currentZone.toUpperCase().includes('COUNTER')
      );

      if (checkoutPersons.length >= maxQueueLengthThreshold) {
        anomalies.push({
          anomaly_type: 'QUEUE_CONGESTION',
          severity: 'Medium',
          camera_id: telemetry.cameraId,
          zone_id: 'ZONE_CHECKOUT',
          confidence_score: 0.95,
          description: `High Customer Congestion: Detected ${checkoutPersons.length} customers in checkout zone (Threshold: ${maxQueueLengthThreshold}). Recommended action: Open counter 2.`,
          metadata: {
            queue_length: checkoutPersons.length,
            threshold: maxQueueLengthThreshold,
            recommendation: 'Open additional POS checkout counter immediately',
            timestamp: telemetry.timestamp,
          },
        });
      }
      return anomalies;
    }

    const queue = telemetry.queueStatus;
    if (queue.customerCount >= maxQueueLengthThreshold) {
      anomalies.push({
        anomaly_type: 'QUEUE_CONGESTION',
        severity: queue.customerCount >= maxQueueLengthThreshold * 1.5 ? 'High' : 'Medium',
        camera_id: telemetry.cameraId,
        zone_id: queue.checkoutZoneId,
        confidence_score: 0.96,
        description: `High Customer Congestion: ${queue.customerCount} customers waiting in queue (Wait time est: ${Math.round(
          queue.estimatedWaitTimeSeconds / 60
        )} mins).`,
        metadata: {
          queue_length: queue.customerCount,
          active_counters: queue.activeCounters,
          estimated_wait_seconds: queue.estimatedWaitTimeSeconds,
          threshold: maxQueueLengthThreshold,
          recommendation: `Open ${Math.ceil(queue.customerCount / 5) - queue.activeCounters} additional counter(s)`,
          timestamp: telemetry.timestamp,
        },
      });
    }

    return anomalies;
  }
}
