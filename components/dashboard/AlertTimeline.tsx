/**
 * Alert Timeline Component
 * Chronological visualization of anomaly events, acknowledgments, and resolutions
 */

'use client';

import React from 'react';
import { Anomaly } from '../../types/anomaly';

interface AlertTimelineProps {
  anomalies: Anomaly[];
}

export const AlertTimeline: React.FC<AlertTimelineProps> = ({ anomalies }) => {
  const sorted = [...anomalies].sort(
    (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
  );

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-6">
      <h3 className="text-sm font-bold text-white mb-6 flex items-center justify-between">
        <span>Operational Incident Timeline</span>
        <span className="text-xs font-normal text-slate-400">Live event stream</span>
      </h3>

      {sorted.length === 0 ? (
        <p className="text-xs text-slate-500 text-center py-8">No incident timeline events recorded.</p>
      ) : (
        <div className="relative pl-6 space-y-6 before:absolute before:left-2 before:top-2 before:bottom-2 before:w-0.5 before:bg-slate-800">
          {sorted.map((item) => {
            const isCritical = item.severity === 'Critical';
            const isHigh = item.severity === 'High';

            return (
              <div key={item.anomaly_id} className="relative group">
                {/* Node dot */}
                <div
                  className={`absolute -left-[27px] top-1.5 h-3.5 w-3.5 rounded-full border-2 border-slate-900 ${
                    isCritical
                      ? 'bg-red-500'
                      : isHigh
                      ? 'bg-orange-500'
                      : 'bg-indigo-500'
                  }`}
                />

                <div className="bg-slate-950/60 border border-slate-800/80 rounded-lg p-3 hover:border-slate-700 transition-colors">
                  <div className="flex justify-between items-center text-xs mb-1">
                    <span className="font-semibold text-white">
                      {item.anomaly_type.replace(/_/g, ' ')}
                    </span>
                    <span className="text-slate-400 text-[11px]">
                      {new Date(item.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    </span>
                  </div>

                  <p className="text-xs text-slate-300">{item.description}</p>

                  <div className="flex items-center gap-3 mt-2 text-[10px] text-slate-400">
                    <span>Camera: <strong className="text-slate-200">{item.camera_id}</strong></span>
                    <span>Zone: <strong className="text-slate-200">{item.zone_id}</strong></span>
                    <span>Status: <strong className="text-indigo-300">{item.status}</strong></span>
                    {item.resolved_by && (
                      <span className="text-emerald-400">Resolved by: {item.resolved_by}</span>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
