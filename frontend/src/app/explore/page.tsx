'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import { Search, MapPin, Eye, Play, Sparkles, AlertCircle, Database } from 'lucide-react';
import { useCities } from '@/hooks/useCities';
import { getHumanErrorMessage } from '@/lib/api/problem';

export default function ExplorePage() {
  const [searchTerm, setSearchTerm] = useState('');
  const { data: cities, isLoading, isError, error } = useCities();

  const filteredCities = (cities || []).filter((c) => {
    if (!searchTerm) return true;
    const name = c.display_name.toLowerCase();
    const slug = c.slug.toLowerCase();
    const term = searchTerm.toLowerCase();
    return name.includes(term) || slug.includes(term);
  });

  return (
    <div className="flex-1 max-w-6xl w-full mx-auto p-6 md:p-8 space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-border pb-6">
        <div>
          <h1 className="text-2xl font-bold text-ink tracking-tight">Explore City Study Areas</h1>
          <p className="text-xs md:text-sm text-muted mt-1">
            Select an officially registered city dataset snapshot to explore geographic features or launch scenario simulations.
          </p>
        </div>

        {/* Search */}
        <div className="relative w-full md:w-72">
          <Search className="w-4 h-4 text-muted absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="search"
            placeholder="Search registered cities..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full text-xs pl-9 pr-3 py-2 bg-white border border-border rounded-lg focus:outline-none focus:ring-2 focus:ring-primary shadow-xs"
            aria-label="Search cities"
          />
        </div>
      </div>

      {/* Loading & Error States */}
      {isLoading && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 animate-pulse">
          {[1, 2, 3].map((n) => (
            <div key={n} className="h-48 rounded-xl bg-slate-200/60" />
          ))}
        </div>
      )}

      {isError && (
        <div className="p-6 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 space-y-2">
          <div className="flex items-center gap-2 font-bold text-sm">
            <AlertCircle className="w-4 h-4" />
            <span>Failed to load city directory</span>
          </div>
          <p className="text-xs">{getHumanErrorMessage(error)}</p>
          <p className="text-[11px] text-rose-700">
            Check that the backend API is running and reachable at your configured API URL.
          </p>
        </div>
      )}

      {/* Empty State */}
      {!isLoading && !isError && filteredCities.length === 0 && (
        <div className="bg-white border border-dashed border-border rounded-2xl p-10 text-center space-y-4 max-w-lg mx-auto my-8">
          <div className="w-12 h-12 rounded-full bg-slate-100 text-slate-500 flex items-center justify-center mx-auto">
            <Database className="w-6 h-6" />
          </div>
          <div>
            <h3 className="font-bold text-sm text-ink">No Registered Cities Available</h3>
            <p className="text-xs text-muted mt-1 leading-relaxed">
              No city study area datasets have been ingested into the local PostGIS database yet.
            </p>
          </div>
          <div className="bg-slate-50 border border-border rounded-lg p-3 text-left font-mono text-[11px] text-slate-700">
            <p className="text-muted text-[10px] uppercase font-sans font-semibold mb-1">
              Backend Ingestion Command:
            </p>
            <code>docker compose run --rm ingest ecotwin ingest osm --city &lt;name&gt; ...</code>
          </div>
        </div>
      )}

      {/* City Directory Grid */}
      {!isLoading && !isError && filteredCities.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {filteredCities.map((city) => (
            <div
              key={city.id}
              className="bg-white border border-border rounded-xl p-5 shadow-sm hover:shadow-md transition-shadow flex flex-col justify-between space-y-4"
            >
              <div>
                <div className="flex items-start justify-between gap-2 mb-2">
                  <div className="truncate">
                    <h2 className="font-bold text-base text-ink truncate">{city.display_name}</h2>
                    <p className="text-xs text-muted font-mono truncate">{city.slug}</p>
                  </div>
                  <span
                    className={`text-[10px] font-semibold px-2 py-0.5 rounded-full uppercase shrink-0 ${
                      city.status === 'READY'
                        ? 'bg-emerald-100 text-emerald-800'
                        : 'bg-amber-100 text-amber-800'
                    }`}
                  >
                    {city.status}
                  </span>
                </div>

                <div className="space-y-1.5 text-xs text-muted mt-3 pt-3 border-t border-border">
                  <div className="flex justify-between">
                    <span>CRS (SRID):</span>
                    <span className="font-mono font-medium text-ink">EPSG:{city.analysis_srid}</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Timezone:</span>
                    <span className="font-medium text-ink">{city.timezone}</span>
                  </div>
                </div>

                {/* Capabilities */}
                <div className="mt-3">
                  <span className="text-[10px] font-semibold uppercase text-muted block mb-1">
                    Available Data Products
                  </span>
                  <div className="flex flex-wrap gap-1">
                    {city.capabilities?.map((cap) => (
                      <span
                        key={cap}
                        className="text-[10px] bg-slate-100 text-slate-700 px-1.5 py-0.5 rounded font-mono"
                      >
                        {cap}
                      </span>
                    ))}
                  </div>
                </div>
              </div>

              {/* Action Buttons */}
              <div className="flex items-center gap-2 pt-2 border-t border-border">
                <Link
                  href={`/city/${city.id}`}
                  className="flex-1 flex items-center justify-center gap-1.5 bg-slate-100 hover:bg-slate-200 text-ink text-xs font-semibold py-2 px-3 rounded-lg transition-colors"
                >
                  <Eye className="w-3.5 h-3.5" />
                  View Map
                </Link>
                <Link
                  href={`/city/${city.id}/simulate`}
                  className="flex-1 flex items-center justify-center gap-1.5 bg-primary hover:bg-primary-hover text-white text-xs font-semibold py-2 px-3 rounded-lg transition-colors shadow-xs"
                >
                  <Play className="w-3.5 h-3.5 fill-current" />
                  Simulate Lab
                </Link>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
