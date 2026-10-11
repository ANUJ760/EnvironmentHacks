'use client';

import React, { useEffect, useState } from 'react';
import { Activity, Server, CheckCircle2, XCircle, RefreshCw } from 'lucide-react';

interface HealthData {
  status: string;
  version: string;
  timestamp: string;
  backend?: {
    status: string;
    ready: boolean;
  };
}

export default function StatusPage() {
  const [frontendHealth, setFrontendHealth] = useState<HealthData | null>(null);
  const [readyzStatus, setReadyzStatus] = useState<string>('checking');
  const [loading, setLoading] = useState(true);

  const checkStatus = async () => {
    setLoading(true);
    try {
      const res = await fetch('/api/health');
      const data = await res.json();
      setFrontendHealth(data);
    } catch {
      setFrontendHealth(null);
    }

    try {
      const res = await fetch('/api/gateway/readyz');
      setReadyzStatus(res.ok ? 'connected' : `status_${res.status}`);
    } catch {
      setReadyzStatus('unreachable');
    }
    setLoading(false);
  };

  useEffect(() => {
    checkStatus();
  }, []);

  return (
    <div className="flex-1 max-w-3xl w-full mx-auto p-6 md:p-12 space-y-6">
      <div className="flex items-center justify-between border-b border-border pb-4">
        <div>
          <h1 className="text-2xl font-bold text-ink">System Connectivity Status</h1>
          <p className="text-xs text-muted mt-1">
            Real-time health verification for the Next.js BFF server and the backend FastAPI service.
          </p>
        </div>
        <button
          type="button"
          onClick={checkStatus}
          disabled={loading}
          className="flex items-center gap-1.5 text-xs font-semibold px-3 py-1.5 rounded-lg border border-border hover:bg-slate-50 transition-colors"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          Refresh Status
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Frontend Health */}
        <div className="bg-white border border-border rounded-xl p-5 shadow-sm space-y-3 text-xs">
          <div className="flex items-center justify-between">
            <h2 className="font-bold text-sm text-ink flex items-center gap-2">
              <Activity className="w-4 h-4 text-primary" />
              Frontend Web Server
            </h2>
            {frontendHealth ? (
              <span className="flex items-center gap-1 text-[11px] font-semibold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-full">
                <CheckCircle2 className="w-3.5 h-3.5" /> Healthy
              </span>
            ) : (
              <span className="flex items-center gap-1 text-[11px] font-semibold text-rose-700 bg-rose-50 px-2 py-0.5 rounded-full">
                <XCircle className="w-3.5 h-3.5" /> Offline
              </span>
            )}
          </div>

          <div className="bg-slate-50 border border-border rounded-lg p-3 space-y-1 text-slate-700">
            <div className="flex justify-between">
              <span>Endpoint:</span>
              <span className="font-mono">/api/health</span>
            </div>
            <div className="flex justify-between">
              <span>Application Version:</span>
              <span className="font-mono">{frontendHealth?.version || '0.2.0'}</span>
            </div>
            <div className="flex justify-between">
              <span>Server Timestamp:</span>
              <span className="text-[10px] text-muted">{frontendHealth?.timestamp || 'N/A'}</span>
            </div>
          </div>
        </div>

        {/* Backend Connectivity */}
        <div className="bg-white border border-border rounded-xl p-5 shadow-sm space-y-3 text-xs">
          <div className="flex items-center justify-between">
            <h2 className="font-bold text-sm text-ink flex items-center gap-2">
              <Server className="w-4 h-4 text-primary" />
              Backend FastAPI Gateway
            </h2>
            {readyzStatus === 'connected' ? (
              <span className="flex items-center gap-1 text-[11px] font-semibold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-full">
                <CheckCircle2 className="w-3.5 h-3.5" /> Ready
              </span>
            ) : (
              <span className="flex items-center gap-1 text-[11px] font-semibold text-rose-700 bg-rose-50 px-2 py-0.5 rounded-full">
                <XCircle className="w-3.5 h-3.5" /> {readyzStatus}
              </span>
            )}
          </div>

          <div className="bg-slate-50 border border-border rounded-lg p-3 space-y-1 text-slate-700">
            <div className="flex justify-between">
              <span>Target Route:</span>
              <span className="font-mono">/readyz</span>
            </div>
            <div className="flex justify-between">
              <span>Gateway Proxy:</span>
              <span className="font-mono">/api/gateway/readyz</span>
            </div>
            <div className="flex justify-between">
              <span>Backend Readiness:</span>
              <span className="font-semibold text-ink">{readyzStatus}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
