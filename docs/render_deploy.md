# Render Deployment

## Service shape
- Render service type: Python Web Service
- Root directory: repo root (`/Users/erichuang/Desktop/MathHomeworkAutomarker`)
- Blueprint file: [render.yaml](/Users/erichuang/Desktop/MathHomeworkAutomarker/render.yaml)
- Web plan in Blueprint: `starter`
- Postgres plan in Blueprint: `basic-256mb`
- Region in Blueprint: `singapore`

## Commands
- Build command: `pip install -r requirements.txt`
- Pre-deploy command: `alembic upgrade head`
- Start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
- Health check path: `/health`

## Runtime notes
- The real FastAPI app import path is `main:app`.
- The app does not auto-load `.env` files. Render and local runs must provide real environment variables.
- Runtime file storage is controlled by `APP_DATA_DIR`.
- The Blueprint mounts a persistent disk at `/var/data/mathhomeworkautomarker` and points `APP_DATA_DIR` there.
- Student PDF rendering now uses `PyMuPDF`, so Render does not need system-level Poppler packages for the grading pipeline.

## Environment variables

### Required in Render
- `DATABASE_URL`
  Blueprint-managed via `fromDatabase.connectionString`.
- `AUTH_SECRET_KEY`
  Blueprint-managed via `generateValue: true`.
- `DASHSCOPE_API_KEY`
  Must be entered manually during the initial Blueprint creation flow because it uses `sync: false`.

### Strongly recommended in Render
- `FRONTEND_BASE_URL`
  Used to generate student join links. Example: `https://your-frontend.example.com`
- `CORS_ALLOW_ORIGINS`
  Comma-separated explicit frontend origins. Example:
  `https://your-frontend.example.com,https://admin.example.com`

### Optional in Render
- `QWEN_VISION_MODEL`
  Production grading usually should set this to a vision-capable DashScope model instead of relying on the code default.
- `QWEN_PLUS_MODEL`
- `DASHSCOPE_BASE_URL`
- `ACCESS_TOKEN_EXPIRE_MINUTES`
- `AUTH_ALGORITHM`
- `PASSWORD_HASH_ITERATIONS`
- `SQLALCHEMY_ECHO`

### Local-only / test-only
- `HOST`
- `PORT`
- `UVICORN_RELOAD`
- `RUN_EXTERNAL_SMOKE`
- Tests inject their own `DATABASE_URL`, `AUTH_SECRET_KEY`, and `FRONTEND_BASE_URL` in `tests/conftest.py`.

## Cloud Postgres
- The app requires `DATABASE_URL` at import time.
- SQLAlchemy is now initialized with `pool_pre_ping=True` for safer long-lived cloud connections.
- The repo now includes `psycopg2-binary`, so `postgresql://...` URLs can start successfully on Render.
- Database migrations are handled by `alembic upgrade head` in `preDeployCommand`.

## CORS and frontend setup
- If `CORS_ALLOW_ORIGINS` is set, the backend uses that explicit list.
- If `CORS_ALLOW_ORIGINS` is not set, the backend falls back to the origin portion of `FRONTEND_BASE_URL`.
- If neither is set, the backend falls back to local development origins only.
- `*` is intentionally rejected for `CORS_ALLOW_ORIGINS`.

## Manual Render steps
1. Push this repository to the Git branch you want Render to deploy.
2. In Render, choose `New +` -> `Blueprint` and select this repo.
3. During the initial Blueprint creation flow, fill in:
   - `DASHSCOPE_API_KEY`
   - `FRONTEND_BASE_URL`
   - `CORS_ALLOW_ORIGINS`
4. Confirm the web service plan remains `starter`, because `preDeployCommand` is intended for the paid service path used here.
5. Wait for the first deploy to complete and confirm the migration step succeeds.

## Verification after deploy
1. Open `https://<your-render-service>.onrender.com/health`
2. Expect HTTP `200` with body:
   `{"status":"ok"}`
3. Check Render logs to confirm:
   - build completed
   - `alembic upgrade head` succeeded
   - uvicorn started on `$PORT`
4. From the frontend origin, confirm the backend responds with the expected CORS headers.

## Remaining dashboard-only work
- Add or update any future `sync: false` secrets manually in the Render Dashboard, because Blueprint sync ignores new `sync: false` values after the initial creation flow.
- If you want a custom domain, configure it separately in the Render Dashboard after the first successful deploy.
