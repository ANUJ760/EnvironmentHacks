import { execSync } from 'child_process';
import { existsSync } from 'fs';
import { resolve } from 'path';

const schemaPath = resolve(process.cwd(), '../backend/openapi.json');
const outputPath = resolve(process.cwd(), 'src/lib/api-types.ts');
const reexportPath = resolve(process.cwd(), 'src/lib/api/api-types.ts');

if (!existsSync(schemaPath)) {
  console.error(`Error: Backend OpenAPI spec not found at ${schemaPath}`);
  process.exit(1);
}

console.log(`Generating types from ${schemaPath} -> ${outputPath}`);
execSync(`npx openapi-typescript "${schemaPath}" -o "${outputPath}"`, { stdio: 'inherit' });

console.log('Types generated successfully.');
