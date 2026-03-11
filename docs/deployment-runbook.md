# Deployment Runbook

This runbook describes environment setup, migration, optional baseline data, and startup for local or server deployment.

## 1. Environment Variables

Backend (`backend/.env`):

- `DATABASE_URL` (default: `sqlite:///.../backend/meal_api.db`)
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

- If you want demo data, create recipes through the API/UI after startup.
- Keep `meal_api.db` backed up before bulk data operations.

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
npm.cmd run build
npm.cmd run dev
```

## 6. Validation Checklist

- `GET /api/v1/health` returns `200`.
- Login/register works.
- Discover endpoint returns local and TheMealDB recipes.
- Suggested endpoint returns formula and explainability reasons.
- Weekly Plan generation endpoint works: `POST /api/v1/users/me/weekly-plan/generate`.
- Weekly Plan retrieval endpoint works: `GET /api/v1/users/me/weekly-plan/current`.
- Weekly Plan selection endpoint works: `POST /api/v1/users/me/weekly-plan/current/select`.
- Analytics summary endpoint works: `GET /api/v1/users/me/analytics/summary`.
- Weekly-plan analytics endpoint works: `GET /api/v1/users/me/analytics/weekly-plan`.
- Analytics recommendation explanation endpoint works: `GET /api/v1/users/me/analytics/recommendation-explanation-summary`.
- Taste profile endpoint works: `GET /api/v1/users/me/taste-profile`.

## 7. Rollback Notes

- SQLite rollback: restore backup copy of `backend/meal_api.db`.
- Migration rollback (if needed):

```powershell
cd backend
.\.venv\Scripts\python.exe -m alembic downgrade -1
```

## 8. Documentation Alignment

- Repository overview: `README.md`
- Architecture and recommendation flow: `docs/architecture-and-recommendation.md`
- API PDF artifact: `docs/api-documentation.pdf`
