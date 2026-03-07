# Backend (FastAPI)

## Run locally

1. Create and activate a virtual environment.
2. Install dependencies:
   - `pip install -r requirements.txt`
3. Copy environment file:
   - `copy .env.example .env`
4. Start API:
   - `uvicorn app.main:app --reload`

API will run at `http://127.0.0.1:8000` and docs at `http://127.0.0.1:8000/docs`.

## Why this structure works for a future Vue frontend

- Versioned API prefix: `/api/v1`
- CORS origins include Vue dev server defaults (`5173`)
- Clear module separation (`api`, `schemas`, `services`, `db`)
- Ready for token auth and persistent database models
