import { test, expect } from '@playwright/test';

test.use({ viewport: { width: 1680, height: 1080 } });

test('published OSM features provide bounded, research-backed removal reports for all four types', async ({ request }) => {
  test.skip(process.env.RUN_LIVE_MAP_TESTS !== '1', 'Requires the imported Zurich snapshot and running backend.');
  const cities = await (await request.get('/api/gateway/v1/cities')).json();
  const city = cities.find((candidate: { slug: string }) => candidate.slug === 'zurich-center');
  const base = `/api/gateway/v1/cities/${city.id}`;
  for (const kind of ['tree', 'building', 'park', 'road']) {
    const features = await (await request.get(`${base}/features?category=${kind === 'tree' ? 'mapped_tree' : kind}&bbox=8.53,47.37,8.55,47.39&limit=1`)).json();
    const geometry = features.features[0].geometry;
    const location = geometry.type === 'Point' ? geometry.coordinates : geometry.type === 'LineString' ? geometry.coordinates[0] : geometry.type === 'Polygon' ? geometry.coordinates[0][0] : geometry.coordinates[0][0][0];
    const response = await request.post(`${base}/removal-preview`, { data: { kind, geometry, location, replacement: kind === 'tree' ? 'unchanged' : 'grass', rainfall_mm: 50 } });
    expect(response.status()).toBe(200);
    const report = await response.json();
    expect(report.kind).toBe(kind);
    expect(report.geometry_source).toContain('Published OSM revision');
    expect(report.area_m2).toBeGreaterThan(0);
    expect(report.sources.length).toBeGreaterThan(3);
    const runoff = report.metrics.find((metric: { key: string }) => metric.key === 'runoff');
    expect(runoff.delta).toBeLessThanOrEqual(0);
    if (kind === 'road') expect(report.metrics[0].evidence).toBe('ASSUMED_INPUT');
    if (kind === 'tree') expect(runoff.delta).toBe(0);
    if (kind === 'building' || kind === 'road') expect(runoff.delta).toBeLessThan(0);
    if (kind === 'road') expect(report.area_m2).toBeLessThanOrEqual(301);
  }
});

test('click a real city feature, update consequences and compare removal without recreating the map', async ({ page, request }) => {
  test.skip(process.env.RUN_LIVE_MAP_TESTS !== '1', 'Requires the Zurich snapshot and internet map tiles.');
  test.setTimeout(120000);
  const cities = await (await request.get('/api/gateway/v1/cities')).json();
  const city = cities.find((candidate: { slug: string }) => candidate.slug === 'zurich-center');
  const errors: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.goto(`/city/${city.id}`);
  await expect(page.locator('[data-city-map-ready="true"]')).toBeVisible({ timeout: 60000 });
  await expect.poll(async () => Number(await page.locator('[data-rendered-buildings]').getAttribute('data-rendered-buildings')), { timeout: 45000 }).toBeGreaterThan(0);
  const canvas = await page.locator('canvas').elementHandle();
  const box = (await canvas!.boundingBox())!;
  // Real rendered-feature hit testing, rather than injecting a fake selection.
  let selected = false;
  for (const y of [0.45, 0.55, 0.35, 0.65]) {
    for (const x of [0.45, 0.55, 0.35, 0.65]) {
      await page.mouse.click(box.x + box.width * x, box.y + box.height * y);
      selected = await page.locator('[data-removal-panel]').isVisible() && (await page.locator('[data-removal-panel]').getAttribute('data-removal-panel')) !== 'water';
      if (selected) break;
    }
    if (selected) break;
  }
  expect(selected).toBe(true);
  await expect(page.locator('[data-removal-results]')).toBeVisible({ timeout: 30000 });
  await page.getByRole('button', { name: 'Preview removal on map', exact: true }).click();
  await page.getByRole('button', { name: 'Before', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Before', exact: true })).toHaveAttribute('aria-pressed', 'true');
  await page.getByRole('button', { name: 'After removal', exact: true }).click();
  await page.getByLabel('Ground after removal').selectOption('impervious');
  await page.getByLabel('Test a design storm instead of forecast rain').check();
  await expect(page.getByLabel('Design storm rainfall')).toBeVisible();
  await expect(page.locator('[data-impact-metric="runoff"]')).toBeVisible({ timeout: 15000 });
  await expect(page.getByText('runoff uses 30 mm design storm', { exact: false })).toBeVisible();
  if (process.env.RUN_LOCAL_AI_TESTS === '1') {
    await page.getByText('Local AI explanation', { exact: true }).click();
    await page.getByRole('button', { name: /^Explain with / }).click();
    await expect(page.locator('[data-local-ai-explanation]')).toBeVisible({ timeout: 60000 });
    await expect(page.locator('[data-local-ai-explanation]')).toContainText('All quantities are computed');
  }
  await page.getByRole('button', { name: 'Restore feature', exact: true }).click();
  await expect(page.getByRole('button', { name: 'After removal', exact: true })).toHaveCount(0);
  expect(await canvas!.evaluate(node => node === document.querySelector('canvas'))).toBe(true);
  expect(errors).toEqual([]);
});
