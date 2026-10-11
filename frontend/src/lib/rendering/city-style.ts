import type { ExpressionSpecification, StyleSpecification } from 'maplibre-gl';
import { computeBBoxFromGeometry } from '@/lib/geo';

export type CityViewMode = 'illustrated' | 'imagery';

export const ZURICH_BOUNDS: [number, number, number, number] = [8.448, 47.320, 8.625, 47.445];

export function cityVisualConfig(slug: string, boundary: any) {
  const bbox = computeBBoxFromGeometry(boundary);
  const zurich = slug.startsWith('zurich');
  return {
    zurich,
    center: zurich ? [8.5417, 47.3739] as [number, number] : [(bbox.minLon + bbox.maxLon) / 2, (bbox.minLat + bbox.maxLat) / 2] as [number, number],
    bounds: zurich ? ZURICH_BOUNDS : [bbox.minLon, bbox.minLat, bbox.maxLon, bbox.maxLat] as [number, number, number, number],
    treesUrl: zurich ? `${(process.env.NEXT_PUBLIC_MAP_ASSET_BASE_URL || '').replace(/\/$/, '')}/maps/zurich-trees.geojson` : null,
  };
}

export const ROOF_COLOR: ExpressionSpecification = ['match', ['%', ['to-number', ['id'], 0], 7],
  0, '#df8864', 1, '#e9b87c', 2, '#8db6b0', 3, '#b593b3', 4, '#d9947d', 5, '#83a8bf', '#cdbb96'];

