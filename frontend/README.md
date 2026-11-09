# Frontend

Vite + React + TypeScript. The status page calls `GET /api/health`; in dev the
Vite server proxies `/api` to the backend.

```sh
npm ci
npm run dev        # http://localhost:5173
npm run lint       # oxlint
npm run typecheck  # tsc -b
npm test           # vitest (jsdom + Testing Library)
npm run build
```

The proxy target defaults to `http://localhost:8000`. If the backend runs on
another port (for example `BACKEND_HOST_PORT=8001` in the root `.env`), set
`API_PROXY_TARGET` in `frontend/.env.local` or in the shell; see `.env.example`.
