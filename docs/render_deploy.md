# Render Deployment

## Service shape
Two Render services defined in one Blueprint ([render.yaml](/render.yaml)):

- **Backend** — `mathhomeworkautomarker-backend`, `runtime: docker`, plan `starter`, region `singapore`.
  Built from the repo-root [Dockerfile](/Dockerfile).
- **Frontend** — `mathhomeworkautomarker-frontend`, `runtime: static`, built from `frontend/`.
- **Database** — `mathhomeworkautomarker-db`, plan `basic-256mb`, region `singapore`.

## Why the backend is Docker, not the Python runtime

The active grading pipeline converts the teacher's `.docx` answer file to PDF
using LibreOffice (`find_soffice` / `convert_docx_to_pdf` in `file_processor.py`)
before rendering pages to images for the vision model. Render's native Python
runtime has no way to install system (apt) packages, and LibreOffice is not a
pip package. Switching the backend to `runtime: docker` lets us install it
ourselves.

The [Dockerfile](/Dockerfile) is `python:3.11-slim` plus two apt packages:

- `libreoffice-writer` — provides `soffice` for the docx→PDF conversion.
- `fonts-noto-cjk` — without CJK fonts, LibreOffice renders Chinese characters
  in teacher answer docs as empty boxes ("tofu") in the converted PDF, which
  breaks grading. Noto CJK covers the Chinese text these documents contain.

`requirements.txt` is copied and installed before the rest of the source so
that Docker layer caching skips the (slow) pip install on source-only changes.
`CMD` uses shell form so `${PORT:-8000}` is expanded at container start —
Render injects `PORT` at runtime and it isn't known at build time.

Because the app now ships as a container, `render.yaml` has no `buildCommand`
or `startCommand` for the backend — the image build and its `CMD` replace
both. `preDeployCommand: alembic upgrade head` and `healthCheckPath: /health`
are unchanged.

## Why the frontend is a static site

`frontend/` previously had no Render config at all. It's a Vite + React SPA
with client-side routing (`react-router`), so the static site definition adds
a catch-all rewrite:

```yaml
routes:
  - type: rewrite
    source: /*
    destination: /index.html
```

Without this rewrite, a direct hit on a deep link — e.g. a student opening a
course-join link at `/student/join/:joinToken` — would 404 at Render's static
file server before React Router ever loads. The rewrite serves `index.html`
for any path so the SPA router can take over.

## Dockerfile and .dockerignore

- [Dockerfile](/Dockerfile) — see above.
- [.dockerignore](/.dockerignore) — keeps the build context small and avoids
  invalidating the pip-install cache layer on unrelated changes. Excludes the
  frontend app (built separately, as a static site), tests, docs, local data,
  and editor/tooling directories. `alembic/` and `alembic.ini` are **not**
  excluded — `preDeployCommand: alembic upgrade head` runs inside the built
  image and needs them.

## Commands

### Backend
- Build: handled by Docker (`dockerfilePath: ./Dockerfile`), no `buildCommand`.
- Pre-deploy: `alembic upgrade head`
- Start: the Dockerfile's `CMD` — `uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips '*'`
- Health check path: `/health`

### Frontend
- Build: `cd frontend && npm ci && npm run build`
- Publish path: `frontend/dist`

## Runtime notes
- The real FastAPI app import path is `main:app`.
- The app does not auto-load `.env` files. Render and local runs must provide real environment variables.
- Runtime file storage is controlled by `APP_DATA_DIR`.
- The Blueprint mounts a persistent disk at `/var/data/mathhomeworkautomarker` and points `APP_DATA_DIR` there.
- Student PDF rendering uses `PyMuPDF` (no system Poppler needed for that step); the teacher-side docx→PDF step is what needs LibreOffice in the Docker image.

## Environment variables

### Required in Render
- `DATABASE_URL`
  Blueprint-managed via `fromDatabase.connectionString`.
- `AUTH_SECRET_KEY`
  Blueprint-managed via `generateValue: true`.
- `GRADING_PROVIDER`
  Set to `doubao` in the Blueprint. Selects which vision model backend
  `grading_provider.py` calls. Can be changed to `qwen` (see below) as a
  fallback without a code change.
- `DOUBAO_VISION_MODEL`
  Set to `doubao-seed-2-1-turbo-260628` in the Blueprint.
- `ARK_API_KEY`
  Required when `GRADING_PROVIDER=doubao`. Must be entered manually
  (`sync: false`) — get it from the Volcano Engine 方舟 (Ark) console under
  API keys for the account with access to the Doubao vision model.
- `FRONTEND_BASE_URL`
  Set explicitly in the Blueprint to
  `https://mathhomeworkautomarker-frontend.onrender.com`. Used to generate
  student join links and as the CORS fallback origin.
