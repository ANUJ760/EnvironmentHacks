'use client';

import React, { useState, use } from 'react';
import Link from 'next/link';
import { useCity } from '@/hooks/useCities';
import { useCityFeatures } from '@/hooks/useCityData';
import { PixiMap } from '@/components/map/PixiMap';
import { LeftRail } from '@/components/shell/LeftRail';
import { RightInspector } from '@/components/shell/RightInspector';
import { computeBBoxFromGeometry, formatBBox } from '@/lib/geo';
import { ArrowLeft, Play, AlertCircle } from 'lucide-react';

export default function CityViewerPage({ params }: { params: Promise<{ cityId: string }> }) {
  const { cityId } = use(params);
  const { data: city, isLoading, isError } = useCity(cityId);

  // Viewport BBox state
  const [currentBbox, setCurrentBbox] = useState<string>('');

  // Initial bbox from boundary
  const defaultBbox = city?.boundary ? formatBBox(computeBBoxFromGeometry(city.boundary)) : '';
  const effectiveBbox = currentBbox || defaultBbox;

  // Features query
  const { data: featureCollection } = useCityFeatures(cityId, effectiveBbox);
  const features = featureCollection?.features || [];

  if (isLoading) {
    return (
      <div className="flex-1 flex items-center justify-center bg-background">
        <div className="text-center space-y-2">
          <div className="w-8 h-8 border-2 border-primary border-t-transparent rounded-full animate-spin mx-auto" />
          <p className="text-xs text-muted">Loading city spatial metadata...</p>
        </div>
      </div>
    );
  }

  if (isError || !city) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center p-6 text-center">
        <AlertCircle className="w-8 h-8 text-rose-600 mb-2" />
        <h2 className="text-lg font-bold text-ink mb-1">City Not Found</h2>
        <p className="text-xs text-muted mb-4">The requested city study area does not exist or failed to load.</p>
        <Link
          href="/explore"
          className="flex items-center gap-1.5 bg-primary text-white text-xs font-semibold px-4 py-2 rounded-lg"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          Back to City Directory
        </Link>
      </div>
    );
  }

  return (
    <div className="flex-1 flex overflow-hidden">
      {/* Left Layer Rail */}
      <LeftRail cityId={cityId} cityName={city.display_name} />

      {/* Main Map Viewport */}
      <div className="flex-1 flex flex-col relative overflow-hidden">
        <PixiMap
          cityId={cityId}
          boundary={city.boundary}
          features={features}
          onBBoxChange={(bbox) => setCurrentBbox(bbox)}
        />
      </div>

      {/* Right Inspector Rail */}
      <RightInspector cityId={cityId} />
    </div>
  );
}
