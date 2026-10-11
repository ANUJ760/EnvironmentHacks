import Link from 'next/link';
import { ArrowRight, Globe, Layers, Cpu, ShieldCheck, Sun, Droplets } from 'lucide-react';

export default function HomePage() {
  return (
    <div className="flex-1 flex flex-col">
      {/* Hero Section */}
      <section className="py-16 md:py-24 px-6 max-w-5xl mx-auto text-center">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-primary-light text-primary text-xs font-semibold mb-6">
          <ShieldCheck className="w-4 h-4" />
          <span>Evidence-Backed Urban Environmental Simulation</span>
        </div>

        <h1 className="text-3xl md:text-5xl font-extrabold text-ink tracking-tight leading-tight mb-6">
          Explore City Boundaries. <br className="hidden md:inline" />
          Stage Interventions. <br className="hidden md:inline" />
          Simulate Real Scientific Trade-Offs.
        </h1>

        <p className="text-sm md:text-base text-muted max-w-2xl mx-auto mb-8 leading-relaxed">
          EcoTwin maps real urban geography from OpenStreetMap and ESA WorldCover satellites, allowing planners to test land-cover conversions and solar installations with verified formulas and transparent evidence provenance.
        </p>

        <div className="flex flex-col sm:flex-row items-center justify-center gap-3">
          <Link
            href="/explore"
            className="w-full sm:w-auto flex items-center justify-center gap-2 bg-primary hover:bg-primary-hover text-white text-sm font-bold py-3 px-6 rounded-xl shadow-sm transition-colors"
          >
            <span>Explore Registered Cities</span>
            <ArrowRight className="w-4 h-4" />
          </Link>
          <Link
            href="/data-methodology"
            className="w-full sm:w-auto flex items-center justify-center gap-2 bg-white hover:bg-slate-50 border border-border text-ink text-sm font-semibold py-3 px-6 rounded-xl transition-colors"
          >
            <span>Data Methodology & Policy</span>
          </Link>
        </div>
      </section>

      {/* Feature Highlights */}
      <section className="border-t border-border bg-white py-14 px-6">
        <div className="max-w-5xl mx-auto">
          <h2 className="text-xs font-bold uppercase tracking-widest text-primary text-center mb-2">
            Core Scientific Capabilities
          </h2>
          <p className="text-lg md:text-xl font-bold text-ink text-center mb-10">
            Built on Authoritative Data, Not Imagined Numbers
          </p>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="p-5 rounded-xl border border-border bg-slate-50 space-y-2.5">
              <div className="w-9 h-9 rounded-lg bg-emerald-100 text-emerald-800 flex items-center justify-center">
                <Layers className="w-5 h-5" />
              </div>
              <h3 className="font-bold text-sm text-ink">WorldCover & OSM Geometry</h3>
              <p className="text-xs text-muted leading-relaxed">
                Uses 10-meter ESA WorldCover classifications and official OpenStreetMap vector features mapped to metric analysis coordinate reference systems.
              </p>
            </div>

            <div className="p-5 rounded-xl border border-border bg-slate-50 space-y-2.5">
              <div className="w-9 h-9 rounded-lg bg-blue-100 text-blue-800 flex items-center justify-center">
                <Droplets className="w-5 h-5" />
              </div>
              <h3 className="font-bold text-sm text-ink">Runoff Volume Screening</h3>
              <p className="text-xs text-muted leading-relaxed">
                Computes stormwater runoff volume differences (m³/event) following land-cover conversions under customizable design rainfall events.
              </p>
            </div>

            <div className="p-5 rounded-xl border border-border bg-slate-50 space-y-2.5">
              <div className="w-9 h-9 rounded-lg bg-amber-100 text-amber-800 flex items-center justify-center">
                <Sun className="w-5 h-5" />
              </div>
              <h3 className="font-bold text-sm text-ink">Indicative Solar Potential</h3>
              <p className="text-xs text-muted leading-relaxed">
                Evaluates rooftop and ground PV installations against hourly global horizontal irradiance with explicit performance ratio assumptions.
              </p>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
