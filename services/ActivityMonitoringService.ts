/**
 * Activity Monitoring Service
 * Evaluates shopper footfall dynamics, suspicious loitering, crowd formation,
 * and high dwell-time interest/congestion hotspots.
 */

import { CVTelemetryFrame, Anomaly, ZoneConfig } from '../types/anomaly';

export class ActivityMonitoringService {
  /**
   * Detects loitering: Person remains near a shelf or aisle longer than threshold.
   * Example: Normal browsing = 30s, Suspicious > 5 minutes (300s).
   */
  public detectSuspiciousLoitering(
    telemetry: CVTelemetryFrame,
    zonesMap: Map<string, ZoneConfig>
  ): Partial<Anomaly>[] {
    const anomalies: Partial<Anomaly>[] = [];

    for (const person of telemetry.trackedPersons) {
      const zone = zonesMap.get(person.currentZone);
      const threshold = zone?.loitering_threshold_seconds || 300;

      if (person.dwellTimeSeconds >= threshold) {
        anomalies.push({
          anomaly_type: 'SUSPICIOUS_LOITERING',
          severity: 'Medium',
          camera_id: telemetry.cameraId,
          zone_id: person.currentZone,
          person_id: person.trackId,
          confidence_score: 0.94,
          description: `Person #${person.trackId} loitering in zone ${person.currentZone} for ${Math.round(
            person.dwellTimeSeconds
          )}s (Threshold: ${threshold}s).`,
          metadata: {
            person_id: person.trackId,
            dwell_time: person.dwellTimeSeconds,
            shelf_zone: person.currentZone,
            timestamp: telemetry.timestamp,
          },
        });
      }
    }

    return anomalies;
  }

  /**
   * Detects unusual customer crowding: Large number of people inside one zone/aisle.
   * Example: > 15 people in an aisle.
   */
  public detectCrowdFormation(
    telemetry: CVTelemetryFrame,
    zonesMap: Map<string, ZoneConfig>
  ): Partial<Anomaly>[] {
    const anomalies: Partial<Anomaly>[] = [];
    const zoneCounts = new Map<string, number>();

    // Aggregate counts per zone
    for (const person of telemetry.trackedPersons) {
      const count = zoneCounts.get(person.currentZone) || 0;
      zoneCounts.set(person.currentZone, count + 1);
    }

    for (const [zoneId, count] of zoneCounts.entries()) {
      const zone = zonesMap.get(zoneId);
      const crowdThreshold = zone?.max_crowd_threshold || 15;

      if (count >= crowdThreshold) {
        anomalies.push({
          anomaly_type: 'UNUSUAL_CUSTOMER_CROWDING',
          severity: 'Medium',
          camera_id: telemetry.cameraId,
          zone_id: zoneId,
          confidence_score: 0.92,
          description: `Crowd formation detected in ${zoneId}: ${count} people present (Threshold: ${crowdThreshold}).`,
          metadata: {
            zone_id: zoneId,
            occupancy: count,
            threshold: crowdThreshold,
            timestamp: telemetry.timestamp,
          },
        });
      }
    }

    return anomalies;
  }

  /**
   * Identifies High Dwell-Time Hotspots: Multiple customers spending unusually long time in an area.
   * Business Insight: High merchandising interest or store navigation bottleneck.
   */
  public detectHighDwellTimeHotspot(
    telemetry: CVTelemetryFrame,
    minAggregateDwellSeconds: number = 600
  ): Partial<Anomaly>[] {
    const anomalies: Partial<Anomaly>[] = [];
    const zoneDwells = new Map<string, { totalDwell: number; count: number }>();

    for (const person of telemetry.trackedPersons) {
      const existing = zoneDwells.get(person.currentZone) || { totalDwell: 0, count: 0 };
      existing.totalDwell += person.dwellTimeSeconds;
      existing.count += 1;
      zoneDwells.set(person.currentZone, existing);
    }

    for (const [zoneId, data] of zoneDwells.entries()) {
      if (data.count >= 3 && data.totalDwell >= minAggregateDwellSeconds) {
        const avgDwell = Math.round(data.totalDwell / data.count);
        anomalies.push({
          anomaly_type: 'HIGH_DWELL_TIME_HOTSPOT',
          severity: 'Medium',
          camera_id: telemetry.cameraId,
          zone_id: zoneId,
          confidence_score: 0.88,
          description: `High Dwell Time Hotspot in ${zoneId}: ${data.count} shoppers accumulated ${data.totalDwell}s dwell (Avg: ${avgDwell}s). Potential high-interest or bottleneck.`,
          metadata: {
            zone_id: zoneId,
            shopper_count: data.count,
            total_dwell_seconds: data.totalDwell,
            avg_dwell_seconds: avgDwell,
            business_insight: 'Potential interest area or store congestion',
            timestamp: telemetry.timestamp,
          },
        });
      }
    }

    return anomalies;
  }
}
