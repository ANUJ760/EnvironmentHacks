import { existsSync } from 'fs';
import { resolve } from 'path';

const requiredAssets = [
  'public/brand/logo.svg',
  'public/brand/icon.svg',
  'public/sprites/manifest.json',
];

let hasError = false;
for (const asset of requiredAssets) {
  const fullPath = resolve(process.cwd(), asset);
  if (!existsSync(fullPath)) {
    console.warn(`Asset missing: ${asset}`);
    hasError = true;
  }
}

if (hasError) {
  console.log('Some assets missing - ensure sprites and icons are generated/installed.');
} else {
  console.log('Public brand and sprite assets verified.');
}
