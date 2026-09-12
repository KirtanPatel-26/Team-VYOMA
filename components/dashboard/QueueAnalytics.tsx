/**
 * Queue Analytics Component
 * Real-time checkout queue monitoring, congestion alerts, and counter scaling
 */

'use client';

import React from 'react';
import { Anomaly } from '../../types/anomaly';

interface QueueAnalyticsProps {
  anomalies: Anomaly[];
}

export const QueueAnalytics: React.FC<QueueAnalyticsProps> = ({ anomalies }) => {
  const queueAlerts = anomalies.filter((a) => a.anomaly_type === 'QUEUE_CONGESTION');

  const lanes = [
    { id: 'Lane 1 (Express)', queueLength: 3, waitTimeMin: 2.5, status: 'Optimal' },
    { id: 'Lane 2 (General)', queueLength: 11, waitTimeMin: 9.0, status: 'Congested' },
    { id: 'Lane 3 (Self-Checkout)', queueLength: 4, waitTimeMin: 3.0, status: 'Optimal' },
    { id: 'Lane 4 (Backup)', queueLength: 0, waitTimeMin: 0.0, status: 'Closed' },
  ];

  return (
    <div className="space-y-6">
      {/* Dynamic Recommendation Banner */}
      {queueAlerts.length > 0 && (
        <div className="bg-amber-500/10 border border-amber-500/30 rounded-xl p-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="text-2xl">⚡</span>
            <div>
              <h4 className="text-sm font-bold text-amber-300">Congestion Surge Detected</h4>
              <p className="text-xs text-amber-200/80">
                Lane 2 has exceeded 10 customers. Recommended action: Open Backup Counter Lane 4.
              </p>
            </div>
          </div>
          <button className="px-4 py-2 bg-amber-500 hover:bg-amber-600 text-black font-bold text-xs rounded-lg transition-colors">
            Open Counter 4 Now
          </button>
        </div>
      )}

      {/* Counter Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        {lanes.map((lane) => (
          <div key={lane.id} className="bg-slate-900 border border-slate-800 rounded-xl p-4">
            <div className="flex justify-between items-center mb-2">
              <span className="text-xs font-semibold text-slate-300">{lane.id}</span>
              <span
                className={`text-[10px] font-bold px-2 py-0.5 rounded ${
                  lane.status === 'Congested'
                    ? 'bg-red-500/20 text-red-400'
                    : lane.status === 'Closed'
                    ? 'bg-slate-800 text-slate-500'
                    : 'bg-emerald-500/20 text-emerald-400'
                }`}
              >
                {lane.status}
              </span>
            </div>
            <div className="flex items-baseline gap-2 mt-2">
              <span className="text-3xl font-extrabold text-white">{lane.queueLength}</span>
              <span className="text-xs text-slate-400">customers</span>
            </div>
            <div className="mt-3 text-xs text-slate-400 flex justify-between">
              <span>Avg Wait:</span>
              <span className="font-semibold text-white">{lane.waitTimeMin} mins</span>
            </div>
            {/* Progress bar gauge */}
            <div className="mt-2 h-1.5 w-full bg-slate-800 rounded-full overflow-hidden">
              <div
                className={`h-full ${
                  lane.queueLength > 8
                    ? 'bg-red-500'
                    : lane.queueLength > 4
                    ? 'bg-amber-500'
                    : 'bg-emerald-500'
                }`}
                style={{ width: `${Math.min(100, (lane.queueLength / 12) * 100)}%` }}
              ></div>
            </div>
          </div>
        ))}
      </div>

      {/* Queue Alert History */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden p-4">
        <h4 className="text-sm font-bold text-white mb-3">Queue Congestion Events</h4>
        {queueAlerts.length === 0 ? (
          <p className="text-xs text-slate-500">No congestion incidents reported in the current period.</p>
        ) : (
          <div className="space-y-2">
            {queueAlerts.map((qa) => (
              <div
                key={qa.anomaly_id}
                className="bg-slate-850 p-3 rounded-lg border border-slate-800 flex justify-between items-center text-xs"
              >
                <div>
                  <p className="font-semibold text-white">{qa.description}</p>
                  <p className="text-[11px] text-slate-400 mt-0.5">
                    Zone: {qa.zone_id} | Detected at: {new Date(qa.created_at).toLocaleTimeString()}
                  </p>
                </div>
                <span className="text-xs text-amber-400 font-semibold">{qa.status}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
