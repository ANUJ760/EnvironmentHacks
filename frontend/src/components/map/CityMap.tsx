'use client';

import React, { useEffect, useMemo, useRef, useState } from 'react';
import type { Map as LibreMap, GeoJSONSource } from 'maplibre-gl';
import type { FeatureCollection, Geometry } from 'geojson';
import { Building2, CloudSun, Focus, Globe2, Layers3, MapPin, Minus, Plus, RotateCcw, Satellite, Wind } from 'lucide-react';
import { cityVisualConfig, createCityStyle, CITY_LAYER_GROUPS, type CityViewMode } from '@/lib/rendering/city-style';
import { useLayerStore } from '@/stores/layerStore';
import { useScenarioStore } from '@/stores/scenarioStore';
import { useRemovalStore } from '@/stores/removalStore';
import { useAir, useLandcover, useWeather } from '@/hooks/useCityData';
import { computeBBoxFromGeometry, isPointInPolygon } from '@/lib/geo';
import { WORLDCOVER_CLASSES } from '@/lib/scenarios';

interface CityMapProps {
  cityId: string;
  citySlug: string;
  cityName: string;
  boundary: Geometry;
  isScenario?: boolean;
}

function setSource(map: LibreMap, name: string, data: FeatureCollection) {
  (map.getSource(name) as GeoJSONSource | undefined)?.setData(data);
}

function applyVisibility(map: LibreMap, layers: ReturnType<typeof useLayerStore.getState>, mode: CityViewMode) {
  for (const [name, ids] of Object.entries(CITY_LAYER_GROUPS)) {
    for (const id of ids) {
      if (map.getLayer(id)) map.setLayoutProperty(id, 'visibility', mode === 'illustrated' && layers[name as keyof typeof CITY_LAYER_GROUPS] ? 'visible' : 'none');
    }
  }
  if (map.getLayer('neighborhoods')) map.setLayoutProperty('neighborhoods', 'visibility', mode === 'illustrated' ? 'visible' : 'none');
  if (map.getLayer('aerial-building-hit')) map.setLayoutProperty('aerial-building-hit', 'visibility', mode === 'imagery' && layers.buildings ? 'visible' : 'none');
  if (map.getLayer('aerial')) {
    map.setPaintProperty('aerial', 'raster-opacity', mode === 'imagery' ? 1 : 0.24);
    map.setPaintProperty('aerial', 'raster-saturation', mode === 'imagery' ? 0 : -0.65);
    map.setPaintProperty('aerial', 'raster-contrast', mode === 'imagery' ? 0 : -0.3);
  }
  if (map.getLayer('air-stations')) map.setLayoutProperty('air-stations', 'visibility', layers.air ? 'visible' : 'none');
}