export function createCityStyle(zurich: boolean): StyleSpecification {
  return {
    version: 8,
    name: 'EcoTwin illustrated city',
    glyphs: 'https://tiles.openfreemap.org/fonts/{fontstack}/{range}.pbf',
    sources: {
      city: { type: 'vector', url: 'https://tiles.openfreemap.org/planet', attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a> · <a href="https://openfreemap.org">OpenFreeMap</a>' },
      ...(zurich ? {
        imagery: { type: 'raster' as const, tiles: ['https://wmts.geo.admin.ch/1.0.0/ch.swisstopo.swissimage/default/current/3857/{z}/{x}/{y}.jpeg'], tileSize: 256, maxzoom: 19, bounds: [5.9, 45.8, 10.6, 47.9], attribution: 'Aerial imagery © <a href="https://www.swisstopo.admin.ch/en/swissimage">swisstopo</a>' },
      } : {}),
      analysis: { type: 'geojson', data: { type: 'FeatureCollection', features: [] } },
      selection: { type: 'geojson', data: { type: 'FeatureCollection', features: [] } },
      interventions: { type: 'geojson', data: { type: 'FeatureCollection', features: [] } },
      removal: { type: 'geojson', data: { type: 'FeatureCollection', features: [] } },
      drawing: { type: 'geojson', data: { type: 'FeatureCollection', features: [] } },
      trees: { type: 'geojson', data: { type: 'FeatureCollection', features: [] }, maxzoom: 16, cluster: true, clusterMaxZoom: 14, clusterRadius: 30 },
      hover: { type: 'geojson', data: { type: 'FeatureCollection', features: [] } },
    },
    layers: [
      { id: 'ground', type: 'background', paint: { 'background-color': '#c9dcb3' } },
      ...(zurich ? [{ id: 'aerial', type: 'raster' as const, source: 'imagery', paint: { 'raster-opacity': 0.24, 'raster-saturation': -0.65, 'raster-contrast': -0.3, 'raster-fade-duration': 150 } }] : []),
      { id: 'neighborhoods', type: 'fill', source: 'city', 'source-layer': 'landuse', filter: ['match', ['get', 'class'], ['residential', 'commercial', 'industrial'], true, false], paint: { 'fill-color': '#eee4cf', 'fill-opacity': 0.87 } },
      { id: 'gardens', type: 'fill', source: 'city', 'source-layer': 'landcover', filter: ['match', ['get', 'class'], ['grass', 'wood', 'wetland'], true, false], paint: { 'fill-color': ['match', ['get', 'class'], 'wood', '#86b580', '#b9d494'], 'fill-opacity': 0.88 } },
      { id: 'parks', type: 'fill', source: 'city', 'source-layer': 'park', paint: { 'fill-color': '#b3d48e', 'fill-opacity': 0.9 } },
      { id: 'park-edges', type: 'line', source: 'city', 'source-layer': 'park', paint: { 'line-color': '#7eaa6c', 'line-width': 1, 'line-opacity': 0.45 } },
      { id: 'sports-fields', type: 'fill', source: 'city', 'source-layer': 'landuse', filter: ['match', ['get', 'class'], ['pitch', 'cemetery'], true, false], paint: { 'fill-color': '#8cba8b', 'fill-outline-color': '#c9e4b8' } },
      { id: 'water-edge', type: 'line', source: 'city', 'source-layer': 'water', paint: { 'line-color': '#6ca8a7', 'line-width': 4 } },
      { id: 'water', type: 'fill', source: 'city', 'source-layer': 'water', paint: { 'fill-color': '#80c9cf', 'fill-opacity': 0.98 } },
      { id: 'streams', type: 'line', source: 'city', 'source-layer': 'waterway', paint: { 'line-color': '#80c9cf', 'line-width': ['interpolate', ['linear'], ['zoom'], 12, 1, 18, 7] } },
      { id: 'road-edge', type: 'line', source: 'city', 'source-layer': 'transportation', filter: ['match', ['get', 'class'], ['rail', 'ferry', 'aerialway'], false, true], layout: { 'line-cap': 'round', 'line-join': 'round' }, paint: { 'line-color': '#c5b9a2', 'line-width': ['interpolate', ['exponential', 1.4], ['zoom'], 10, 1, 14, 4, 17, 13, 20, 35] } },
      { id: 'roads', type: 'line', source: 'city', 'source-layer': 'transportation', filter: ['match', ['get', 'class'], ['rail', 'ferry', 'aerialway'], false, true], layout: { 'line-cap': 'round', 'line-join': 'round' }, paint: { 'line-color': ['match', ['get', 'class'], ['motorway', 'trunk', 'primary'], '#f7dcab', '#fff8e6'], 'line-width': ['interpolate', ['exponential', 1.4], ['zoom'], 10, 0.5, 14, 2.5, 17, 9, 20, 29] } },
      { id: 'rail', type: 'line', source: 'city', 'source-layer': 'transportation', filter: ['==', ['get', 'class'], 'rail'], paint: { 'line-color': '#a59d92', 'line-width': 1.5, 'line-dasharray': [3, 2] } },
      { id: 'building-shadows', type: 'fill', source: 'city', 'source-layer': 'building', minzoom: 13, paint: { 'fill-color': '#7c745e', 'fill-opacity': 0.22, 'fill-translate': [3, 5], 'fill-translate-anchor': 'map' } },
      { id: 'building-roofs', type: 'fill', source: 'city', 'source-layer': 'building', minzoom: 13, paint: { 'fill-color': ROOF_COLOR, 'fill-outline-color': '#90795c' } },
      { id: 'roof-details', type: 'fill', source: 'city', 'source-layer': 'building', minzoom: 16, paint: { 'fill-pattern': 'roof-grain', 'fill-opacity': 0.3 } },
      { id: 'roof-rims', type: 'line', source: 'city', 'source-layer': 'building', minzoom: 16, paint: { 'line-color': '#ffedcb', 'line-width': 0.6, 'line-opacity': 0.7, 'line-offset': -0.7 } },
      { id: 'aerial-building-hit', type: 'fill', source: 'city', 'source-layer': 'building', minzoom: 13, layout: { visibility: 'none' }, paint: { 'fill-opacity': 0 } },
      { id: 'tree-shadows', type: 'circle', source: 'trees', minzoom: 15, filter: ['!', ['has', 'point_count']], paint: { 'circle-radius': ['interpolate', ['linear'], ['zoom'], 15, 1.5, 18, 6], 'circle-color': '#547759', 'circle-opacity': 0.2, 'circle-translate': [2, 3] } },
      { id: 'tree-clusters', type: 'circle', source: 'trees', maxzoom: 15, filter: ['has', 'point_count'], paint: { 'circle-radius': ['step', ['get', 'point_count'], 8, 100, 12, 1000, 17], 'circle-color': '#4d9962', 'circle-stroke-color': '#b1e7a7', 'circle-stroke-width': 1, 'circle-opacity': 0.8 } },
      { id: 'tree-canopies', type: 'circle', source: 'trees', minzoom: 13, filter: ['!', ['has', 'point_count']], paint: { 'circle-radius': ['interpolate', ['linear'], ['zoom'], 13, 2, 15, 3, 18, 8], 'circle-color': '#75b76a', 'circle-stroke-color': '#3e7844', 'circle-stroke-width': 0.8, 'circle-opacity': 0.95 } },
      { id: 'tree-light', type: 'circle', source: 'trees', minzoom: 16, filter: ['!', ['has', 'point_count']], paint: { 'circle-radius': ['interpolate', ['linear'], ['zoom'], 16, 0.6, 18, 2.5], 'circle-color': '#b1cd87', 'circle-translate': [-1, -1], 'circle-opacity': 0.65 } },
      { id: 'tree-hover', type: 'circle', source: 'hover', filter: ['==', ['geometry-type'], 'Point'], paint: { 'circle-radius': 11, 'circle-color': '#55d9ff', 'circle-opacity': 0.1, 'circle-stroke-color': '#55d9ff', 'circle-stroke-width': 2 } },
      { id: 'removal-ground', type: 'fill', source: 'removal', paint: { 'fill-color': ['get', 'color'], 'fill-opacity': 1 } },
      { id: 'removal-border', type: 'line', source: 'removal', paint: { 'line-color': '#b17740', 'line-width': 2, 'line-dasharray': [2, 2] } },
      { id: 'analysis-fill', type: 'fill', source: 'analysis', paint: { 'fill-color': '#167858', 'fill-opacity': 0.035 } },
      { id: 'analysis-boundary', type: 'line', source: 'analysis', paint: { 'line-color': '#167858', 'line-width': 2, 'line-dasharray': [3, 3], 'line-opacity': 0.8 } },
      { id: 'intervention-fill', type: 'fill', source: 'interventions', paint: { 'fill-color': ['get', 'color'], 'fill-opacity': 0.5 } },
      { id: 'intervention-edge', type: 'line', source: 'interventions', paint: { 'line-color': '#174e42', 'line-width': 2.5, 'line-dasharray': [2, 1] } },
      { id: 'selection-fill', type: 'fill', source: 'selection', paint: { 'fill-color': '#ffd686', 'fill-opacity': 0.3 } },
      { id: 'selected-tree', type: 'circle', source: 'selection', filter: ['==', ['geometry-type'], 'Point'], paint: { 'circle-radius': 11, 'circle-color': '#55d9ff', 'circle-opacity': 0.12, 'circle-stroke-color': '#55d9ff', 'circle-stroke-width': 2 } },
      { id: 'selection-edge', type: 'line', source: 'selection', paint: { 'line-color': '#ec9f43', 'line-width': 3 } },
      { id: 'drawing-fill', type: 'fill', source: 'drawing', filter: ['==', ['geometry-type'], 'Polygon'], paint: { 'fill-color': '#38bdf8', 'fill-opacity': 0.22 } },
      { id: 'drawing-line', type: 'line', source: 'drawing', filter: ['==', ['geometry-type'], 'LineString'], paint: { 'line-color': '#0284c7', 'line-width': 3, 'line-dasharray': [2, 1] } },
      { id: 'drawing-points', type: 'circle', source: 'drawing', filter: ['==', ['geometry-type'], 'Point'], paint: { 'circle-color': '#0284c7', 'circle-radius': 5, 'circle-stroke-color': '#fff', 'circle-stroke-width': 2 } },
      { id: 'neighborhood-labels', type: 'symbol', source: 'city', 'source-layer': 'place', minzoom: 10, maxzoom: 16, layout: { 'text-field': ['coalesce', ['get', 'name:en'], ['get', 'name']], 'text-font': ['Noto Sans Regular'], 'text-size': ['interpolate', ['linear'], ['zoom'], 10, 12, 15, 15], 'text-max-width': 8 }, paint: { 'text-color': '#5d6450', 'text-halo-color': '#f6f4df', 'text-halo-width': 2 } },
      { id: 'street-labels', type: 'symbol', source: 'city', 'source-layer': 'transportation_name', minzoom: 16, layout: { 'symbol-placement': 'line', 'text-field': ['get', 'name'], 'text-font': ['Noto Sans Regular'], 'text-size': 10 }, paint: { 'text-color': '#7a735f', 'text-halo-color': '#fff8e7', 'text-halo-width': 1.5 } },
    ],
  };
}

export const CITY_LAYER_GROUPS = {
  buildings: ['building-shadows', 'building-roofs', 'roof-details', 'roof-rims'],
  roads: ['road-edge', 'roads', 'rail', 'street-labels'],
  parks: ['gardens', 'parks', 'park-edges', 'sports-fields', 'tree-shadows', 'tree-canopies', 'tree-light', 'tree-clusters'],
  water: ['water-edge', 'water', 'streams'],
};

export const CARTOON_LAYERS = ['neighborhoods', ...Object.values(CITY_LAYER_GROUPS).flat()];
