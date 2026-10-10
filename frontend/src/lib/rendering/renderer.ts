import { Application, Container, Graphics } from 'pixi.js';
import { MapCamera } from './camera';
import { WORLDCOVER_CLASSES, type ScenarioEdit } from '../scenarios';

export class CityRenderer {
  public app: Application | null = null;
  public camera: MapCamera;
  public container: HTMLElement;

  public terrainContainer: Container;
  public parksContainer: Container;
  public roadsContainer: Container;
  public buildingsContainer: Container;
  public markersContainer: Container;
  public diffContainer: Container;
  public selectionContainer: Container;
  public handleContainer: Container;

  private isDestroyed: boolean = false;

  constructor(container: HTMLElement) {
    this.container = container;
    this.camera = new MapCamera(0, 0, 5000, container.clientWidth, container.clientHeight);

    this.terrainContainer = new Container();
    this.parksContainer = new Container();
    this.roadsContainer = new Container();
    this.buildingsContainer = new Container();
    this.markersContainer = new Container();
    this.diffContainer = new Container();
    this.selectionContainer = new Container();
    this.handleContainer = new Container();
  }

  public async init(): Promise<boolean> {
    try {
      this.app = new Application();
      await this.app.init({
        resizeTo: this.container,
        backgroundAlpha: 0,
        antialias: true,
        resolution: typeof window !== 'undefined' ? Math.min(window.devicePixelRatio || 1, 2) : 1,
        preference: 'webgl',
      });

      if (this.isDestroyed || !this.app.canvas) {
        return false;
      }

      this.container.appendChild(this.app.canvas);

      // Deterministic z-order
      this.app.stage.addChild(this.terrainContainer);
      this.app.stage.addChild(this.parksContainer);
      this.app.stage.addChild(this.roadsContainer);
      this.app.stage.addChild(this.buildingsContainer);
      this.app.stage.addChild(this.markersContainer);
      this.app.stage.addChild(this.diffContainer);
      this.app.stage.addChild(this.selectionContainer);
      this.app.stage.addChild(this.handleContainer);

      return true;
    } catch (err) {
      console.warn('WebGL / Pixi initialization failed, falling back to SVG renderer:', err);
      return false;
    }
  }

  public resize(width: number, height: number) {
    if (this.app && !this.isDestroyed) {
      this.camera.setViewport(width, height);
    }
  }

  public renderFeatures(
    features: any[],
    layerVisibility: {
      buildings: boolean;
      roads: boolean;
      parks: boolean;
      water: boolean;
      waste: boolean;
      air: boolean;
    }
  ) {
    if (!this.app || this.isDestroyed) return;

    this.terrainContainer.removeChildren();
    this.parksContainer.removeChildren();
    this.roadsContainer.removeChildren();
    this.buildingsContainer.removeChildren();
    this.markersContainer.removeChildren();

    this.terrainContainer.visible = layerVisibility.water;
    this.parksContainer.visible = layerVisibility.parks;
    this.roadsContainer.visible = layerVisibility.roads;
    this.buildingsContainer.visible = layerVisibility.buildings;

    for (const feat of features) {
      const geom = feat.geometry;
      if (!geom) continue;

      const category = (feat.properties?.category || feat.properties?.class || '').toLowerCase();

      if (category.includes('water') && layerVisibility.water) {
        this.drawPolygon(this.terrainContainer, geom, 0x1e88e5, 0.7, 0x1565c0);
      } else if ((category.includes('park') || category.includes('vegetation') || category.includes('forest')) && layerVisibility.parks) {
        this.drawPolygon(this.parksContainer, geom, 0x81c784, 0.8, 0x388e3c);
      } else if (category.includes('road') && layerVisibility.roads) {
        this.drawLine(this.roadsContainer, geom, 0x37474f, 3);
      } else if ((category.includes('building') || category.includes('residential') || category.includes('commercial')) && layerVisibility.buildings) {
        const isCommercial = category.includes('commercial');
        this.drawPolygon(this.buildingsContainer, geom, isCommercial ? 0x90a4ae : 0xd7ccc8, 0.9, 0x546e7a);
      } else {
        // Generic polygon
        if (geom.type === 'Polygon' || geom.type === 'MultiPolygon') {
          this.drawPolygon(this.buildingsContainer, geom, 0xcccccc, 0.7, 0x888888);
        } else if (geom.type === 'LineString' || geom.type === 'MultiLineString') {
          this.drawLine(this.roadsContainer, geom, 0x555555, 2);
        } else if (geom.type === 'Point') {
          this.drawPoint(this.markersContainer, geom, 0x00acc1, 6);
        }
      }
    }
  }

