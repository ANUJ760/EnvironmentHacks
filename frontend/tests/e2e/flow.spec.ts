import { test, expect } from '@playwright/test';

test.describe('EcoTwin Frontend Journey', () => {
  test('loads home page and navigates to explore cities', async ({ page }) => {
    await page.goto('/');
    await expect(page).toHaveTitle(/EcoTwin/);
    await expect(page.locator('h1')).toContainText('Explore City Boundaries');

    await page.click('text=Explore Registered Cities');
    await expect(page).toHaveURL(/\/explore/);
    await expect(page.locator('h1')).toContainText('Explore City Study Areas');
  });

  test('verifies data methodology page and scientific boundaries', async ({ page }) => {
    await page.goto('/data-methodology');
    await expect(page.locator('h1')).toContainText('Data Methodology & Evidence Policy');
    await expect(page.locator('text=OBSERVED')).toBeVisible();
    await expect(page.locator('text=SCREENING_ESTIMATE')).toBeVisible();
  });

  test('verifies system status page and healthcheck', async ({ page }) => {
    await page.goto('/status');
    await expect(page.locator('h1')).toContainText('System Connectivity Status');
  });
});
