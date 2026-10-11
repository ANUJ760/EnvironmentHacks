import { readFileSync, existsSync } from 'fs';
import { resolve } from 'path';

const schemaPath = resolve(process.cwd(), '../backend/openapi.json');

if (!existsSync(schemaPath)) {
  console.error(`Error: Backend OpenAPI spec not found at ${schemaPath}`);
  process.exit(1);
}

try {
  const content = readFileSync(schemaPath, 'utf-8');
  const schema = JSON.parse(content);

  const requiredPaths = [
    '/v1/cities',
    '/v1/models',
    '/v1/scenarios',
    '/v1/jobs/{identifier}',
    '/v1/results/{identifier}',
    '/readyz',
  ];

  const paths = Object.keys(schema.paths || {});
  const missing = requiredPaths.filter(p => !paths.includes(p));

  if (missing.length > 0) {
    console.error(`OpenAPI spec is missing required paths: ${missing.join(', ')}`);
    process.exit(1);
  }

  console.log(`OpenAPI spec verified successfully: ${paths.length} endpoints defined.`);
} catch (err) {
  console.error(`Failed to verify OpenAPI schema:`, err);
  process.exit(1);
}
