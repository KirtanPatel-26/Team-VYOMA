/**
 * Anomaly Dashboard Master Container
 * Next.js / React component coordinating all 8 operational views with Supabase Realtime
 */

'use client';

import React, { useState } from 'react';
import { useAnomalyRealtime } from '../../hooks/useAnomalyRealtime';
import { SeverityStats } from './SeverityStats';
import { ActiveAlertsView } from './ActiveAlertsView';
import { SecurityCenter } from './SecurityCenter';
import { InventoryAnomalies } from './InventoryAnomalies';
import { QueueAnalytics } from './QueueAnalytics';
import { AlertTimeline } from './AlertTimeline';
import { AlertHistory } from './AlertHistory';
import { LiveNotificationToast } from './LiveNotificationToast';

export type DashboardTab =
  | 'active'
  | 'security'
  | 'inventory'
  | 'queue'
  | 'timeline'
  | 'history';

export const AnomalyDashboardContainer: React.FC = () => {
  const [activeTab, setActiveTab] = useState<DashboardTab>('active');
  const {
    anomalies,
    latestAlert,
    unreadCount,
    soundEnabled,
    setSoundEnabled,
    acknowledgeAnomaly,
    resolveAnomaly,
    loading,
  } = useAnomalyRealtime();

  const tabs: { id: DashboardTab; label: string; icon: string; count?: number }[] = [
    { id: 'active', label: 'Active Alerts', icon: '🚨', count: unreadCount },
    { id: 'security', label: 'Security Center', icon: '🛡️' },
    { id: 'inventory', label: 'Inventory Anomalies', icon: '📦' },
    { id: 'queue', label: 'Queue Analytics', icon: '👥' },
    { id: 'timeline', label: 'Alert Timeline', icon: '⏱️' },
    { id: 'history', label: 'Alert History', icon: '📜' },
  ];

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 p-4 md:p-8 font-sans">
      {/* Top Header */}
      <header className="flex flex-wrap items-center justify-between gap-4 pb-6 border-b border-slate-800 mb-6">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-black tracking-tight text-white">
              AI Anomaly & Trigger Engine
            </h1>
            <span className="flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
              <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse"></span>
              Realtime Active
            </span>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            Autonomous multi-modal monitoring: Computer Vision, POS registers, and Warehouse shelf telemetry.
          </p>
        </div>

        {/* Global Controls */}
        <div className="flex items-center gap-3">
          <button
            onClick={() => setSoundEnabled(!soundEnabled)}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold border transition-colors flex items-center gap-2 ${
              soundEnabled
                ? 'bg-indigo-600/20 text-indigo-300 border-indigo-500/40'
                : 'bg-slate-800 text-slate-400 border-slate-700'
            }`}
          >
            <span>{soundEnabled ? '🔊' : '🔇'}</span>
            <span>{soundEnabled ? 'Alarm On' : 'Muted'}</span>
          </button>
        </div>
      </header>

      {/* Severity Metric Cards */}
      <SeverityStats anomalies={anomalies} />

      {/* Tab Navigation */}
      <nav className="flex items-center gap-2 overflow-x-auto pb-2 mb-6 border-b border-slate-800">
        {tabs.map((tab) => {
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`px-4 py-2.5 rounded-xl text-xs font-bold transition-all flex items-center gap-2 whitespace-nowrap ${
                isActive
                  ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-600/25'
                  : 'bg-slate-900/60 text-slate-400 hover:text-white hover:bg-slate-800'
              }`}
            >
              <span>{tab.icon}</span>
              <span>{tab.label}</span>
              {tab.count !== undefined && tab.count > 0 && (
                <span className="ml-1.5 px-2 py-0.5 rounded-full text-[10px] font-extrabold bg-red-500 text-white animate-pulse">
                  {tab.count}
                </span>
              )}
            </button>
          );
        })}
      </nav>

      {/* Main Tab Content */}
      <main>
        {loading && anomalies.length === 0 ? (
          <div className="p-12 text-center text-xs text-slate-500">
            Connecting to Supabase Realtime mesh...
          </div>
        ) : (
          <>
            {activeTab === 'active' && (
              <ActiveAlertsView
                anomalies={anomalies}
                onAcknowledge={acknowledgeAnomaly}
                onResolve={resolveAnomaly}
              />
            )}
            {activeTab === 'security' && <SecurityCenter anomalies={anomalies} />}
            {activeTab === 'inventory' && <InventoryAnomalies anomalies={anomalies} />}
            {activeTab === 'queue' && <QueueAnalytics anomalies={anomalies} />}
            {activeTab === 'timeline' && <AlertTimeline anomalies={anomalies} />}
            {activeTab === 'history' && <AlertHistory anomalies={anomalies} />}
          </>
        )}
      </main>

      {/* Live Toast Notifications */}
      <LiveNotificationToast
        latestAlert={latestAlert}
        soundEnabled={soundEnabled}
        onToggleSound={() => setSoundEnabled(!soundEnabled)}
      />
    </div>
  );
};
