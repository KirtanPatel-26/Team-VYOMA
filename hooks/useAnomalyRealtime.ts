/**
 * useAnomalyRealtime Hook
 * Realtime Supabase listener hook for live anomalies, broadcast notifications,
 * badge counters, and audio alarm triggers on critical events.
 */

'use client';

import { useEffect, useState, useCallback } from 'react';
import { supabaseBrowser } from '../lib/supabaseClient';
import { Anomaly, AnomalySeverity, AnomalyStatus } from '../types/anomaly';

export interface AnomalyFilterOptions {
  status?: AnomalyStatus | 'ALL';
  severity?: AnomalySeverity | 'ALL';
  zoneId?: string;
  cameraId?: string;
}

export function useAnomalyRealtime(initialFilters?: AnomalyFilterOptions) {
  const [anomalies, setAnomalies] = useState<Anomaly[]>([]);
  const [latestAlert, setLatestAlert] = useState<Anomaly | null>(null);
  const [unreadCount, setUnreadCount] = useState<number>(0);
  const [loading, setLoading] = useState<boolean>(true);
  const [soundEnabled, setSoundEnabled] = useState<boolean>(true);

  // Play alarm sound for critical incidents
  const playAlertSound = useCallback((severity: AnomalySeverity) => {
    if (typeof window === 'undefined') return;
    try {
      const audio = new Audio(
        severity === 'Critical'
          ? 'https://assets.mixkit.co/active_storage/sfx/2869/2869-preview.mp3' // High-priority alert beep
          : 'https://assets.mixkit.co/active_storage/sfx/2874/2874-preview.mp3' // Warning chime
      );
      audio.volume = 0.6;
      audio.play().catch(() => {
        // Handled silently if browser auto-play policies restrict audio before user gesture
      });
    } catch (e) {
      // Audio fallback silent
    }
  }, []);

  // Fetch initial anomalies snapshot
  const fetchAnomalies = useCallback(async () => {
    setLoading(true);
    let query = supabaseBrowser
      .from('anomalies')
      .select('*')
      .order('created_at', { ascending: false })
      .limit(50);

    if (initialFilters?.status && initialFilters.status !== 'ALL') {
      query = query.eq('status', initialFilters.status);
    }
    if (initialFilters?.severity && initialFilters.severity !== 'ALL') {
      query = query.eq('severity', initialFilters.severity);
    }
    if (initialFilters?.zoneId) {
      query = query.eq('zone_id', initialFilters.zoneId);
    }
    if (initialFilters?.cameraId) {
      query = query.eq('camera_id', initialFilters.cameraId);
    }

    const { data, error } = await query;
    if (error) {
      console.error('[useAnomalyRealtime] Failed to load anomalies:', error.message);
    } else {
      setAnomalies(data || []);
      const activeCount = (data || []).filter((a) => a.status === 'Active').length;
      setUnreadCount(activeCount);
    }
    setLoading(false);
  }, [initialFilters]);

  useEffect(() => {
    fetchAnomalies();

    // 1. Postgres Changes Subscription for DB-level insertions/updates
    const dbChannel = supabaseBrowser
      .channel('anomalies-db-sync')
      .on(
        'postgres_changes',
        { event: '*', schema: 'public', table: 'anomalies' },
        (payload) => {
          if (payload.eventType === 'INSERT') {
            const newAnomaly = payload.new as Anomaly;
            setAnomalies((prev) => [newAnomaly, ...prev]);
            setLatestAlert(newAnomaly);
            setUnreadCount((c) => c + 1);

            if (soundEnabled && (newAnomaly.severity === 'Critical' || newAnomaly.severity === 'High')) {
              playAlertSound(newAnomaly.severity);
            }
          } else if (payload.eventType === 'UPDATE') {
            const updated = payload.new as Anomaly;
            setAnomalies((prev) =>
              prev.map((a) => (a.anomaly_id === updated.anomaly_id ? updated : a))
            );
          } else if (payload.eventType === 'DELETE') {
            const deletedId = (payload.old as Anomaly).anomaly_id;
            setAnomalies((prev) => prev.filter((a) => a.anomaly_id !== deletedId));
          }
        }
      )
      .subscribe();

    // 2. Broadcast Channel for zero-latency messaging
    const broadcastChannel = supabaseBrowser
      .channel('retail-anomalies')
      .on('broadcast', { event: 'NEW_ANOMALY' }, ({ payload }) => {
        setLatestAlert(payload);
      })
      .on('broadcast', { event: 'ANOMALY_ACKNOWLEDGED' }, ({ payload }) => {
        setAnomalies((prev) =>
          prev.map((a) =>
            a.anomaly_id === payload.anomalyId
              ? { ...a, status: 'Acknowledged', acknowledged_by: payload.operatorName }
              : a
          )
        );
      })
      .on('broadcast', { event: 'ANOMALY_RESOLVED' }, ({ payload }) => {
        setAnomalies((prev) =>
          prev.map((a) =>
            a.anomaly_id === payload.anomalyId
              ? { ...a, status: 'Resolved', resolved_by: payload.operatorName, resolution_notes: payload.notes }
              : a
          )
        );
      })
      .subscribe();

    return () => {
      supabaseBrowser.removeChannel(dbChannel);
      supabaseBrowser.removeChannel(broadcastChannel);
    };
  }, [fetchAnomalies, playAlertSound, soundEnabled]);

  // Acknowledge Action
  const acknowledgeAnomaly = async (anomalyId: string, operatorName: string = 'Store Manager') => {
    try {
      const res = await fetch(`/api/anomalies/${anomalyId}/acknowledge`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ operatorName }),
      });
      if (res.ok) {
        setAnomalies((prev) =>
          prev.map((a) => (a.anomaly_id === anomalyId ? { ...a, status: 'Acknowledged', acknowledged_by: operatorName } : a))
        );
      }
    } catch (err) {
      console.error('Failed to acknowledge anomaly:', err);
    }
  };

  // Resolve Action
  const resolveAnomaly = async (
    anomalyId: string,
    notes: string,
    operatorName: string = 'Store Manager'
  ) => {
    try {
      const res = await fetch(`/api/anomalies/${anomalyId}/resolve`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ operatorName, notes }),
      });
      if (res.ok) {
        setAnomalies((prev) =>
          prev.map((a) =>
            a.anomaly_id === anomalyId ? { ...a, status: 'Resolved', resolved_by: operatorName, resolution_notes: notes } : a
          )
        );
      }
    } catch (err) {
      console.error('Failed to resolve anomaly:', err);
    }
  };

  return {
    anomalies,
    latestAlert,
    unreadCount,
    loading,
    soundEnabled,
    setSoundEnabled,
    acknowledgeAnomaly,
    resolveAnomaly,
    refetch: fetchAnomalies,
  };
}
