import { test, expect } from '@playwright/test';
test.use({ viewport: { width: 1680, height: 1080 } });

test('public planner retires authentication and duplicate lab without exposing privileged APIs', async ({ request, page }) => {
  expect((await request.get('/api/auth/session')).status()).toBe(410);
  expect((await request.post('/api/gateway/v1/scenarios', { data: {} })).status()).toBe(410);
  await page.goto('/explore');
  await expect(page.getByText('Sign In', { exact: true })).toHaveCount(0);
  await expect(page.getByText('Simulate Lab', { exact: true })).toHaveCount(0);
  await expect(page.getByRole('link', { name: 'Open planner' }).first()).toBeVisible();
});

test('real municipal tree selection uses a nearest hit and keeps layout and source evidence', async ({ page, request }) => {
  test.skip(process.env.RUN_LIVE_MAP_TESTS !== '1', 'Requires published Zürich datasets and map tiles.');
  test.setTimeout(120000);
  const city = (await (await request.get('/api/gateway/v1/cities')).json()).find((c: { slug: string }) => c.slug === 'zurich-center');
  const geometry = { type: 'Point', coordinates: [8.541265, 47.373218] };
  const response = await request.post(`/api/gateway/v1/cities/${city.id}/planning-preview`, { data: { selection_type: 'tree', geometry, location: geometry.coordinates, crown_diameter_m: 16 } });
  expect(response.status()).toBe(200);
  const report = await response.json();
  expect(report.geometry_source).toContain('Published municipal tree revision');
  expect(report.provenance.datasets.some((dataset: { kind: string }) => dataset.kind === 'municipal_trees')).toBe(true);
  expect(report.inventory.tree_inventory_complete).toBe(false);
  await page.goto(`/city/${city.id}/simulate`);
  await expect(page).toHaveURL(new RegExp(`/city/${city.id}$`));
  await expect.poll(async () => Number(await page.locator('[data-rendered-trees]').getAttribute('data-rendered-trees')), { timeout: 60000 }).toBeGreaterThan(0);
  const canvas = page.locator('canvas');
  const box = (await canvas.boundingBox())!;
  const targets = JSON.parse((await page.locator('[data-tree-targets]').getAttribute('data-tree-targets'))!) as { x: number; y: number }[];
  let selected = false;
  for (const target of targets) {
    if (target.x < box.width * .35 || target.x > box.width * .75 || target.y < box.height * .2 || target.y > box.height * .7) continue;
    await page.mouse.move(box.x + target.x + 6, box.y + target.y);
    await page.mouse.click(box.x + target.x + 6, box.y + target.y);
    selected = await page.locator('[data-planning-panel="tree"]').isVisible();
    if (selected) break;
  }
  expect(selected).toBe(true);
  await expect(page.locator('[data-impact-metric="carbon"]')).toBeVisible({ timeout: 30000 });
  await expect(page.getByRole('region', { name: 'Highlighted elements' })).toContainText(/tree/i);
  await expect(page.getByRole('region', { name: 'Results summary' })).toContainText('Within the published study area');
  await expect(page.getByRole('button', { name: /Run simulation/i })).toHaveCount(0);
});
