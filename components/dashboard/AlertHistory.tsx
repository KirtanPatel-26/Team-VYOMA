/**
 * Alert History Component
 * Full searchable and filterable database audit log with CSV export
 */

'use client';

import React, { useState, useMemo } from 'react';
import { Anomaly } from '../../types/anomaly';

interface AlertHistoryProps {
  anomalies: Anomaly[];
}

export const AlertHistory: React.FC<AlertHistoryProps> = ({ anomalies }) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [severityFilter, setSeverityFilter] = useState('ALL');
  const [statusFilter, setStatusFilter] = useState('ALL');

  const filtered = useMemo(() => {
    return anomalies.filter((a) => {
      const matchSearch =
        a.description.toLowerCase().includes(searchTerm.toLowerCase()) ||
        a.zone_id.toLowerCase().includes(searchTerm.toLowerCase()) ||
        a.camera_id.toLowerCase().includes(searchTerm.toLowerCase()) ||
        a.anomaly_type.toLowerCase().includes(searchTerm.toLowerCase());

      const matchSeverity = severityFilter === 'ALL' || a.severity === severityFilter;
      const matchStatus = statusFilter === 'ALL' || a.status === statusFilter;

      return matchSearch && matchSeverity && matchStatus;
    });
  }, [anomalies, searchTerm, severityFilter, statusFilter]);

  const exportCSV = () => {
    const headers = ['Anomaly ID', 'Type', 'Severity', 'Camera', 'Zone', 'Status', 'Description', 'Timestamp'];
    const rows = filtered.map((a) => [
      a.anomaly_id,
      a.anomaly_type,
      a.severity,
      a.camera_id,
      a.zone_id,
      a.status,
      `"${a.description.replace(/"/g, '""')}"`,
      a.created_at,
    ]);

    const csvContent = 'data:text/csv;charset=utf-8,' + [headers.join(','), ...rows.map((e) => e.join(','))].join('\n');
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement('a');
    link.setAttribute('href', encodedUri);
    link.setAttribute('download', `retail_anomalies_export_${Date.now()}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden">
      {/* Filter and Search Bar */}
      <div className="p-4 border-b border-slate-800 flex flex-wrap items-center justify-between gap-4">
        <div className="flex flex-wrap items-center gap-3">
          <input
            type="text"
            placeholder="Search anomalies..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="bg-slate-800 border border-slate-700 text-white text-xs rounded-lg px-3 py-2 w-64 focus:outline-none focus:border-indigo-500"
          />

          <select
            value={severityFilter}
            onChange={(e) => setSeverityFilter(e.target.value)}
            className="bg-slate-800 border border-slate-700 text-white text-xs rounded-lg px-3 py-2 focus:outline-none"
          >
            <option value="ALL">All Severities</option>
            <option value="Critical">Critical</option>
            <option value="High">High</option>
            <option value="Medium">Medium</option>
            <option value="Low">Low</option>
          </select>

          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="bg-slate-800 border border-slate-700 text-white text-xs rounded-lg px-3 py-2 focus:outline-none"
          >
            <option value="ALL">All Statuses</option>
            <option value="Active">Active</option>
            <option value="Acknowledged">Acknowledged</option>
            <option value="Resolved">Resolved</option>
          </select>
        </div>

        <button
          onClick={exportCSV}
          className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold rounded-lg flex items-center gap-2 transition-colors"
        >
          <span>📥</span> Export CSV
        </button>
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs text-slate-300">
          <thead className="bg-slate-800/60 uppercase tracking-wider text-[10px] text-slate-400">
            <tr>
              <th className="px-4 py-3">Type</th>
              <th className="px-4 py-3">Severity</th>
              <th className="px-4 py-3">Location</th>
              <th className="px-4 py-3">Description</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3 text-right">Timestamp</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800">
            {filtered.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-slate-500">
                  No anomaly records match your filter criteria.
                </td>
              </tr>
            ) : (
              filtered.map((item) => (
                <tr key={item.anomaly_id} className="hover:bg-slate-800/40 transition-colors">
                  <td className="px-4 py-3 font-semibold text-white">
                    {item.anomaly_type.replace(/_/g, ' ')}
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                        item.severity === 'Critical'
                          ? 'bg-red-500/20 text-red-400 border border-red-500/30'
                          : item.severity === 'High'
                          ? 'bg-orange-500/20 text-orange-400 border border-orange-500/30'
                          : 'bg-amber-500/20 text-amber-400 border border-amber-500/30'
                      }`}
                    >
                      {item.severity}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-slate-400">
                    <div>{item.zone_id}</div>
                    <div className="text-[10px] text-slate-500">{item.camera_id}</div>
                  </td>
                  <td className="px-4 py-3 text-slate-300 max-w-sm truncate">{item.description}</td>
                  <td className="px-4 py-3">
                    <span
                      className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                        item.status === 'Active'
                          ? 'text-red-400'
                          : item.status === 'Acknowledged'
                          ? 'text-amber-400'
                          : 'text-emerald-400'
                      }`}
                    >
                      {item.status}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-right text-slate-400">
                    {new Date(item.created_at).toLocaleString()}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};
