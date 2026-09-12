/**
 * Security Center Component
 * Focused operations center for Restricted Zone breaches, After-Hours Intrusions,
 * Camera Obstructions, and Shoplifting Investigations.
 */

'use client';

import React from 'react';
import { Anomaly } from '../../types/anomaly';

interface SecurityCenterProps {
  anomalies: Anomaly[];
}

export const SecurityCenter: React.FC<SecurityCenterProps> = ({ anomalies }) => {
  const securityTypes = [
    'RESTRICTED_AREA_ACCESS',
    'AFTER_HOURS_ACTIVITY',
    'CAMERA_OBSTRUCTION',
    'POSSIBLE_SHOPLIFTING',
  ];

  const securityAlerts = anomalies.filter((a) => securityTypes.includes(a.anomaly_type));

  const cameras = [
    { id: 'CAM_01', name: 'Warehouse Restricted Gate', status: 'Online', alerts: 1 },
    { id: 'CAM_02', name: 'Main Aisle 1 (High Value)', status: 'Online', alerts: 0 },
    { id: 'CAM_03', name: 'Store Entrance & Exit', status: 'Online', alerts: 2 },
    { id: 'CAM_04', name: 'Backroom Loading Dock', status: 'Warning', alerts: 1 },
  ];

  return (
    <div className="space-y-6">
      {/* CCTV Camera Status Matrix */}
      <div>
        <h3 className="text-sm font-bold uppercase tracking-wider text-slate-300 mb-3 flex items-center gap-2">
          <span className="inline-block h-2 w-2 rounded-full bg-emerald-400 animate-ping"></span>
          Surveillance Camera Mesh
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
          {cameras.map((cam) => (
            <div
              key={cam.id}
              className="bg-slate-900 border border-slate-800 rounded-xl p-3 relative overflow-hidden"
            >
              <div className="flex justify-between items-center text-xs text-slate-400 mb-2">
                <span className="font-semibold text-white">{cam.id}</span>
                <span
                  className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                    cam.status === 'Online'
                      ? 'bg-emerald-500/20 text-emerald-400'
                      : 'bg-amber-500/20 text-amber-400'
                  }`}
                >
                  {cam.status}
                </span>
              </div>
              <div className="h-24 bg-slate-950 rounded-lg flex items-center justify-center border border-slate-800 relative group cursor-pointer">
                <span className="text-xs text-slate-500 font-mono">[LIVE RTSP FEED]</span>
                <div className="absolute inset-0 bg-indigo-600/10 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
                  <span className="text-xs text-indigo-300 font-semibold">Inspect Stream</span>
                </div>
              </div>
              <p className="text-[11px] text-slate-400 mt-2 truncate">{cam.name}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Security Incidents Table */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden">
        <div className="p-4 border-b border-slate-800 flex justify-between items-center">
          <h3 className="text-sm font-bold text-white">Security Events & Intrusions</h3>
          <span className="text-xs text-slate-400">{securityAlerts.length} recorded</span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs text-slate-300">
            <thead className="bg-slate-800/60 uppercase tracking-wider text-[10px] text-slate-400">
              <tr>
                <th className="px-4 py-3">Event Type</th>
                <th className="px-4 py-3">Severity</th>
                <th className="px-4 py-3">Camera / Zone</th>
                <th className="px-4 py-3">Details</th>
                <th className="px-4 py-3">Timestamp</th>
                <th className="px-4 py-3 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800">
              {securityAlerts.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-4 py-6 text-center text-slate-500">
                    No active security breaches or intrusions recorded.
                  </td>
                </tr>
              ) : (
                securityAlerts.map((alert) => (
                  <tr key={alert.anomaly_id} className="hover:bg-slate-800/40 transition-colors">
                    <td className="px-4 py-3 font-semibold text-white">
                      {alert.anomaly_type.replace(/_/g, ' ')}
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                          alert.severity === 'Critical'
                            ? 'bg-red-500/20 text-red-400 border border-red-500/30'
                            : 'bg-orange-500/20 text-orange-400 border border-orange-500/30'
                        }`}
                      >
                        {alert.severity}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <div>{alert.camera_id}</div>
                      <div className="text-slate-500 text-[10px]">{alert.zone_id}</div>
                    </td>
                    <td className="px-4 py-3 max-w-xs truncate text-slate-300">
                      {alert.description}
                    </td>
                    <td className="px-4 py-3 text-slate-400">
                      {new Date(alert.created_at).toLocaleTimeString()}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <button className="px-3 py-1 bg-red-600/20 hover:bg-red-600/30 text-red-400 border border-red-500/30 rounded font-semibold text-[11px]">
                        Dispatch Guard
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
