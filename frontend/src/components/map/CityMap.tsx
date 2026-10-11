'use client';

import React, { useEffect, useMemo, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import type { Map as LibreMap, GeoJSONSource } from 'maplibre-gl';
import type { FeatureCollection, Geometry } from 'geojson';
import { Building2, Check, CloudSun, Focus, Globe2, Layers3, MapPin, Minus, Plus, RotateCcw, Satellite, Scan, Wind, X } from 'lucide-react';
import { cityVisualConfig, createCityStyle, CITY_LAYER_GROUPS, type CityViewMode } from '@/lib/rendering/city-style';
import { useLayerStore } from '@/stores/layerStore';
import { useScenarioStore } from '@/stores/scenarioStore';
import { useRemovalStore } from '@/stores/removalStore';
import { usePlanningStore } from '@/stores/planningStore';
import { useAir, useWeather } from '@/hooks/useCityData';
import { computeBBoxFromGeometry, isPointInPolygon } from '@/lib/geo';
import { WORLDCOVER_CLASSES } from '@/lib/scenarios';
import { fetchGateway } from '@/lib/api/browser-client';
import { nearestTree } from '@/lib/rendering/tree-picking';

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
  for (const id of ['tree-canopies', 'tree-light', 'tree-clusters']) if (map.getLayer(id)) map.setLayoutProperty(id, 'visibility', layers.parks ? 'visible' : 'none');
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
  const { drawing, points, setDrawing, resetDrawing } = usePlanningStore();
  const { data: pinnedWeather } = useWeather(cityId);
  const { data: environment } = useQuery<{ weather: NonNullable<typeof pinnedWeather> & { source: string } }>({
    queryKey: ['environment-baseline', cityId], queryFn: async ({ signal }) => (await fetchGateway<{ weather: NonNullable<typeof pinnedWeather> & { source: string } }>(`/api/gateway/v1/cities/${cityId}/environment-baseline`, { signal })).data,
    staleTime: 300000, refetchInterval: 300000, retry: 1,
  });
  const weather = environment?.weather.series.length ? environment.weather : pinnedWeather;
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
      // Initialize when the style is ready; optional aerial tiles must not block
      // selection or local tree data while a remote image request is slow.
      map.on('style.load', () => {
        if (disposed) return;
        setSource(map, 'analysis', { type: 'FeatureCollection', features: [{ type: 'Feature', properties: {}, geometry: boundary }] });
        if (config.treesUrl) (map.getSource('trees') as GeoJSONSource).setData(config.treesUrl);
        applyVisibility(map, latest.current.layers, latest.current.mode);
        setReadyMap(map);
        setLoading(false);
        setError('');
      });
      const refreshCounts = () => {
        if (disposed) return;
        clearTimeout(countTimer);
        countTimer = setTimeout(() => {
          if (disposed || !map.getLayer('building-roofs')) return;
          const roofs = map.queryRenderedFeatures(undefined, { layers: ['building-roofs'] });
          setBuildingCount(new Set(roofs.map(feature => feature.id ?? JSON.stringify(feature.geometry))).size);
          setZoom(map.getZoom());
          hostRef.current?.setAttribute('data-rendered-buildings', String(roofs.length));
          const trees = map.queryRenderedFeatures(undefined, { layers: ['tree-canopies'] });
          hostRef.current?.setAttribute('data-rendered-trees', String(trees.length));
          hostRef.current?.setAttribute('data-tree-targets', JSON.stringify(trees.filter(tree => tree.geometry.type === 'Point').map(tree => {
            const pixel = map.project(tree.geometry.type === 'Point' ? tree.geometry.coordinates as [number, number] : config.center);
            return { x: pixel.x, y: pixel.y };
          }).filter(pixel => pixel.x > map.getCanvas().clientWidth * .35 && pixel.x < map.getCanvas().clientWidth * .75 && pixel.y > map.getCanvas().clientHeight * .2 && pixel.y < map.getCanvas().clientHeight * .7).slice(0, 12)));
        }, 120);
      };
      map.on('idle', refreshCounts);
      map.on('sourcedata', refreshCounts);
      map.on('styledata', refreshCounts);
      map.on('moveend', refreshCounts);
      map.on('zoomend', () => { if (!disposed) setZoom(map.getZoom()); });
      map.on('click', event => {
        if (usePlanningStore.getState().drawing) {
          usePlanningStore.getState().addPoint([event.lngLat.lng, event.lngLat.lat]);
          return;
        }
        const hitLayers = ['tree-canopies', 'building-roofs', 'aerial-building-hit', 'parks', 'water', 'roads', 'air-stations'].filter(id => map.getLayer(id));
        const treeHits = map.queryRenderedFeatures([[event.point.x - 9, event.point.y - 9], [event.point.x + 9, event.point.y + 9]], { layers: ['tree-canopies'] });
        const nearest = nearestTree(treeHits, event.point, coordinate => map.project(coordinate));
        const cluster = map.queryRenderedFeatures(event.point, { layers: ['tree-clusters'] })[0];
        if (!nearest && cluster?.geometry.type === 'Point') {
          (map.getSource('trees') as GeoJSONSource).getClusterExpansionZoom(Number(cluster.properties.cluster_id)).then(zoom => { if (!disposed) map.easeTo({ center: cluster.geometry.type === 'Point' ? cluster.geometry.coordinates as [number, number] : config.center, zoom }); }).catch(() => {});
          return;
        }
        const hit = nearest || map.queryRenderedFeatures(event.point, { layers: hitLayers })[0];
        if (!hit) {
          const lon = event.lngLat.lng, lat = event.lngLat.lat;
          const dy = 20 / 111320, dx = dy / Math.cos(lat * Math.PI / 180);
          useRemovalStore.getState().setPreview(null);
          setSelectedFeature({ type: 'Feature', geometry: { type: 'Polygon', coordinates: [[[lon-dx, lat-dy], [lon+dx, lat-dy], [lon+dx, lat+dy], [lon-dx, lat+dy], [lon-dx, lat-dy]]] }, properties: { category: 'area', name: 'Ground selection (~40 m)', source: 'User-selected ground; classified from published data', clicked_location: [lon, lat] } });
          return;
        }
        const category = hit.layer.id === 'tree-canopies' ? 'mapped_tree' : ['building-roofs', 'aerial-building-hit'].includes(hit.layer.id) ? 'building' : hit.layer.id === 'parks' ? 'park' : hit.layer.id === 'water' ? 'water' : hit.layer.id === 'air-stations' ? 'air_station' : 'road';
        let geometry = hit.geometry;
        if (geometry.type === 'MultiPolygon') {
          const polygon = geometry.coordinates.find(coordinates => isPointInPolygon([event.lngLat.lng, event.lngLat.lat], { type: 'Polygon', coordinates }));
          if (polygon) geometry = { type: 'Polygon', coordinates: polygon };
        }
        useRemovalStore.getState().setPreview(null);
        const location: [number, number] = category === 'mapped_tree' && geometry.type === 'Point' ? geometry.coordinates as [number, number] : [event.lngLat.lng, event.lngLat.lat];
        setSelectedFeature({ type: 'Feature', id: hit.id, geometry, properties: { ...hit.properties, clicked_location: location, name: hit.properties?.name || hit.properties?.species || (category === 'building' ? 'Mapped building' : category === 'mapped_tree' ? 'Mapped tree' : category), category, source: hit.properties?.municipal ? 'City of Zürich · CC0 tree register' : hit.properties?.source || (category === 'air_station' ? 'OpenAQ' : 'OpenStreetMap / OpenFreeMap'), crown_note: hit.properties?.municipal ? 'Register estimate; 8 m may be a fallback, not a measured crown.' : undefined, within_analysis_area: isPointInPolygon(location, boundary), illustration_note: category === 'building' ? 'Real mapped footprint; roof colors and textures are illustrative.' : undefined } });
      });
      map.on('mousemove', event => {
        const now = performance.now();
        if (usePlanningStore.getState().drawing) { map.getCanvas().style.cursor = 'crosshair'; return; }
        if (now - lastHoverAt < 50 || map.isMoving()) return;
        lastHoverAt = now;
        if (!map.getLayer('tree-canopies')) return;
        const trees = map.queryRenderedFeatures([[event.point.x - 9, event.point.y - 9], [event.point.x + 9, event.point.y + 9]], { layers: ['tree-canopies'] });
        const hit = nearestTree(trees, event.point, coordinate => map.project(coordinate)) || map.queryRenderedFeatures(event.point, { layers: ['building-roofs', 'aerial-building-hit', 'parks', 'water', 'roads', 'tree-clusters'].filter(id => map.getLayer(id)) })[0];
        map.getCanvas().style.cursor = hit ? 'pointer' : '';
        const state = usePlanningStore.getState();
        const next = hit ? { id: hit.id, name: hit.properties?.name || hit.properties?.species || (hit.properties?.point_count ? `${hit.properties.point_count} mapped trees · zoom to inspect` : hit.layer.id === 'building-roofs' ? 'Mapped building' : hit.layer.id === 'tree-canopies' ? 'Mapped tree' : hit.layer.id), category: hit.properties?.category || hit.layer.id } : null;
        if (JSON.stringify(next) !== JSON.stringify(state.highlighted)) {
          state.setHighlighted(next);
          setSource(map, 'hover', { type: 'FeatureCollection', features: hit && hit.layer.id === 'tree-canopies' ? [{ type: 'Feature', geometry: hit.geometry, properties: {} }] : [] });
        }
      });
      map.getCanvas().addEventListener('mouseleave', () => { usePlanningStore.getState().setHighlighted(null); setSource(map, 'hover', { type: 'FeatureCollection', features: [] }); });
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
      usePlanningStore.getState().resetDrawing();
      usePlanningStore.getState().setHighlighted(null);
    };
  }, [config, boundary, setSelectedFeature]);

  useEffect(() => { if (readyMap) applyVisibility(readyMap, layers, mode); }, [readyMap, layers, mode]);

  useEffect(() => {
    if (!readyMap) return;
    if (drawing) readyMap.doubleClickZoom.disable(); else readyMap.doubleClickZoom.enable();
    const features: FeatureCollection['features'] = points.map(point => ({ type: 'Feature', properties: {}, geometry: { type: 'Point', coordinates: point } }));
    if (points.length >= 2) features.push({ type: 'Feature', properties: {}, geometry: { type: 'LineString', coordinates: points } });
    if (points.length >= 3) features.push({ type: 'Feature', properties: {}, geometry: { type: 'Polygon', coordinates: [[...points, points[0]!]] } });
    setSource(readyMap, 'drawing', { type: 'FeatureCollection', features });
  }, [readyMap, drawing, points]);

  function finishArea() {
    if (points.length < 3) return;
    useRemovalStore.getState().setPreview(null);
    setSelectedFeature({ type: 'Feature', geometry: { type: 'Polygon', coordinates: [[...points, points[0]]] }, properties: { category: 'area', name: 'Custom planning area', source: 'User polygon intersected with published city datasets', clicked_location: points[0] } });
    resetDrawing();
  }

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

  return (
    <div className="city-map relative overflow-hidden bg-black" data-city-map-ready={!!readyMap} data-view-mode={mode}>
      <div ref={hostRef} style={{ position: 'absolute', inset: 0 }} />
      {layers.weather && weatherEffects && currentWeather && mode === 'illustrated' && (
        <div className={`city-atmosphere pointer-events-none absolute inset-0 ${night ? 'city-atmosphere-night' : ''} ${wet ? 'city-atmosphere-rain' : ''}`} aria-hidden="true" />
      )}

      <div className="absolute top-5 left-5 right-5 z-10 flex items-start justify-between gap-3 pointer-events-none">
        <div className="city-map-panel pointer-events-auto rounded-2xl p-4 w-[300px] max-w-[55%]">
          <div className="flex items-center gap-2 text-xs font-semibold text-primary">City planning · lightweight 2D</div>
          <h2 className="mt-1 text-2xl font-bold tracking-tight text-ink">{config.zurich ? 'Zurich' : cityName}</h2>
          <div className="flex gap-1 mt-3 bg-sky-50 rounded-xl p-1">
            <button onClick={() => changeMode('illustrated')} aria-pressed={mode === 'illustrated'} className={`flex-1 city-view-button ${mode === 'illustrated' ? 'city-view-button-active' : ''}`}><Layers3 size={13} /> Illustrated 2D</button>
            {config.zurich && <button onClick={() => changeMode('imagery')} aria-pressed={mode === 'imagery'} className={`flex-1 city-view-button ${mode === 'imagery' ? 'city-view-button-active' : ''}`}><Satellite size={13} /> Aerial</button>}
          </div>
        </div>
        {layers.weather && <div className="city-map-panel pointer-events-auto rounded-2xl p-3 w-[170px]">
          <div className="flex items-center justify-between"><CloudSun size={21} className="text-[#d3a95c]" /><span className="text-xl font-semibold text-[#344732]">{currentWeather?.temperature_c != null ? `${Math.round(currentWeather.temperature_c)}°` : '—'}</span></div>
          <p className="mt-1 text-[11px] font-semibold text-[#5a6e4e]">{currentWeather ? wet ? 'Rainy skies' : night ? 'Evening light' : 'Daylight' : 'Weather unavailable'}</p>
          {currentWeather && <><div className="mt-2 flex gap-3 text-xs text-muted"><span className="flex items-center gap-1"><Wind size={13} />{currentWeather.wind_mps?.toFixed(1) ?? '—'} m/s</span><span>{precipitation.toFixed(1)} mm</span></div><p className="text-xs text-muted mt-2">{environment?.weather.source === 'live_forecast' ? 'Live forecast' : 'Pinned forecast'} · {new Date(currentWeather.valid_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}{weather?.stale ? ' · stale' : ''}</p></>}
          <button onClick={() => setWeatherEffects(!weatherEffects)} className="mt-2 text-[10px] text-[#5a785b] underline underline-offset-2" aria-pressed={weatherEffects}>Atmosphere {weatherEffects ? 'on' : 'off'}</button>
        </div>}
      </div>

      <div className="absolute top-[230px] right-5 z-10 city-map-panel rounded-xl p-2 flex items-center gap-2 text-sm" role="toolbar" aria-label="Custom area selection">
        {!drawing ? <><button className="flex items-center gap-2 rounded-lg bg-primary text-white px-3 py-2 font-semibold" onClick={() => { setSelectedFeature(null); setDrawing(true); }}><Scan size={17} />Draw area</button><button className="city-nav-button" aria-label="Clear selection" onClick={() => setSelectedFeature(null)}><X size={17} /></button></> : <><span className="px-2 text-muted">{points.length} points</span><button disabled={points.length < 3} className="flex items-center gap-1 bg-primary text-white rounded-lg px-3 py-2 disabled:opacity-40" onClick={finishArea}><Check size={16} />Finish area</button><button className="city-nav-button" aria-label="Cancel drawing" onClick={resetDrawing}><X size={17} /></button></>}
      </div>

      <div className="absolute bottom-4 left-1/2 -translate-x-1/2 z-20 city-map-panel rounded-2xl p-1.5 flex gap-1" role="toolbar" aria-label="City map navigation">
        <button className="city-nav-button" aria-label="Zoom in" title="Zoom in" onClick={() => mapRef.current?.zoomIn({ duration: 250 })}><Plus size={17} /></button>
        <button className="city-nav-button" aria-label="Zoom out" title="Zoom out" onClick={() => mapRef.current?.zoomOut({ duration: 250 })}><Minus size={17} /></button>
        <button className="city-nav-button" aria-label="View entire city" title="View entire city" onClick={() => mapRef.current?.fitBounds([[config.bounds[0], config.bounds[1]], [config.bounds[2], config.bounds[3]]], { padding: 70, pitch: 0, bearing: 0, duration: 800 })}><Globe2 size={17} /></button>
        <button className="city-nav-button" aria-label="View analysis area" title="View analysis area" onClick={flyToStudy}><Focus size={17} /></button>
        <button className="city-nav-button" aria-label="Toggle north-up orientation" title="Toggle north-up orientation" onClick={() => { setNorthUp(!northUp); mapRef.current?.easeTo({ bearing: northUp ? -24 : 0, duration: 300 }); }}><Layers3 size={17} /></button>
        <button className="city-nav-button" aria-label="Reset city view" title="Return downtown" onClick={() => { setNorthUp(false); mapRef.current?.flyTo({ center: config.center, zoom: 15.5, bearing: -24, pitch: 0, duration: 600 }); }}><RotateCcw size={16} /></button>
      </div>

      <div className="absolute top-[205px] left-5 z-10 city-map-panel rounded-xl px-3 py-2 text-xs max-w-[220px] pointer-events-none">
        <span className="flex items-center gap-1.5"><Building2 size={12} />{mode === 'imagery' ? 'Aerial imagery' : `${buildingCount.toLocaleString()} visible buildings`}</span>
        <p className="text-primary mt-1">Dashed line: study boundary</p>
      </div>
      {zoom < 13 && mode === 'illustrated' && <div className="absolute bottom-20 left-1/2 -translate-x-1/2 z-10 city-map-panel px-3 py-2 rounded-xl text-xs text-primary">Zoom in to explore buildings and street details</div>}
      {(loading || error || (imageryError && mode === 'imagery')) && <div role="status" className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 z-20 city-map-panel rounded-2xl px-5 py-4 max-w-sm text-sm text-[#5a6f51]">{error || (imageryError && mode === 'imagery' ? 'Aerial imagery is temporarily unavailable. Illustrated 2D remains available.' : <span className="flex items-center gap-3"><span className="w-4 h-4 rounded-full border-2 border-[#a5b996] border-t-[#538169] animate-spin" /> Bringing the city into view…</span>)}</div>}
    </div>
  );
}