  public renderSelection(selectedFeature: any | null) {
    if (!this.app || this.isDestroyed) return;
    this.selectionContainer.removeChildren();

    if (!selectedFeature || !selectedFeature.geometry) return;

    const geom = selectedFeature.geometry;
    if (geom.type === 'Polygon' || geom.type === 'MultiPolygon') {
      this.drawPolygon(this.selectionContainer, geom, 0xffd54f, 0.4, 0xff8f00, 3);
    } else if (geom.type === 'Point') {
      this.drawPoint(this.selectionContainer, geom, 0xff8f00, 10, true);
    }
  }

  public renderScenarioEdits(edits: ScenarioEdit[]) {
    if (!this.app || this.isDestroyed) return;
    this.diffContainer.removeChildren();

    for (const edit of edits) {
      if (edit.edit_type === 'LAND_COVER_RECLASSIFY') {
        const classInfo = WORLDCOVER_CLASSES[edit.to_class_code];
        const color = classInfo ? parseInt(classInfo.color.replace('#', '0x'), 16) : 0x2e7d32;
        this.drawPolygon(this.diffContainer, edit.polygon_geojson, color, 0.6, 0x1b5e20, 2);
      } else if (edit.edit_type === 'SOLAR_PV_INSTALL') {
        this.drawPolygon(this.diffContainer, edit.footprint_geojson, 0x1565c0, 0.7, 0x0d47a1, 2);
      }
    }
  }

  private drawPolygon(
    container: Container,
    geom: any,
    fillColor: number,
    fillAlpha: number,
    strokeColor: number,
    strokeWidth: number = 1
  ) {
    const g = new Graphics();
    g.fill({ color: fillColor, alpha: fillAlpha });
    g.stroke({ color: strokeColor, width: strokeWidth });

    const rings = geom.type === 'Polygon' ? [geom.coordinates] : geom.coordinates;

    for (const poly of rings) {
      for (const ring of poly) {
        if (!Array.isArray(ring) || ring.length < 3) continue;
        const screenPoints: number[] = [];
        for (const pt of ring) {
          const [x, y] = this.camera.worldToScreen(pt[0], pt[1]);
          screenPoints.push(x, y);
        }

        if (screenPoints.length >= 6) {
          g.poly(screenPoints);
        }
      }
    }

    container.addChild(g);
  }

  private drawLine(container: Container, geom: any, strokeColor: number, strokeWidth: number) {
    const g = new Graphics();
    g.stroke({ color: strokeColor, width: strokeWidth });

    const lines = geom.type === 'LineString' ? [geom.coordinates] : geom.coordinates;

    for (const line of lines) {
      if (!Array.isArray(line) || line.length < 2) continue;
      const first = line[0];
      const [startX, startY] = this.camera.worldToScreen(first[0], first[1]);
      g.moveTo(startX, startY);

      for (let i = 1; i < line.length; i++) {
        const pt = line[i];
        const [x, y] = this.camera.worldToScreen(pt[0], pt[1]);
        g.lineTo(x, y);
      }
    }

    container.addChild(g);
  }

  private drawPoint(
    container: Container,
    geom: any,
    color: number,
    radius: number,
    highlight: boolean = false
  ) {
    const coords = geom.coordinates;
    if (!coords || coords.length < 2) return;
    const [x, y] = this.camera.worldToScreen(coords[0], coords[1]);

    const g = new Graphics();
    g.circle(x, y, radius);
    g.fill({ color, alpha: highlight ? 0.9 : 0.8 });
    g.stroke({ color: highlight ? 0xffffff : 0x000000, width: 2 });
    container.addChild(g);
  }

  public destroy() {
    this.isDestroyed = true;
    try {
      if (this.app) {
        this.app.destroy(true, { children: true, texture: true });
        this.app = null;
      }
    } catch {
      // Ignore cleanup error on unmount
    }
  }
}
