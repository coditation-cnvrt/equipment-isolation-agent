# Equipment Isolation Frontend

React/Vite interface for selecting CNVRT and UniGraph context, viewing the HILT drawing, launching advisory isolation-agent runs, and reopening persisted results without another Gemini call.

## Local development

```bash
cp .env.example .env.local
pnpm install
pnpm dev
```

The frontend installs `@coditation-cnvrt/p360-hitl-viewer` from the private GitHub Packages registry. Configure the `@coditation-cnvrt` registry in npm and provide a `GITHUB_PACKAGES_TOKEN` with `read:packages` before running `pnpm install`.

Set `VITE_APP_SERVER_BASE_URL`, `VITE_APP_OAUTH_CLIENT_ID`, and `VITE_APP_OAUTH_CLIENT_SECRET` in `.env.local` using the existing shared CNVRT password-grant client configured for UniGraph. Never commit populated credentials. The frontend authentication flow will obtain the signed-in user's CNVRT token and send it as bearer authorization to the Equipment Isolation API.

The Equipment Isolation API defaults to `http://localhost:8088`; override it with `VITE_API_BASE_URL`.

## Checks

```bash
pnpm build
pnpm lint
```
