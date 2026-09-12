/**
 * Severity Statistics Component
 * Visual KPI metric cards for Critical, High, Medium, and Low severity anomalies
 */

'use client';

import React from 'react';
import { Anomaly } from '../../types/anomaly';

interface SeverityStatsProps {
  anomalies: Anomaly[];
}

export const SeverityStats: React.FC<SeverityStatsProps> = ({ anomalies }) => {
  const stats = {
    critical: anomalies.filter((a) => a.severity === 'Critical' && a.status === 'Active').length,
    high: anomalies.filter((a) => a.severity === 'High' && a.status === 'Active').length,
    medium: anomalies.filter((a) => a.severity === 'Medium' && a.status === 'Active').length,
    low: anomalies.filter((a) => a.severity === 'Low' && a.status === 'Active').length,
    totalActive: anomalies.filter((a) => a.status === 'Active').length,
    acknowledged: anomalies.filter((a) => a.status === 'Acknowledged').length,
    resolved: anomalies.filter((a) => a.status === 'Resolved').length,
  };

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
      {/* Critical */}
      <div className="bg-slate-900 border border-red-500/40 rounded-xl p-4 shadow-lg shadow-red-500/10 flex items-center justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wider text-red-400">Critical Incidents</p>
          <h3 className="text-3xl font-extrabold text-white mt-1">{stats.critical}</h3>
          <p className="text-xs text-slate-400 mt-1">Immediate Owner Attention</p>
        </div>
        <div className="h-12 w-12 rounded-full bg-red-500/20 flex items-center justify-center text-red-400 text-xl font-bold animate-pulse">
          ⚡
        </div>
      </div>

      {/* High */}
      <div className="bg-slate-900 border border-orange-500/40 rounded-xl p-4 shadow-lg shadow-orange-500/10 flex items-center justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wider text-orange-400">High Severity</p>
          <h3 className="text-3xl font-extrabold text-white mt-1">{stats.high}</h3>
          <p className="text-xs text-slate-400 mt-1">Security & Rapid Depletion</p>
        </div>
        <div className="h-12 w-12 rounded-full bg-orange-500/20 flex items-center justify-center text-orange-400 text-xl font-bold">
          ⚠️
        </div>
      </div>

      {/* Medium */}
      <div className="bg-slate-900 border border-amber-500/40 rounded-xl p-4 shadow-lg shadow-amber-500/10 flex items-center justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wider text-amber-400">Medium Severity</p>
          <h3 className="text-3xl font-extrabold text-white mt-1">{stats.medium}</h3>
          <p className="text-xs text-slate-400 mt-1">Queues & Loitering</p>
        </div>
        <div className="h-12 w-12 rounded-full bg-amber-500/20 flex items-center justify-center text-amber-400 text-xl font-bold">
          ⏱️
        </div>
      </div>

      {/* Total Active vs Resolved */}
      <div className="bg-slate-900 border border-indigo-500/40 rounded-xl p-4 shadow-lg shadow-indigo-500/10 flex items-center justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wider text-indigo-400">Active / Resolved</p>
          <h3 className="text-2xl font-extrabold text-white mt-1">
            {stats.totalActive} <span className="text-sm font-medium text-slate-400">/ {stats.resolved}</span>
          </h3>
          <p className="text-xs text-emerald-400 mt-1">{stats.acknowledged} under review</p>
        </div>
        <div className="h-12 w-12 rounded-full bg-indigo-500/20 flex items-center justify-center text-indigo-400 text-xl font-bold">
          📊
        </div>
      </div>
    </div>
  );
};
