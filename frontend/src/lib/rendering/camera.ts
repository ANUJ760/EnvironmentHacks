import type { BoundingBox } from '../geo';

export class MapCamera {
  public centerLon: number;
  public centerLat: number;
  public zoom: number; // pixels per degree
  public width: number;
  public height: number;

  constructor(centerLon: number = 0, centerLat: number = 0, zoom: number = 5000, width: number = 800, height: number = 600) {
    this.centerLon = centerLon;
    this.centerLat = centerLat;
    this.zoom = zoom;
    this.width = width;
    this.height = height;
  }

  public setViewport(width: number, height: number) {
    this.width = Math.max(10, width);
    this.height = Math.max(10, height);
  }

  public worldToScreen(lon: number, lat: number): [number, number] {
    const x = this.width / 2 + (lon - this.centerLon) * this.zoom;
    // Y is inverted in screen space: higher latitude (North) is lower Y (top of screen)
    const y = this.height / 2 - (lat - this.centerLat) * this.zoom;
    return [x, y];
  }

  public screenToWorld(x: number, y: number): [number, number] {
    const lon = this.centerLon + (x - this.width / 2) / this.zoom;
    const lat = this.centerLat - (y - this.height / 2) / this.zoom;
    return [lon, lat];
  }

  public getVisibleBBox(): BoundingBox {
    const [minLon, maxLat] = this.screenToWorld(0, 0);
    const [maxLon, minLat] = this.screenToWorld(this.width, this.height);
    return { minLon, minLat, maxLon, maxLat };
  }

  public fitBounds(bbox: BoundingBox, padding: number = 40) {
    this.centerLon = (bbox.minLon + bbox.maxLon) / 2;
    this.centerLat = (bbox.minLat + bbox.maxLat) / 2;

    const lonDiff = Math.max(0.0001, bbox.maxLon - bbox.minLon);
    const latDiff = Math.max(0.0001, bbox.maxLat - bbox.minLat);

    const availableWidth = Math.max(100, this.width - padding * 2);
    const availableHeight = Math.max(100, this.height - padding * 2);

    const zoomX = availableWidth / lonDiff;
    const zoomY = availableHeight / latDiff;

    this.zoom = Math.min(zoomX, zoomY);
  }

  public pan(dx: number, dy: number) {
    this.centerLon -= dx / this.zoom;
    this.centerLat += dy / this.zoom;
  }

  public zoomAt(factor: number, screenX?: number, screenY?: number) {
    const targetX = screenX !== undefined ? screenX : this.width / 2;
    const targetY = screenY !== undefined ? screenY : this.height / 2;

    const [worldLon, worldLat] = this.screenToWorld(targetX, targetY);

    const newZoom = Math.min(2000000, Math.max(200, this.zoom * factor));
    this.zoom = newZoom;

    // Adjust center so point under mouse stays under mouse
    this.centerLon = worldLon - (targetX - this.width / 2) / this.zoom;
    this.centerLat = worldLat + (targetY - this.height / 2) / this.zoom;
  }
}