export function CityMap({ cityId, citySlug, cityName, boundary, isScenario = false }: CityMapProps) {
  const hostRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<LibreMap | null>(null);
  const [readyMap, setReadyMap] = useState<LibreMap | null>(null);
  const [mode, setMode] = useState<CityViewMode>('illustrated');
  const [northUp, setNorthUp] = useState(false);
  const [error, setError] = useState('');
  const [imageryError, setImageryError] = useState(false);
  const [buildingCount, setBuildingCount] = useState(0);
  const [zoom, setZoom] = useState(15.5);
  const [loading, setLoading] = useState(true);
  const [weatherEffects, setWeatherEffects] = useState(true);
  const layers = useLayerStore();
  const { selectedFeature, setSelectedFeature, edits } = useScenarioStore();
  const removalPreview = useRemovalStore(state => state.preview);
  const showingAfter = useRemovalStore(state => state.showingAfter);
  const { data: weather } = useWeather(cityId);
  const { data: landcover } = useLandcover(cityId);
  const { data: air } = useAir(cityId);
  const config = useMemo(() => cityVisualConfig(citySlug, boundary), [citySlug, boundary]);
  const latest = useRef({ layers, mode });
  latest.current = { layers, mode };

  const currentWeather = useMemo(() => {
    const now = Date.now();
    return weather?.series?.reduce((closest, sample) => Math.abs(Date.parse(sample.valid_at) - now) < Math.abs(Date.parse(closest.valid_at) - now) ? sample : closest);
  }, [weather]);
  const precipitation = currentWeather?.rain_mm ?? 0;
  const night = currentWeather?.ghi_w_m2 != null && currentWeather.ghi_w_m2 <= 1;
  const wet = precipitation > 0.1;

  useEffect(() => {
    let disposed = false;
    let observer: ResizeObserver | undefined;
    let countTimer: ReturnType<typeof setTimeout> | undefined;
    let lastHoverAt = 0;
    setLoading(true);
    setReadyMap(null);
    setError('');
    async function initialize() {
      const { Map, AttributionControl, ScaleControl, setWorkerUrl, setWorkerCount } = await import('maplibre-gl');
      if (disposed || !hostRef.current) return;
      setWorkerUrl('/api/map/worker/maplibre-gl-worker.mjs');
      setWorkerCount(2);
      const map = new Map({
        container: hostRef.current,
        style: createCityStyle(config.zurich),
        center: config.center,
        zoom: config.zurich ? 15.5 : 14.5,
        pitch: 0,
        bearing: -24,
        maxPitch: 0,
        pitchWithRotate: false,
        touchPitch: false,
        minZoom: 9,
        maxZoom: 19,
        attributionControl: false,
        canvasContextAttributes: { antialias: false, powerPreference: 'low-power' },
        pixelRatio: Math.min(window.devicePixelRatio || 1, 1.5),
        renderWorldCopies: false,
        fadeDuration: 100,
        maxTileCacheSize: 200,
      });
      mapRef.current = map;
      map.on('styleimagemissing', event => {
        if (event.id !== 'roof-grain' || map.hasImage(event.id)) return;
        const width = 16;
        const data = new Uint8Array(width * width * 4);
        for (let y = 0; y < width; y++) {
          for (let x = 0; x < width; x++) {
            const index = (y * width + x) * 4;
            data[index] = 103; data[index + 1] = 72; data[index + 2] = 43;
            data[index + 3] = y % 4 === 0 || (x + (y % 8 === 0 ? 4 : 0)) % 8 === 0 ? 80 : 0;
          }
        }
        map.addImage(event.id, { width, height: width, data });
      });
      map.addControl(new AttributionControl({ compact: true }), 'bottom-right');
      map.addControl(new ScaleControl({ maxWidth: 100, unit: 'metric' }), 'bottom-right');
      map.getCanvas().setAttribute('aria-label', 'Interactive illustrated city map');
      map.on('error', event => {
        if (disposed) return;
        if ((event as any).sourceId === 'imagery' || /geo.admin/.test(event.error?.message || '')) setImageryError(true);
        else if (!map.isStyleLoaded()) setError('The city tiles could not load. Check your connection and reload the view.');
      });
      map.on('load', () => {
        if (disposed) return;
        setSource(map, 'analysis', { type: 'FeatureCollection', features: [{ type: 'Feature', properties: {}, geometry: boundary }] });
        if (config.treesUrl) (map.getSource('trees') as GeoJSONSource).setData(config.treesUrl);
        applyVisibility(map, latest.current.layers, latest.current.mode);
        setReadyMap(map);
        setLoading(false);
        setError('');
      });
      map.on('idle', () => {
        if (disposed) return;
        clearTimeout(countTimer);
        countTimer = setTimeout(() => {
          if (disposed || !map.getLayer('building-roofs')) return;
          const roofs = map.queryRenderedFeatures(undefined, { layers: ['building-roofs'] });
          setBuildingCount(new Set(roofs.map(feature => feature.id ?? JSON.stringify(feature.geometry))).size);
          setZoom(map.getZoom());
          hostRef.current?.setAttribute('data-rendered-buildings', String(roofs.length));
        }, 120);
      });
      map.on('click', event => {
        const hitLayers = ['tree-canopies', 'building-roofs', 'aerial-building-hit', 'parks', 'water', 'roads', 'air-stations'].filter(id => map.getLayer(id));
        const hit = map.queryRenderedFeatures(event.point, { layers: hitLayers })[0];
        if (!hit) { useRemovalStore.getState().setPreview(null); setSelectedFeature(null); return; }
        const category = hit.layer.id === 'tree-canopies' ? 'mapped_tree' : ['building-roofs', 'aerial-building-hit'].includes(hit.layer.id) ? 'building' : hit.layer.id === 'parks' ? 'park' : hit.layer.id === 'water' ? 'water' : hit.layer.id === 'air-stations' ? 'air_station' : 'road';
        let geometry = hit.geometry;
        if (geometry.type === 'MultiPolygon') {
          const polygon = geometry.coordinates.find(coordinates => isPointInPolygon([event.lngLat.lng, event.lngLat.lat], { type: 'Polygon', coordinates }));
          if (polygon) geometry = { type: 'Polygon', coordinates: polygon };
        }
        useRemovalStore.getState().setPreview(null);
        setSelectedFeature({ type: 'Feature', id: hit.id, geometry, properties: { ...hit.properties, clicked_location: [event.lngLat.lng, event.lngLat.lat], name: hit.properties?.name || (category === 'building' ? 'Mapped building' : category === 'mapped_tree' ? 'Mapped tree' : category), category, source: category === 'air_station' ? 'OpenAQ' : 'OpenStreetMap / OpenFreeMap', within_analysis_area: isPointInPolygon([event.lngLat.lng, event.lngLat.lat], boundary), illustration_note: category === 'building' ? 'Real mapped footprint; roof colors and textures are illustrative.' : undefined } });
      });
      map.on('mousemove', event => {
        const now = performance.now();
        if (now - lastHoverAt < 50 || map.isMoving()) return;
        lastHoverAt = now;
        if (!map.isStyleLoaded()) return;
        const hits = map.queryRenderedFeatures(event.point, { layers: ['tree-canopies', 'building-roofs', 'aerial-building-hit', 'parks', 'roads'].filter(id => map.getLayer(id)) });
        map.getCanvas().style.cursor = hits.length ? 'pointer' : '';
      });
      observer = new ResizeObserver(() => map.resize());
      observer.observe(hostRef.current);
    }
    initialize().catch(err => { if (!disposed) { setLoading(false); setError(`City renderer could not start: ${err.message}`); } });
    return () => {
      disposed = true;
      clearTimeout(countTimer);
      observer?.disconnect();
      mapRef.current?.remove();
      mapRef.current = null;
      useRemovalStore.getState().setPreview(null);
    };
  }, [config, boundary, setSelectedFeature]);

  useEffect(() => { if (readyMap) applyVisibility(readyMap, layers, mode); }, [readyMap, layers, mode]);

  useEffect(() => {
    if (!readyMap) return;
    setSource(readyMap, 'removal', { type: 'FeatureCollection', features: removalPreview && showingAfter ? [{ type: 'Feature', properties: { color: removalPreview.color }, geometry: removalPreview.geometry }] : [] });
  }, [readyMap, removalPreview, showingAfter]);

  useEffect(() => {
    if (!readyMap) return;
    setSource(readyMap, 'selection', { type: 'FeatureCollection', features: selectedFeature?.geometry ? [{ type: 'Feature', properties: {}, geometry: selectedFeature.geometry }] : [] });
  }, [readyMap, selectedFeature]);

  useEffect(() => {
    if (!readyMap) return;
    setSource(readyMap, 'interventions', { type: 'FeatureCollection', features: edits.flatMap((edit, index) => {
      const geometry = edit.edit_type === 'LAND_COVER_RECLASSIFY' ? edit.polygon_geojson : edit.edit_type === 'SOLAR_PV_INSTALL' ? edit.footprint_geojson : null;
      return geometry ? [{ type: 'Feature' as const, id: index, geometry: geometry as Geometry, properties: { color: edit.edit_type === 'LAND_COVER_RECLASSIFY' ? WORLDCOVER_CLASSES[edit.to_class_code]?.color || '#66ad6c' : '#547fa8' } }] : [];
    }) });
  }, [readyMap, edits]);

  useEffect(() => {
    if (!readyMap || !air?.readings) return;
    const stations = new Map(air.readings.map(reading => [reading.station_id, reading]));
    const data: FeatureCollection = { type: 'FeatureCollection', features: [...stations.values()].flatMap(reading => reading.location ? [{ type: 'Feature' as const, geometry: reading.location as unknown as Geometry, properties: { name: reading.station_name, parameter: reading.parameter, value: reading.value, unit: reading.unit } }] : []) };
    if (!readyMap.getSource('air')) {
      readyMap.addSource('air', { type: 'geojson', data });
      readyMap.addLayer({ id: 'air-stations', source: 'air', type: 'circle', paint: { 'circle-radius': 6, 'circle-color': '#5b99af', 'circle-stroke-color': '#fff', 'circle-stroke-width': 2 } });
    } else setSource(readyMap, 'air', data);
    applyVisibility(readyMap, latest.current.layers, latest.current.mode);
  }, [readyMap, air]);

  function flyToStudy() {
    const bbox = computeBBoxFromGeometry(boundary);
    mapRef.current?.fitBounds([[bbox.minLon, bbox.minLat], [bbox.maxLon, bbox.maxLat]], { padding: 70, bearing: northUp ? 0 : -24, duration: 500 });
  }

  function changeMode(next: CityViewMode) {
    setMode(next);
  }

  const canopy = (landcover?.class_percentages as Record<string, number> | undefined)?.['10'];
  return (
    <div className="city-map relative flex-1 min-h-[620px] overflow-hidden bg-[#cadcb5]" data-city-map-ready={!!readyMap} data-view-mode={mode}>
      <div ref={hostRef} style={{ position: 'absolute', inset: 0 }} />
      {layers.weather && weatherEffects && currentWeather && mode === 'illustrated' && (
        <div className={`city-atmosphere pointer-events-none absolute inset-0 ${night ? 'city-atmosphere-night' : ''} ${wet ? 'city-atmosphere-rain' : ''}`} aria-hidden="true" />
      )}

      <div className="absolute top-5 left-5 right-5 z-10 flex items-start justify-between gap-3 pointer-events-none">
        <div className="city-map-panel pointer-events-auto rounded-2xl p-4 max-w-[290px]">
          <div className="flex items-center gap-2 text-[10px] uppercase font-bold tracking-[0.18em] text-[#6f8265]"><span className="w-1.5 h-1.5 rounded-full bg-[#51976c]" /> A living city, illustrated</div>
          <h2 className="mt-1 text-xl font-bold tracking-tight text-[#344732]">{config.zurich ? 'Zurich' : cityName}</h2>
          <p className="mt-1 text-[11px] leading-relaxed text-[#7a826b]">{config.zurich ? 'Explore the whole city, one neighborhood at a time.' : 'Explore real city footprints in a new perspective.'}</p>
          <div className="flex gap-1 mt-3 bg-[#eeeede] rounded-xl p-1">
            <button onClick={() => changeMode('illustrated')} aria-pressed={mode === 'illustrated'} className={`flex-1 city-view-button ${mode === 'illustrated' ? 'city-view-button-active' : ''}`}><Layers3 size={13} /> Illustrated 2D</button>
            {config.zurich && <button onClick={() => changeMode('imagery')} aria-pressed={mode === 'imagery'} className={`flex-1 city-view-button ${mode === 'imagery' ? 'city-view-button-active' : ''}`}><Satellite size={13} /> Aerial</button>}
          </div>
        </div>
        {layers.weather && <div className="city-map-panel pointer-events-auto rounded-2xl p-3 w-[170px]">
          <div className="flex items-center justify-between"><CloudSun size={21} className="text-[#d3a95c]" /><span className="text-xl font-semibold text-[#344732]">{currentWeather?.temperature_c != null ? `${Math.round(currentWeather.temperature_c)}°` : '—'}</span></div>
          <p className="mt-1 text-[11px] font-semibold text-[#5a6e4e]">{currentWeather ? wet ? 'Rainy skies' : night ? 'Evening light' : 'Daylight' : 'Weather unavailable'}</p>
          {currentWeather && <><div className="mt-2 flex gap-3 text-[10px] text-[#7c8670]"><span className="flex items-center gap-1"><Wind size={11} />{currentWeather.wind_mps?.toFixed(1) ?? '—'} m/s</span><span>{precipitation.toFixed(1)} mm</span></div><p className="text-[9px] text-[#8b927d] mt-2">Pinned forecast · {new Date(currentWeather.valid_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}{weather?.stale ? ' · stale' : ''}</p></>}
          <button onClick={() => setWeatherEffects(!weatherEffects)} className="mt-2 text-[10px] text-[#5a785b] underline underline-offset-2" aria-pressed={weatherEffects}>Atmosphere {weatherEffects ? 'on' : 'off'}</button>
        </div>}
      </div>

      <div className="absolute left-5 top-[205px] z-10 city-map-panel rounded-2xl p-1.5 flex flex-col gap-1" role="toolbar" aria-label="City map navigation">
        <button className="city-nav-button" aria-label="Zoom in" title="Zoom in" onClick={() => mapRef.current?.zoomIn({ duration: 250 })}><Plus size={17} /></button>
        <button className="city-nav-button" aria-label="Zoom out" title="Zoom out" onClick={() => mapRef.current?.zoomOut({ duration: 250 })}><Minus size={17} /></button>
        <span className="h-px bg-[#e1e5d5] mx-2" />
        <button className="city-nav-button" aria-label="View entire city" title="View entire city" onClick={() => mapRef.current?.fitBounds([[config.bounds[0], config.bounds[1]], [config.bounds[2], config.bounds[3]]], { padding: 70, pitch: 0, bearing: 0, duration: 800 })}><Globe2 size={17} /></button>
        <button className="city-nav-button" aria-label="View analysis area" title="View analysis area" onClick={flyToStudy}><Focus size={17} /></button>
        <button className="city-nav-button" aria-label="Toggle north-up orientation" title="Toggle north-up orientation" onClick={() => { setNorthUp(!northUp); mapRef.current?.easeTo({ bearing: northUp ? -24 : 0, duration: 300 }); }}><Layers3 size={17} /></button>
        <button className="city-nav-button" aria-label="Reset city view" title="Return downtown" onClick={() => { setNorthUp(false); mapRef.current?.flyTo({ center: config.center, zoom: 15.5, bearing: -24, pitch: 0, duration: 600 }); }}><RotateCcw size={16} /></button>
      </div>

      <div className="absolute bottom-6 left-5 z-10 city-map-panel rounded-2xl px-4 py-3 text-[11px] max-w-[330px]">
        <div className="flex items-center gap-2 text-[#5a6f51] font-semibold"><MapPin size={13} /> {isScenario ? 'Scenario workspace' : 'Real geography. Playful perspective.'}</div>
        <p className="text-[10px] text-[#8a917c] mt-1">Drag to explore · scroll to zoom · click a building to inspect</p>
        <p className="text-[10px] text-[#5d7953] mt-1">Click trees, parks or roads to explore removal consequences.</p>
        <div className="flex gap-4 mt-2.5 pt-2.5 border-t border-[#e5e7d8] text-[#6f7e61]"><span className="flex items-center gap-1.5"><Building2 size={12} />{mode === 'imagery' ? 'Aerial imagery' : `${buildingCount.toLocaleString()} visible buildings`}</span>{layers.landcover && canopy != null && <span>{canopy.toFixed(0)}% study-area tree cover</span>}</div>
        <p className="text-[9px] mt-2 text-[#959b87]">Dashed outline: verified analysis area. Forecast and WorldCover apply there. Roof colors and textures are illustrative.</p>
      </div>
      {zoom < 13 && mode === 'illustrated' && <div className="absolute bottom-6 left-1/2 -translate-x-1/2 z-10 city-map-panel px-3 py-2 rounded-xl text-[11px] text-[#5d7150]">Zoom in to explore buildings and street details</div>}
      {(loading || error || (imageryError && mode === 'imagery')) && <div role="status" className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 z-20 city-map-panel rounded-2xl px-5 py-4 max-w-sm text-sm text-[#5a6f51]">{error || (imageryError && mode === 'imagery' ? 'Aerial imagery is temporarily unavailable. Illustrated 2D remains available.' : <span className="flex items-center gap-3"><span className="w-4 h-4 rounded-full border-2 border-[#a5b996] border-t-[#538169] animate-spin" /> Bringing the city into view…</span>)}</div>}
    </div>
  );
}
