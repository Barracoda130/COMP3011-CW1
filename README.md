# COMP3011-CW1

Backend-first coursework scaffold with a structure that supports adding a Vue.js frontend later.

## Project layout

- `backend/` FastAPI backend (versioned API, CORS-ready, test scaffold)
- `frontend/` reserved folder for future Vue.js app

## Quick start (backend)

1. Open a terminal in `backend/`
2. Install dependencies:
	- `pip install -r requirements.txt`
3. Create env file:
	- `copy .env.example .env`
4. Run API:
	- `uvicorn app.main:app --reload`

Useful URLs:

- API root: `http://127.0.0.1:8000/`
- Swagger docs: `http://127.0.0.1:8000/docs`
- Health check: `http://127.0.0.1:8000/api/v1/health`