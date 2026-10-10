import React from 'react';
import Link from 'next/link';
import { ShieldCheck, Layers, AlertCircle, FileCheck, Info } from 'lucide-react';
import { EVIDENCE_BADGES } from '@/lib/reports';

export default function DataMethodologyPage() {
  return (
    <div className="flex-1 max-w-4xl w-full mx-auto p-6 md:p-12 space-y-8">
      <div className="border-b border-border pb-6">
        <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-primary-light text-primary text-xs font-semibold mb-3">
          <ShieldCheck className="w-3.5 h-3.5" />
          Scientific Integrity & Transparency
        </div>
        <h1 className="text-3xl font-extrabold text-ink tracking-tight">
          Data Methodology & Evidence Policy
        </h1>
        <p className="text-xs md:text-sm text-muted mt-2 leading-relaxed">
          EcoTwin adheres to rigorous scientific honesty. We distinguish measured historical observations from screening approximations and deterministic calculations, and explicitly report unsimulated indicators as unavailable.
        </p>
      </div>

      {/* Evidence Hierarchy */}
      <section className="space-y-4">
        <h2 className="text-lg font-bold text-ink">Evidence Classification System</h2>
        <p className="text-xs text-muted leading-relaxed">
          Every output metric returned by our simulation engine is classified under one of six unambiguous evidence tiers:
        </p>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {Object.entries(EVIDENCE_BADGES).map(([key, badge]) => (
            <div key={key} className="bg-white border border-border rounded-xl p-4 shadow-sm space-y-2 text-xs">
              <div className="flex items-center justify-between">
                <span className="font-mono text-[11px] font-bold text-slate-700">{key}</span>
                <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full border ${badge.className}`}>
                  {badge.label}
                </span>
              </div>
              <p className="text-muted leading-relaxed">{badge.description}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Explicit Exclusions */}
      <section className="bg-white border border-border rounded-xl p-6 shadow-sm space-y-3 text-xs">
        <h2 className="text-sm font-bold text-ink flex items-center gap-2">
          <AlertCircle className="w-4 h-4 text-amber-600" />
          Scientifically Unsupported Claims Excluded From EcoTwin
        </h2>
        <p className="text-muted leading-relaxed">
          Previous concept illustrations for EcoTwin featured illustrative figures (such as +1.8 °C temperature changes, +28% PM2.5 concentrations, or -35% habitat connectivity). In this production build, those figures are <strong>not hardcoded or simulated</strong> because:
        </p>
        <ul className="list-disc list-inside space-y-1.5 text-slate-700 pl-2">
          <li><strong>Microclimate air temperature (heat_delta):</strong> Requires detailed 3D building canyon geometry, surface albedo, and calibrated boundary-layer physics.</li>
          <li><strong>Street-level PM2.5 dispersion (pm25_delta):</strong> Cannot be accurately predicted solely from tree count without traffic emission matrices and micro-scale CFD.</li>
          <li><strong>Biodiversity and health incidence:</strong> High-uncertainty downstream indicators that cannot be claimed from coarse land-cover reclassifications alone.</li>
        </ul>
        <p className="text-muted pt-2 border-t border-border">
          When requested, these metrics are labeled <code>UNAVAILABLE</code> with actionable scientific rationale.
        </p>
      </section>

      {/* Authoritative Sources */}
      <section className="space-y-3">
        <h2 className="text-lg font-bold text-ink">Data Sources & Licensing</h2>
        <div className="bg-white border border-border rounded-xl p-5 shadow-sm space-y-3 text-xs">
          <div className="flex items-start justify-between pb-2 border-b border-border">
            <div>
              <h3 className="font-bold text-ink">OpenStreetMap (OSM)</h3>
              <p className="text-muted">Building footprints, road network vectors, park boundaries</p>
            </div>
            <span className="text-[11px] font-mono bg-slate-100 px-2 py-0.5 rounded">ODbL 1.0</span>
          </div>

          <div className="flex items-start justify-between pb-2 border-b border-border">
            <div>
              <h3 className="font-bold text-ink">ESA WorldCover 10m 2021</h3>
              <p className="text-muted">Global land cover classification at 10-meter spatial resolution</p>
            </div>
            <span className="text-[11px] font-mono bg-slate-100 px-2 py-0.5 rounded">CC-BY 4.0</span>
          </div>

          <div className="flex items-start justify-between pb-2 border-b border-border">
            <div>
              <h3 className="font-bold text-ink">Open-Meteo Weather API</h3>
              <p className="text-muted">Hourly forecast context, precipitation, temperature, and GHI</p>
            </div>
            <span className="text-[11px] font-mono bg-slate-100 px-2 py-0.5 rounded">Open Access</span>
          </div>

          <div className="flex items-start justify-between">
            <div>
              <h3 className="font-bold text-ink">OpenAQ Sensor Network</h3>
              <p className="text-muted">Direct station measurements of ambient PM2.5 and PM10</p>
            </div>
            <span className="text-[11px] font-mono bg-slate-100 px-2 py-0.5 rounded">Open Data</span>
          </div>
        </div>
      </section>
    </div>
  );
}
