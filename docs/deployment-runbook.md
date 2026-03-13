# Deployment Runbook

This runbook describes environment setup, migration, optional seed, and startup for local or server deployment.

## 1. Environment Variables

Backend (`backend/.env`):

- `DATABASE_URL` (deployment: PostgreSQL URL, e.g. `postgresql+psycopg://...`)
- `BACKEND_CORS_ORIGINS` (JSON list or comma-separated origins)
- `SECRET_KEY` (required in non-dev deployments)
- `ALGORITHM` (default `HS256`)
- `ACCESS_TOKEN_EXPIRE_MINUTES` (default `1440`)
- `THEMEALDB_BASE_URL` (default `https://www.themealdb.com/api/json/v1/1`)

Frontend (`frontend/.env` if needed):

- `VITE_API_BASE_URL` (for non-local backend URL)

## 2. Backend Install

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

## 3. Database Migration

Run migrations before starting production workload:

```powershell
cd backend
.\.venv\Scripts\python.exe -m alembic upgrade head
```

## 4. Optional Seed / Baseline Data

Current setup does not require mandatory seed scripts.

- If you want demo data, create recipes through API/UI after startup.
- For PostgreSQL environments, rely on provider backups/snapshots before bulk operations.

## 5. Start Services

Backend:

```powershell
cd backend
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Frontend:

```powershell
cd frontend
npm.cmd install
npm.cmd run dev
```

Production/static build output:

```powershell
cd frontend
npm.cmd run build
```

## 6. Validation Checklist

- `GET /api/v1/health` returns `200`.
- Login/register works.
- Discover endpoint returns local/external recipes.
- Suggested endpoint returns formula and reasons.
- Weekly plan generate/current/select endpoints work for authenticated users.

## 7. Rollback Notes

- PostgreSQL rollback: restore provider snapshot/backup or rollback schema migration.
- SQLite local rollback: restore backup copy of `backend/meal_api.db`.
- Migration rollback (if needed):

```powershell
cd backend
.\.venv\Scripts\python.exe -m alembic downgrade -1
```