- `CORS_ALLOW_ORIGINS`
  Set explicitly in the Blueprint to the same frontend URL. `*` is
  intentionally rejected.

### Optional / fallback in Render
- `DASHSCOPE_API_KEY`
  Only needed if `GRADING_PROVIDER` is switched to `qwen` (`sync: false`,
  kept in the Blueprint as a ready-made fallback slot). If you fail over to
  Qwen, also set `QWEN_VISION_MODEL` to a vision-capable DashScope model.
- `QWEN_PLUS_MODEL`
- `DASHSCOPE_BASE_URL`
- `ACCESS_TOKEN_EXPIRE_MINUTES`
- `AUTH_ALGORITHM`
- `PASSWORD_HASH_ITERATIONS`
- `SQLALCHEMY_ECHO`

### Frontend
- `VITE_API_BASE_URL`
  Set explicitly in the Blueprint to
  `https://mathhomeworkautomarker-backend.onrender.com`. Baked into the
  static build at build time (Vite env vars are compile-time, not runtime).

### Local-only / test-only
- `HOST`
- `PORT`
- `UVICORN_RELOAD`
- `RUN_EXTERNAL_SMOKE`
- Tests inject their own `DATABASE_URL`, `AUTH_SECRET_KEY`, and `FRONTEND_BASE_URL` in `tests/conftest.py`.

## Cloud Postgres
- The app requires `DATABASE_URL` at import time.
- SQLAlchemy is initialized with `pool_pre_ping=True` for safer long-lived cloud connections.
- The repo includes `psycopg2-binary`, so `postgresql://...` URLs work on Render.
- Database migrations are handled by `alembic upgrade head` in `preDeployCommand`.

## CORS and frontend setup
- If `CORS_ALLOW_ORIGINS` is set, the backend uses that explicit list.
- If `CORS_ALLOW_ORIGINS` is not set, the backend falls back to the origin portion of `FRONTEND_BASE_URL`.
- If neither is set, the backend falls back to local development origins only.
- `*` is intentionally rejected for `CORS_ALLOW_ORIGINS`.

## First deploy via Blueprint
1. Push this repository to the Git branch you want Render to deploy.
2. In Render, choose `New +` -> `Blueprint` and select this repo.
3. During the initial Blueprint creation flow, fill in the `sync: false` secrets:
   - `ARK_API_KEY`
   - `DASHSCOPE_API_KEY` (optional, only if you plan to use the `qwen` fallback)
4. Confirm the backend plan remains `starter` — `preDeployCommand` requires a
   paid web service plan, and `starter` is the cheapest one that qualifies —
   and the Docker build completes — the first build is slower than a plain
   Python build because it installs LibreOffice and CJK fonts.
5. Wait for both services (backend, frontend) to finish deploying.

### Onrender subdomain caveat

`render.yaml` pre-writes both services' URLs into each other's env vars
(`FRONTEND_BASE_URL`, `CORS_ALLOW_ORIGINS`, `VITE_API_BASE_URL`) assuming the
service names in the Blueprint are available. If either
`mathhomeworkautomarker-backend` or `mathhomeworkautomarker-frontend` is
already taken on Render, it will suffix your actual service with a random
string (e.g. `mathhomeworkautomarker-frontend-ab12`). If that happens, go back
and update all three places to match the real assigned URLs, then redeploy:

1. Backend env var `FRONTEND_BASE_URL`
2. Backend env var `CORS_ALLOW_ORIGINS`
3. Frontend env var `VITE_API_BASE_URL` (requires a rebuild, since it's baked in at build time)

## Verification after deploy
1. Open `https://<your-backend-service>.onrender.com/health`
2. Expect HTTP `200` with body:
   `{"status":"ok"}`
3. Check Render logs to confirm:
   - the Docker image built successfully (LibreOffice + fonts installed)
   - `alembic upgrade head` succeeded
   - uvicorn started on `$PORT`
4. Open the frontend static site URL and confirm it loads and can reach the
   backend (no CORS errors in the browser console).
5. Run one real grading pass end-to-end: log in as a teacher, upload an
   answer file and a student homework submission, and confirm grading
   completes with a result instead of `failed_grading`. This exercises the
   LibreOffice conversion path that the Docker switch exists for.

## Cost
- Backend: `starter` plan (Docker web service).
- Database: `basic-256mb` plan.
- Frontend: Render static sites are free — no plan cost.

## Remaining dashboard-only work
- Add or update any future `sync: false` secrets manually in the Render Dashboard, because Blueprint sync ignores new `sync: false` values after the initial creation flow.
- If you want a custom domain, configure it separately in the Render Dashboard after the first successful deploy.
