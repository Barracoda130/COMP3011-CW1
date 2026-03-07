# Frontend (Vue 3 + Vite)

This frontend maps directly to the current backend endpoints.

## Setup

1. Install dependencies:
	- `npm install`
2. Copy env file:
	- `copy .env.example .env`
3. Start dev server:
	- `npm run dev`

App URL: `http://127.0.0.1:5173`

## API endpoint page mapping

- `/health` page -> `GET /api/v1/health`
- `/auth/register` page -> `POST /api/v1/auth/register`
- `/auth/login` page -> `POST /api/v1/auth/login`
- `/auth/me` page -> `GET /api/v1/auth/me`
- `/recipes` page -> `GET /api/v1/recipes`, `POST /api/v1/recipes`
- `/recipes/:id` page -> `GET /api/v1/recipes/{id}`, `PUT /api/v1/recipes/{id}`,
  `DELETE /api/v1/recipes/{id}`, `POST /api/v1/recipes/{id}/ratings`

## Notes

- Login token is stored in local storage and added as Bearer auth automatically.
- Owner-only backend checks still apply for update/delete endpoints.
