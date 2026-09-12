/**
 * Live Notification Toast Component
 * Floating non-intrusive alert popup with sound indicator and quick view
 */

'use client';

import React, { useState, useEffect } from 'react';
import { Anomaly } from '../../types/anomaly';

interface LiveNotificationToastProps {
  latestAlert: Anomaly | null;
  soundEnabled: boolean;
  onToggleSound: () => void;
}

export const LiveNotificationToast: React.FC<LiveNotificationToastProps> = ({
  latestAlert,
  soundEnabled,
  onToggleSound,
}) => {
  const [visible, setVisible] = useState<boolean>(false);
  const [current, setCurrent] = useState<Anomaly | null>(null);

  useEffect(() => {
    if (latestAlert) {
      setCurrent(latestAlert);
      setVisible(true);

      const timer = setTimeout(() => {
        setVisible(false);
      }, 7000); // 7s auto-dismiss

      return () => clearTimeout(timer);
    }
  }, [latestAlert]);

  if (!visible || !current) return null;

  const isCritical = current.severity === 'Critical';

  return (
    <div className="fixed bottom-5 right-5 z-50 max-w-sm w-full animate-bounce-short">
      <div
        className={`bg-slate-900 border ${
          isCritical ? 'border-red-500 shadow-red-500/20' : 'border-indigo-500 shadow-indigo-500/20'
        } shadow-2xl rounded-2xl p-4 text-white backdrop-blur-lg flex items-start gap-3`}
      >
        <div
          className={`h-10 w-10 rounded-xl flex items-center justify-center font-bold text-lg ${
            isCritical ? 'bg-red-500/20 text-red-400' : 'bg-indigo-500/20 text-indigo-400'
          }`}
        >
          {isCritical ? '🚨' : '🔔'}
        </div>

        <div className="flex-1">
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
              {current.anomaly_type.replace(/_/g, ' ')}
            </span>
            <button
              onClick={() => setVisible(false)}
              className="text-slate-400 hover:text-white text-sm"
            >
              ✕
            </button>
          </div>
          <h4 className="text-xs font-bold mt-1 text-white">{current.description}</h4>
          <p className="text-[10px] text-slate-400 mt-1">
            Zone: {current.zone_id} • Camera: {current.camera_id}
          </p>
        </div>
      </div>
    </div>
  );
};
