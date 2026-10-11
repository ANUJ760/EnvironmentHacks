'use client';

import React from 'react';
import type { ResultView } from '@/hooks/useResult';
import { ShieldCheck, AlertTriangle, Cpu, Hash } from 'lucide-react';

interface EvidenceProvenanceCardProps {
  result: ResultView;
}

export function EvidenceProvenanceCard({ result }: EvidenceProvenanceCardProps) {
  return (
    <div className="bg-white border border-border rounded-xl p-5 shadow-sm space-y-4 text-xs">
      <div className="flex items-center justify-between border-b border-border pb-3">
        <h3 className="font-bold text-sm text-ink flex items-center gap-2">
          <ShieldCheck className="w-4 h-4 text-primary" />
          Evidence Provenance & Verification
        </h3>
        <span className="font-mono text-[11px] bg-slate-100 text-slate-700 px-2 py-0.5 rounded">
          Report Schema v{result.report_schema_version}
        </span>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Hashes & Digests */}
        <div className="space-y-2 bg-slate-50 border border-border rounded-lg p-3">
          <div className="font-semibold text-ink flex items-center gap-1.5 mb-1">
            <Hash className="w-3.5 h-3.5 text-muted" />
            Cryptographic Integrity Digests
          </div>
          <div>
            <span className="text-[10px] text-muted block">Input Digest (SHA-256)</span>
            <span className="font-mono text-[11px] text-ink break-all select-all">
              {result.input_digest}
            </span>
          </div>
          <div>
            <span className="text-[10px] text-muted block">Output Digest (SHA-256)</span>
            <span className="font-mono text-[11px] text-ink break-all select-all">
              {result.output_digest}
            </span>
          </div>
        </div>

        {/* Models Used */}
        <div className="space-y-2 bg-slate-50 border border-border rounded-lg p-3">
          <div className="font-semibold text-ink flex items-center gap-1.5 mb-1">
            <Cpu className="w-3.5 h-3.5 text-muted" />
            Executed Scientific Engines
          </div>
          <div className="space-y-1">
            {Object.entries(result.model_versions || {}).map(([model, version]) => (
              <div key={model} className="flex justify-between items-center text-[11px]">
                <span className="font-medium text-ink">{model}</span>
                <span className="font-mono text-[10px] bg-white border border-border px-1.5 py-0.5 rounded text-muted">
                  v{version}
                </span>
              </div>
            ))}
          </div>
          <div className="pt-2 border-t border-border/60 text-[10px] text-muted">
            Created: {new Date(result.created_at).toLocaleString()}
          </div>
        </div>
      </div>

      {/* Warnings if any */}
      {result.warnings && result.warnings.length > 0 && (
        <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 text-amber-800 space-y-1">
          <div className="font-semibold flex items-center gap-1.5 text-xs">
            <AlertTriangle className="w-3.5 h-3.5 text-amber-600" />
            Execution Warnings & Domain Cautions
          </div>
          <ul className="list-disc list-inside space-y-0.5 text-[11px]">
            {result.warnings.map((w, idx) => (
              <li key={idx}>{w}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
