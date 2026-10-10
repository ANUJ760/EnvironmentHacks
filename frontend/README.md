# EcoTwin Frontend Application

Production-oriented user-facing web application and scenario simulation lab for **EcoTwin**.

## Tech Stack
- **Framework**: Next.js 15 (App Router, Standalone SSR)
- **UI & Components**: React 19, Tailwind CSS, Lucide icons
- **2D Map Rendering**: PixiJS v8 (WebGL with accessible DOM/SVG fallback)
- **Data & State**: TanStack Query v5, Zustand v5, Zod
- **API Contract**: openapi-typescript & openapi-fetch (strictly synced with `backend/openapi.json`)
- **Authentication**: NextAuth.js v4 (Cognito OIDC in production, local dev token injection in development)
- **Testing**: Vitest, React Testing Library, Playwright, axe-core

## Local Development Quickstart

1. Configure environment:
   ```bash
   cp .env.example .env.local
   ```
2. Generate an authenticated developer token using the backend CLI:
   ```bash
   # From repository root
   uv run ecotwin auth issue-dev-token --subject local-developer --minutes 120
   ```
   Add the token to `frontend/.env.local` as `ECOTWIN_DEV_BEARER_TOKEN`.

3. Install dependencies and run:
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
