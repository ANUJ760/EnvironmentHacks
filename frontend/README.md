# EcoTwin Frontend Application

Public, lightweight city-change planner for **EcoTwin**. No sign-in required.

## Tech Stack
- **Framework**: Next.js 15 (App Router, Standalone SSR)
- **UI & Components**: React 19, Tailwind CSS, Lucide icons
- **City Rendering**: lightweight MapLibre illustrated 2D / aerial imagery
- **Data & State**: TanStack Query v5, Zustand v5, Zod
- **API Contract**: openapi-typescript & openapi-fetch (strictly synced with `backend/openapi.json`)
- **Access**: public read-only planning; retired account-owned API operations are not exposed by the gateway
- **Testing**: Vitest, React Testing Library, Playwright, axe-core

## Local Development Quickstart

1. Configure environment:
   ```bash
   cp .env.example .env.local
   ```
2. Install dependencies and run:
   ```bash
   npm ci
   npm run api:generate
   npm run dev
   ```
   Open [http://localhost:3000](http://localhost:3000) in your browser.

## Available Scripts
- `npm run dev`: Launch local development server on port 3000
- `npm run build`: Compile standalone production server
- `npm run start`: Launch compiled standalone server
- `npm run lint`: Run ESLint checks (0 warnings permitted)
- `npm run typecheck`: Run TypeScript compilation check (`tsc --noEmit`)
- `npm run test`: Run Vitest unit, component, and contract tests
- `npm run test:e2e`: Run Playwright end-to-end tests
- `npm run api:generate`: Generate TypeScript interfaces from backend OpenAPI spec
- `npm run api:check`: Ensure generated types have zero drift against backend spec

## Interactive removal impacts

Click a feature or any ground location, or use **Draw area** for a custom polygon.
The single planner compares clearing, filling or grass conversion under the same
conditions: runoff, energy, operational waste, demolition materials, vegetation and
regional air context. Editable assumptions and evidence limits are separate from
the main cards. Export a JSON report for offline replay. Optional local Ollama
organizes verified findings only.

[Small architecture guide and Docker/AWS handoff](../docs/ARCHITECTURE.md).
