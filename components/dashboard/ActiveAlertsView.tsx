/**
 * Active Alerts View Component
 * Interactive cards for currently active anomalies with quick action buttons
 */

'use client';

import React, { useState } from 'react';
import { Anomaly, AnomalySeverity } from '../../types/anomaly';

interface ActiveAlertsViewProps {
  anomalies: Anomaly[];
  onAcknowledge: (id: string) => void;
  onResolve: (id: string, notes: string) => void;
}

const severityColors: Record<AnomalySeverity, { bg: string; text: string; border: string }> = {
  Critical: { bg: 'bg-red-500/20', text: 'text-red-400', border: 'border-red-500/40' },
  High: { bg: 'bg-orange-500/20', text: 'text-orange-400', border: 'border-orange-500/40' },
  Medium: { bg: 'bg-amber-500/20', text: 'text-amber-400', border: 'border-amber-500/40' },
  Low: { bg: 'bg-blue-500/20', text: 'text-blue-400', border: 'border-blue-500/40' },
};

export const ActiveAlertsView: React.FC<ActiveAlertsViewProps> = ({
  anomalies,
  onAcknowledge,
  onResolve,
}) => {
  const [selectedAnomaly, setSelectedAnomaly] = useState<Anomaly | null>(null);
  const [resolveNotes, setResolveNotes] = useState<string>('');
  const [resolvingId, setResolvingId] = useState<string | null>(null);

  const activeList = anomalies.filter((a) => a.status === 'Active' || a.status === 'Acknowledged');

  const handleResolveSubmit = (id: string) => {
    onResolve(id, resolveNotes || 'Resolved by floor manager');
    setResolvingId(null);
    setResolveNotes('');
  };

  if (activeList.length === 0) {
    return (
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-12 text-center">
        <div className="text-4xl mb-3">✅</div>
        <h3 className="text-lg font-bold text-white">All Systems Operational</h3>
        <p className="text-sm text-slate-400 mt-1">No active anomalies detected across cameras or shelves.</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {activeList.map((anomaly) => {
          const colors = severityColors[anomaly.severity] || severityColors.Medium;
          const isAck = anomaly.status === 'Acknowledged';

          return (
            <div
              key={anomaly.anomaly_id}
              className={`bg-slate-900/90 border ${colors.border} rounded-xl p-5 shadow-md flex flex-col justify-between transition-all hover:border-indigo-400`}
            >
              <div>
                <div className="flex items-center justify-between gap-2 mb-2">
                  <span
                    className={`text-xs px-2.5 py-0.5 rounded-full font-bold uppercase tracking-wider ${colors.bg} ${colors.text} border ${colors.border}`}
                  >
                    {anomaly.severity}
                  </span>
                  <span className="text-xs text-slate-400">
                    {new Date(anomaly.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                  </span>
                </div>

                <h4 className="text-base font-bold text-white">{anomaly.description}</h4>

                <div className="grid grid-cols-2 gap-2 my-3 text-xs text-slate-300 bg-slate-800/50 p-2.5 rounded-lg">
                  <div>
                    <span className="text-slate-400">Zone:</span> <span className="font-semibold text-white">{anomaly.zone_id}</span>
                  </div>
                  <div>
                    <span className="text-slate-400">Camera:</span> <span className="font-semibold text-white">{anomaly.camera_id}</span>
                  </div>
                  <div>
                    <span className="text-slate-400">Confidence:</span>{' '}
                    <span className="font-semibold text-emerald-400">{Math.round(anomaly.confidence_score * 100)}%</span>
                  </div>
                  <div>
                    <span className="text-slate-400">Status:</span>{' '}
                    <span className={`font-semibold ${isAck ? 'text-amber-400' : 'text-red-400'}`}>{anomaly.status}</span>
                  </div>
                </div>

                {anomaly.snapshot_url && (
                  <div className="mb-3">
                    <img
                      src={anomaly.snapshot_url}
                      alt="Evidence Snapshot"
                      className="rounded-lg h-32 w-full object-cover border border-slate-700"
                    />
                  </div>
                )}
              </div>

              {/* Action Buttons */}
              <div className="pt-3 border-t border-slate-800 flex items-center justify-between gap-2">
                <button
                  onClick={() => setSelectedAnomaly(anomaly)}
                  className="text-xs text-slate-400 hover:text-white underline"
                >
                  View Details
                </button>

                <div className="flex items-center gap-2">
                  {!isAck && (
                    <button
                      onClick={() => onAcknowledge(anomaly.anomaly_id)}
                      className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-amber-500/20 text-amber-300 hover:bg-amber-500/30 border border-amber-500/40 transition-colors"
                    >
                      Acknowledge
                    </button>
                  )}

                  {resolvingId === anomaly.anomaly_id ? (
                    <div className="flex items-center gap-1">
                      <input
                        type="text"
                        placeholder="Resolution notes..."
                        value={resolveNotes}
                        onChange={(e) => setResolveNotes(e.target.value)}
                        className="text-xs bg-slate-800 border border-slate-700 rounded px-2 py-1 text-white focus:outline-none"
                      />
                      <button
                        onClick={() => handleResolveSubmit(anomaly.anomaly_id)}
                        className="px-2 py-1 text-xs bg-emerald-600 text-white rounded hover:bg-emerald-500"
                      >
                        Save
                      </button>
                    </div>
                  ) : (
                    <button
                      onClick={() => setResolvingId(anomaly.anomaly_id)}
                      className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-emerald-500/20 text-emerald-300 hover:bg-emerald-500/30 border border-emerald-500/40 transition-colors"
                    >
                      Resolve
                    </button>
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Metadata Detail Modal */}
      {selectedAnomaly && (
        <div className="fixed inset-0 z-50 bg-black/75 flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-700 rounded-2xl max-w-lg w-full p-6 space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <h3 className="text-base font-bold text-white">Anomaly Details</h3>
              <button
                onClick={() => setSelectedAnomaly(null)}
                className="text-slate-400 hover:text-white text-xl font-bold"
              >
                &times;
              </button>
            </div>
            <div className="space-y-2 text-xs text-slate-300">
              <p><span className="text-slate-500">ID:</span> {selectedAnomaly.anomaly_id}</p>
              <p><span className="text-slate-500">Type:</span> {selectedAnomaly.anomaly_type}</p>
              <p><span className="text-slate-500">Description:</span> {selectedAnomaly.description}</p>
              <p><span className="text-slate-500">Timestamp:</span> {new Date(selectedAnomaly.created_at).toLocaleString()}</p>
              <div className="mt-3">
                <span className="text-slate-400 font-semibold">Raw Metadata:</span>
                <pre className="mt-1 bg-slate-950 p-3 rounded-lg overflow-x-auto text-[11px] text-emerald-400 border border-slate-800">
                  {JSON.stringify(selectedAnomaly.metadata || {}, null, 2)}
                </pre>
              </div>
            </div>
            <div className="text-right pt-2">
              <button
                onClick={() => setSelectedAnomaly(null)}
                className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-white text-xs font-semibold rounded-lg"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
