import { test, expect } from '@playwright/test';

test.use({ viewport: { width: 1680, height: 1080 } });

test('real Zurich city: 2D details, aerial view, navigation and layer controls', async ({ page, request }) => {
  test.skip(process.env.RUN_LIVE_MAP_TESTS !== '1', 'Requires the locally imported Zurich snapshot and internet tile access.');
  test.setTimeout(120000);
  const cities = await (await request.get('/api/gateway/v1/cities')).json();
  const city = cities.find((candidate: { slug: string }) => candidate.slug === 'zurich-center');
  expect(city).toBeTruthy();
  const errors: string[] = [];
  let paginatedRequests = 0;
  page.on('pageerror', error => errors.push(error.message));
  page.on('request', req => { if (req.url().includes('/features?')) paginatedRequests++; });
  await page.goto(`/city/${city.id}`);
  await expect(page.locator('[data-city-map-ready="true"]')).toBeVisible({ timeout: 60000 });
  await expect.poll(async () => Number(await page.locator('[data-rendered-buildings]').getAttribute('data-rendered-buildings')), { timeout: 45000 }).toBeGreaterThan(0);
  const canvas = await page.locator('canvas').elementHandle();
  expect((await canvas!.boundingBox())!.height).toBeGreaterThan(400);
  await page.getByRole('button', { name: 'Zoom in', exact: true }).click();
  expect(await canvas!.evaluate(node => node === document.querySelector('canvas'))).toBe(true);
  await page.getByRole('button', { name: 'Aerial', exact: true }).click();
  await expect(page.locator('[data-view-mode="imagery"]')).toBeVisible();
  await page.getByRole('button', { name: 'Illustrated 2D', exact: true }).click();
  await page.getByRole('button', { name: 'Buildings (OSM)', exact: true }).click();
  await expect.poll(async () => Number(await page.locator('[data-rendered-buildings]').getAttribute('data-rendered-buildings')), { timeout: 10000 }).toBe(0);
  await page.getByRole('button', { name: 'Buildings (OSM)', exact: true }).click();
  await expect.poll(async () => Number(await page.locator('[data-rendered-buildings]').getAttribute('data-rendered-buildings')), { timeout: 15000 }).toBeGreaterThan(0);
  await page.getByRole('button', { name: 'View entire city', exact: true }).click();
  await expect(page.getByText('Zoom in to explore buildings and street details')).toBeVisible({ timeout: 15000 });
  await page.getByRole('button', { name: 'Reset city view', exact: true }).click();
  await expect.poll(async () => Number(await page.locator('[data-rendered-buildings]').getAttribute('data-rendered-buildings')), { timeout: 30000 }).toBeGreaterThan(0);
  expect(paginatedRequests).toBe(0);
  expect(errors).toEqual([]);
});
