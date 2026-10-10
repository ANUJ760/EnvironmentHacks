import proj4 from 'proj4';
import booleanPointInPolygon from '@turf/boolean-point-in-polygon';
import { point as turfPoint, polygon as turfPolygon, multiPolygon as turfMultiPolygon } from '@turf/helpers';

// Register standard projections commonly used for city analysis
proj4.defs('EPSG:4326', '+proj=longlat +datum=WGS84 +no_defs');
proj4.defs('EPSG:3857', '+proj=merc +a=6378137 +b=6378137 +lat_ts=0 +lon_0=0 +x_0=0 +y_0=0 +k=1 +units=m +nadgrids=@null +wktext +no_defs');
proj4.defs('EPSG:32643', '+proj=utm +zone=43 +datum=WGS84 +units=m +no_defs');
proj4.defs('EPSG:32644', '+proj=utm +zone=44 +datum=WGS84 +units=m +no_defs');
proj4.defs('EPSG:32632', '+proj=utm +zone=32 +datum=WGS84 +units=m +no_defs');
proj4.defs('EPSG:32633', '+proj=utm +zone=33 +datum=WGS84 +units=m +no_defs');

export interface BoundingBox {
  minLon: number;
  minLat: number;
  maxLon: number;
  maxLat: number;
}

export function formatBBox(bbox: BoundingBox): string {
  return `${bbox.minLon.toFixed(6)},${bbox.minLat.toFixed(6)},${bbox.maxLon.toFixed(6)},${bbox.maxLat.toFixed(6)}`;
}

export function parseBBox(str: string): BoundingBox | null {
  const parts = str.split(',').map(Number);
  if (parts.length !== 4 || parts.some(isNaN)) return null;
  const [minLon = 0, minLat = 0, maxLon = 0, maxLat = 0] = parts;
  return { minLon, minLat, maxLon, maxLat };
}

export function computeBBoxFromGeometry(geometry: any): BoundingBox {
  let minLon = Infinity;
  let minLat = Infinity;
  let maxLon = -Infinity;
  let maxLat = -Infinity;

  function traverse(coords: any) {
    if (!Array.isArray(coords)) return;
    if (typeof coords[0] === 'number' && typeof coords[1] === 'number') {
      const [lon, lat] = coords as [number, number];
      if (lon < minLon) minLon = lon;
      if (lat < minLat) minLat = lat;
      if (lon > maxLon) maxLon = lon;
      if (lat > maxLat) maxLat = lat;
    } else {
      for (const item of coords) {
        traverse(item);
      }
    }
  }

  traverse(geometry?.coordinates || []);

  if (minLon === Infinity) {
    return { minLon: 0, minLat: 0, maxLon: 0, maxLat: 0 };
  }

  return { minLon, minLat, maxLon, maxLat };
}

export function isPointInPolygon(point: [number, number], polygonGeoJson: any): boolean {
  try {
    const pt = turfPoint(point);
    if (polygonGeoJson.type === 'Polygon') {
      const poly = turfPolygon(polygonGeoJson.coordinates);
      return booleanPointInPolygon(pt, poly);
    }
    if (polygonGeoJson.type === 'MultiPolygon') {
      const poly = turfMultiPolygon(polygonGeoJson.coordinates);
      return booleanPointInPolygon(pt, poly);
    }
  } catch {
    return false;
  }
  return false;
}

export function validatePolygon(coords: number[][][]): { valid: boolean; error?: string } {
  if (!coords || coords.length === 0) {
    return { valid: false, error: 'Polygon must have at least one linear ring.' };
  }

  const exterior = coords[0];
  if (!exterior || exterior.length < 4) {
    return { valid: false, error: 'Exterior ring must have at least 4 coordinates (including closure).' };
  }

  const first = exterior[0];
  const last = exterior[exterior.length - 1];
  if (!first || !last || first[0] !== last[0] || first[1] !== last[1]) {
    return { valid: false, error: 'Exterior ring must be closed (first and last coordinate match).' };
  }

  return { valid: true };
}

export function projectCoordinates(
  coords: [number, number],
  fromCrs: string = 'EPSG:4326',
  toCrs: string = 'EPSG:3857'
): [number, number] {
  try {
    return proj4(fromCrs, toCrs, coords);
  } catch {
    return coords;
  }
}
