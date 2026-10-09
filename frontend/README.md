This directory is the generated TypeScript API contract only. No interactive frontend is included.
Run `make contracts` after API schema changes. Consume `paths` and `components` from
`src/lib/api-types.ts`. Mutable endpoints require a backend-issued bearer access token.
Keep every AWS credential, OpenAQ key and database URI out of browser configuration.
Only `NEXT_PUBLIC_API_BASE_URL` belongs in the browser environment.
