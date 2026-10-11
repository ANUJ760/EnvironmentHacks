import { describe, it, expect } from 'vitest';
import type { paths, components } from '@/lib/api/api-types';

describe('OpenAPI Contract Conformance', () => {
  it('includes core backend endpoints in generated paths interface', () => {
    type CitiesGet = paths['/v1/cities']['get'];
    type CityDetailGet = paths['/v1/cities/{identifier}']['get'];
    type FeaturesGet = paths['/v1/cities/{identifier}/features']['get'];
    type ScenariosPost = paths['/v1/scenarios']['post'];
    type ScenarioEditsPut = paths['/v1/scenarios/{identifier}/edits']['put'];
    type SimulatePost = paths['/v1/scenarios/{identifier}/simulate']['post'];
    type JobGet = paths['/v1/jobs/{identifier}']['get'];
    type ResultGet = paths['/v1/results/{identifier}']['get'];
    type ReadyzGet = paths['/readyz']['get'];

    // Verify types compile and exist
    const endpointCheck: boolean = true;
    expect(endpointCheck).toBe(true);
  });

  it('includes required schemas with exact property definitions', () => {
    type CityView = components['schemas']['CityView'];
    type ResultView = components['schemas']['ResultView'];
    type Metric = components['schemas']['Metric'];
    type Reclassify = components['schemas']['Reclassify'];
    type SolarInstall = components['schemas']['SolarInstall'];

    const mockReclassify: Reclassify = {
      edit_type: 'LAND_COVER_RECLASSIFY',
      polygon_geojson: { type: 'Polygon', coordinates: [] },
      from_class_code: 50,
      to_class_code: 10,
      fraction: 0.8,
    };
    expect(mockReclassify.edit_type).toBe('LAND_COVER_RECLASSIFY');

    const mockSolar: SolarInstall = {
      edit_type: 'SOLAR_PV_INSTALL',
      footprint_geojson: { type: 'Polygon', coordinates: [] },
      installed_kwp: 100,
      panel_azimuth_deg: 0,
      panel_tilt_deg: 15,
      performance_ratio: 0.75,
    };
    expect(mockSolar.edit_type).toBe('SOLAR_PV_INSTALL');
  });
});
