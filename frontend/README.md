# Frontend

React + TypeScript + Vite UI for the Intrusion Detection System — an upload
flow (`src/pages/UploadPage.tsx`) and a live-camera flow
(`src/pages/LivePage.tsx`), both talking to the FastAPI backend via
`src/api/client.ts`.

See the [repo root README](../README.md) for the full project overview and
setup instructions. Quick reference for this package:

```bash
npm install
npm run dev      # http://localhost:5173, talks to VITE_API_URL (default http://localhost:8000)
npm run lint      # oxlint
npm run build     # tsc -b && vite build
```
