# Deployment Guide

> **Synthetic data only — no PHI.** Every patient, provider, facility, and payer record is programmatically generated. All organization names are fictional and all NPIs are fake. This is a **portfolio and educational project — not a real healthcare deployment** and not medical, billing, or financial advice.

This document describes how to deploy the two-service application to [Render](https://render.com) using the committed Blueprint at [`render.yaml`](../render.yaml). The [main README](../README.md) has a summary; use this file for the exact procedure, environment variables, troubleshooting, and free-tier caveats.

## Hosted architecture

```
Browser  →  Render Static Site  →  FastAPI Web Service  →  In-memory synthetic CSV dataset
             (Vite build,              (Python + uvicorn,        (generated at build time
              VITE_API_URL              CSV mode by default,       by etl/run_pipeline.py)
              baked in)                 CORS from FRONTEND_URL)
```

- The frontend calls the backend at the origin embedded in `VITE_API_URL` (build-time variable).
- The backend accepts requests from the origin listed in `FRONTEND_URL` (runtime variable used to build the CORS allowlist in [`api/main.py`](../api/main.py)).
- The dataset is generated during the backend build step — no external data source is required.
- The API runs in **CSV mode** unless a `DATABASE_URL` is deliberately configured. The Render portfolio deployment does **not** use PostgreSQL.
- No real patient records or PHI are used, transmitted, or stored.

## Services defined in `render.yaml`

| Service | Type | Purpose |
|---|---|---|
| `healthcare-rcm-api` | Web Service (Python) | FastAPI + uvicorn; builds the synthetic dataset, runs validation, serves the API |
| `healthcare-rcm-command-center` | Static Site | Vite production build of the React dashboard, published from `frontend/dist` |

Both services are on the **Render free plan** with `autoDeployTrigger: commit` — pushing to `main` triggers a redeploy of the changed service (`rootDir` scopes the frontend to `frontend/`).

## Step-by-step deployment

1. **Push the deployment commits to GitHub.** The Blueprint (`render.yaml`) and the two `.env.example` files must be on the branch Render syncs from (typically `main`).
2. **Open Render** at [dashboard.render.com](https://dashboard.render.com) and sign in.
3. Choose **New → Blueprint**.
4. **Connect** the GitHub repository: `Darshita-dp/Healthcare-Revenue-Cycle-Command-Center`.
5. Render parses `render.yaml` and shows two services: `healthcare-rcm-api` and `healthcare-rcm-command-center`. Review each service's build command, start command, and detected environment variables.
6. Render prompts for the two `sync: false` variables. Enter them as predicted from the service names (adjust after step 10 if Render assigns a suffix):

   | Service | Variable | Value |
   |---|---|---|
   | `healthcare-rcm-api` | `FRONTEND_URL` | `https://healthcare-rcm-command-center.onrender.com` |
   | `healthcare-rcm-command-center` | `VITE_API_URL` | `https://healthcare-rcm-api.onrender.com` |

   Enter each origin **with `https://`**, **no path**, and **no trailing slash**.
7. Click **Apply**. Render creates both services and begins the first deploy.
8. Wait for both services to reach **Live** status.
   - The backend build runs `pip install -r requirements.txt`, then the ETL pipeline, then the 46-check validation, then follow-up-task generation. On failure the deploy halts — check the build log.
   - The frontend build runs `npm ci && npm run build` inside `frontend/`.
9. **Verify** in a browser:
   - Backend `/health` returns `{"status":"ok","mode":"csv"}`
   - Backend `/docs` shows Swagger UI with all endpoints
   - Frontend homepage renders the Command Center with real KPIs
   - Direct routes work: `/claims`, `/claims/CLM-003896`, `/payers`, `/tasks`, `/about` (thanks to the SPA rewrite in `render.yaml`)
10. **If Render assigned a hostname suffix** (because a name was unavailable), the actual public URL will differ from the prediction in step 6. Update both `FRONTEND_URL` and `VITE_API_URL` in the Render dashboard to the actual URLs.
11. **After changing `VITE_API_URL`, redeploy the frontend manually** (Manual Deploy → Deploy latest commit in the static site's dashboard). Vite embeds `VITE_API_URL` at *build time*, so the new value only takes effect on a fresh build.

## Environment variables

### Backend (`healthcare-rcm-api`)

**`FRONTEND_URL`** — controls the CORS allowlist in `api/main.py`.
- Full origin including scheme, e.g. `https://healthcare-rcm-command-center.onrender.com`.
- No path, no trailing slash (a trailing slash is stripped in code, but leaving it off matches how browsers report the `Origin` header).
- **Comma-separated origins are supported** — the backend splits on `,` and normalizes each entry — but only add extras if you actually need them. Wildcards (`*`) are intentionally not supported.
- Local development origins (`http://localhost:5173`, `http://127.0.0.1:5173`, plus the Vite `:4173` preview) are always allowed automatically; you do not need to add them here.
- A wrong value shows up as a **browser CORS error** on the frontend — the request is refused by the browser, not the server.

**`PYTHON_VERSION`** — pinned to `3.11.15` in `render.yaml`; leave as-is unless you have a reason to bump it.

**`DATABASE_URL`** *(optional)* — set only if you deliberately want PostgreSQL mode. The Render portfolio deployment does **not** need this; the API falls back to CSV mode when it is unset. Do not provision a Render Postgres just to run this project.

### Frontend (`healthcare-rcm-command-center`)

**`VITE_API_URL`** — the full backend origin the frontend calls.
- Full origin including scheme, e.g. `https://healthcare-rcm-api.onrender.com`.
- No trailing slash (the client trims one anyway).
- **Embedded at build time** — Vite bakes the value into `dist/assets/*.js`. Changing it requires a new build (Manual Deploy on Render).
- **May remain unset during local development** because the Vite dev server proxies `/api` and `/health` to `http://localhost:8000` (see [`frontend/vite.config.ts`](../frontend/vite.config.ts)).

Both `.env.example` files ([root](../.env.example), [frontend](../frontend/.env.example)) document these variables inline.

## Free-tier behavior

The Render free plan powers down web services when they have been idle. What that means in practice:

- The **first request after a period of inactivity is slower** while the service wakes up.
- The frontend already shows a public-friendly message during that window — *"The demo API is temporarily unavailable. Please try again in a moment. If the app has been idle it may take a few seconds to wake up."*
- **This is not a broken deployment.** Once the service is warm, subsequent requests are fast.
- The frontend static site is not affected — only the backend Web Service sleeps.
- If you need consistent latency for a demo (e.g. a scheduled interview), open `/health` a minute or two beforehand to warm the service.

Exact idle and cold-start timings depend on Render's current free-plan policy; see the [Render pricing documentation](https://render.com/pricing) for current values.

## Troubleshooting

### Browser shows a CORS error

The backend refused the request's origin. Check, in order:

1. Open the backend in the Render dashboard and confirm **`FRONTEND_URL`** is set.
2. It must be the **full origin** (`https://…`) — not a path, not a hostname alone.
3. It must **exactly match the frontend's public URL** — check for suffix mismatches (`-abc123.onrender.com`).
4. **No trailing slash, no path** (the backend normalizes trailing slashes, but a path will not match).
5. **Redeploy the backend** after changing any env var — env-var changes only take effect on the next deploy.
6. As a sanity check, tail the backend's start-up logs: it prints `CORS allowed origins: [...]` on boot.

### Frontend cannot reach the API

The requests fail at the network layer (not CORS — CORS errors mention the origin explicitly).

1. Open the frontend service's env vars and confirm **`VITE_API_URL`** is the current backend URL.
2. Hit `<backend>/health` in a browser tab — expect `{"status":"ok","mode":"csv"}`.
3. Check the backend service status in the Render dashboard — is it Live? Suspended? Failing to start?
4. If you just changed `VITE_API_URL`, **manually redeploy the frontend** — the old value is still embedded in the deployed bundle otherwise.
5. Open the browser's DevTools → Network tab and look at the failing request URL. If the domain looks wrong, the env var is wrong; if it looks right but hangs or 502s, the backend is the problem.

### API fails during startup

The backend build or start crashed. Check the deploy log in the Render dashboard:

1. Did `pip install -r requirements.txt` complete?
2. Did `python etl/run_pipeline.py` write to `data/processed/`?
3. Did `python etl/validate_data.py` print `Validation: 46 passed, 0 failed`? (Non-zero exit halts the deploy.)
4. Did `python automation/generate_followup_tasks.py` finish with `Tasks written: …` and `Payer alerts written: …`?
5. When uvicorn boots, does `api.database` log `Loaded 12 tables from CSV`? If a table is missing, one of the previous steps did not run.

### Direct route returns 404 (e.g. refreshing `/claims/CLM-003896`)

The static site's SPA rewrite is not active. Confirm the frontend service's `render.yaml` block still contains:

```yaml
routes:
  - type: rewrite
    source: /*
    destination: /index.html
```

The `type` must be `rewrite`, not `redirect` — a redirect would change the URL in the browser and break the deep link.

### Slow first load

Expected. The backend is waking from idle on the free plan (see [Free-tier behavior](#free-tier-behavior)). The message the frontend shows is intentional and correct. Wait a few seconds and reload.

## Local development

Deployment does not change how the project runs locally. See the [main README's How to Run section](../README.md#how-to-run):

- Backend at `http://localhost:8000`
- Frontend at `http://localhost:5173` (Vite dev server proxies `/api` and `/health` to the backend)
- No hosted URLs and no environment variables required for the standard local flow
- Copy `.env.example` → `.env` and `frontend/.env.example` → `frontend/.env` only if you want to override the defaults

## Disclaimer

This project uses **synthetic / public-style healthcare data only** and does not contain real patient information. All patient, provider, facility, and payer records are programmatically generated, all organization names are fictional, and all NPI numbers are fake. It is a **portfolio and educational project — not a real healthcare deployment**. This project is not designed, certified, or intended for use with real PHI or in a HIPAA-regulated production environment, and it is not medical, billing, or financial advice. The Power BI layer is documented (measures, page layouts, DAX) but is not deployed as part of the Render setup.
