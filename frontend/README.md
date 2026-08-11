# Equipment Isolation Frontend

React/Vite interface for selecting CNVRT and UniGraph context, viewing the HILT drawing, launching advisory isolation-agent runs, and reopening persisted results without another Gemini call.

## Local development

```bash
cp .env.example .env.local
export NODE_AUTH_TOKEN=github_pat_with_read_packages
pnpm install
pnpm dev
```

`NODE_AUTH_TOKEN` must be a GitHub token with `read:packages` access because the HILT viewer is installed from private GitHub Packages. Never commit the token.

Set `VITE_API_AUTH_TOKEN` in `.env.local` because isolation-run status and result endpoints require bearer authentication. The value is embedded in the local browser bundle, so use a read-only developer token and never commit it. Production deployments should inject the authenticated user's token through the hosting application rather than a build-time secret.

The API defaults to `http://localhost:8088`; override it with `VITE_API_BASE_URL`.

## Checks

```bash
pnpm build
pnpm lint
```
