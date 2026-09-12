/**
 * Inventory Anomalies Component
 * Tracks SKU planogram misplacement, empty shelves, rapid removal,
 * and ERP count discrepancies.
 */

'use client';

import React from 'react';
import { Anomaly } from '../../types/anomaly';

interface InventoryAnomaliesProps {
  anomalies: Anomaly[];
}

export const InventoryAnomalies: React.FC<InventoryAnomaliesProps> = ({ anomalies }) => {
  const inventoryTypes = [
    'PRODUCT_MISPLACEMENT',
    'RAPID_INVENTORY_REMOVAL',
    'EMPTY_SHELF_EVENT',
    'INVENTORY_COUNT_MISMATCH',
    'UNUSUAL_SALES_VS_SHELF_MOVEMENT',
  ];

  const inventoryAlerts = anomalies.filter((a) => inventoryTypes.includes(a.anomaly_type));

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
          <p className="text-xs uppercase tracking-wider text-slate-400 font-semibold">Stockouts & Empty Shelves</p>
          <h3 className="text-2xl font-bold text-white mt-1">
            {inventoryAlerts.filter((a) => a.anomaly_type === 'EMPTY_SHELF_EVENT').length}
          </h3>
          <p className="text-xs text-amber-400 mt-1">Immediate restocking needed</p>
        </div>

        <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
          <p className="text-xs uppercase tracking-wider text-slate-400 font-semibold">Misplaced SKUs</p>
          <h3 className="text-2xl font-bold text-white mt-1">
            {inventoryAlerts.filter((a) => a.anomaly_type === 'PRODUCT_MISPLACEMENT').length}
          </h3>
          <p className="text-xs text-indigo-400 mt-1">Planogram realignment</p>
        </div>

        <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
          <p className="text-xs uppercase tracking-wider text-slate-400 font-semibold">Sales / Shelf Discrepancies</p>
          <h3 className="text-2xl font-bold text-white mt-1">
            {inventoryAlerts.filter((a) => a.anomaly_type === 'UNUSUAL_SALES_VS_SHELF_MOVEMENT').length}
          </h3>
          <p className="text-xs text-red-400 mt-1">Potential shrink / unbilled</p>
        </div>
      </div>

      <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden">
        <div className="p-4 border-b border-slate-800 flex justify-between items-center">
          <h3 className="text-sm font-bold text-white">Shelf & Inventory Discrepancy Stream</h3>
          <span className="text-xs text-slate-400">{inventoryAlerts.length} issues detected</span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs text-slate-300">
            <thead className="bg-slate-800/60 uppercase tracking-wider text-[10px] text-slate-400">
              <tr>
                <th className="px-4 py-3">Product Name</th>
                <th className="px-4 py-3">Zone / Shelf</th>
                <th className="px-4 py-3">Anomaly Type</th>
                <th className="px-4 py-3">Confidence</th>
                <th className="px-4 py-3">Discrepancy Detail</th>
                <th className="px-4 py-3 text-right">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800">
              {inventoryAlerts.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-4 py-6 text-center text-slate-500">
                    No active shelf or inventory discrepancies detected.
                  </td>
                </tr>
              ) : (
                inventoryAlerts.map((alert) => (
                  <tr key={alert.anomaly_id} className="hover:bg-slate-800/40 transition-colors">
                    <td className="px-4 py-3 font-semibold text-white">
                      {alert.product_name || alert.metadata?.product_name || 'Generic SKU'}
                    </td>
                    <td className="px-4 py-3 text-slate-400">{alert.zone_id}</td>
                    <td className="px-4 py-3">
                      <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">
                        {alert.anomaly_type.replace(/_/g, ' ')}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-emerald-400 font-mono">
                      {Math.round(alert.confidence_score * 100)}%
                    </td>
                    <td className="px-4 py-3 text-slate-300 max-w-sm truncate">
                      {alert.description}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <span
                        className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                          alert.status === 'Active'
                            ? 'text-red-400 bg-red-500/10'
                            : alert.status === 'Acknowledged'
                            ? 'text-amber-400 bg-amber-500/10'
                            : 'text-emerald-400 bg-emerald-500/10'
                        }`}
                      >
                        {alert.status}
                      </span>
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
