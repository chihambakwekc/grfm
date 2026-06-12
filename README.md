# GRFM

Clean full-stack architecture scaffold for the GRFM system.

Stack:
- Django + Django REST Framework
- Simple JWT
- PostgreSQL
- Redis
- Vite + React + TypeScript
- shadcn-style UI components
- nginx reverse proxy
- Docker and production Docker Compose

Portal boundaries:
- Public frontend portal: `frontend/src/portals/public`
- Internal frontend portal: `frontend/src/portals/internal`
- Public backend app: `backend/apps/public_portal`
- Internal backend app: `backend/apps/internal_portal`
- Shared backend foundation: `backend/apps/core`

Local ports:
- Frontend: http://localhost:5176
- Backend: http://localhost:8003
- Public portal through nginx: http://localhost:1516
- Internal admin portal through nginx: http://localhost:1516/login
- Postgres: localhost:5436
- Redis: localhost:6382

## Start

```powershell
docker compose up --build
```

## Production config

```powershell
docker compose --env-file .env.prod -f docker-compose.prod.yml up --build -d
```

## First backend setup

```powershell
docker compose exec backend python manage.py migrate
docker compose exec backend python manage.py createsuperuser
```

## Health

- API: `/api/health/`
- Frontend proxy: `http://localhost:5176/api/health/`

## Public Portal Translation Workflow

The public portal uses `i18next` and `react-i18next`.

Language files live in:

- `frontend/src/i18n/locales/en.json`
- `frontend/src/i18n/locales/sn.json`
- `frontend/src/i18n/locales/nd.json`

English (`en.json`) is the master language file. Shona (`sn.json`) and Ndebele (`nd.json`) must always contain the same keys. Until reviewed translations are available, Shona and Ndebele values may use the English fallback text.

When adding public-facing text:

1. Add the new key and English text to `frontend/src/i18n/locales/en.json`.
2. Use `t("key.name")` in the public React component instead of hardcoding text.
3. Run:

```powershell
cd frontend
npm run i18n:check
```

4. If keys are missing from Shona or Ndebele, run:

```powershell
npm run i18n:sync
```

`npm run i18n:sync` uses `en.json` as the master, adds missing keys to `sn.json` and `nd.json`, preserves existing translated values, and does not overwrite reviewed translations.

Rules:

- Do not translate dynamic database values yet, such as names, provinces, districts, case numbers, uploaded notes, or submitted complaint descriptions.
- Programme names can remain English until controlled programme translations are introduced.
- The admin dashboard remains English for now, but the same i18n structure can be used later.
- Missing Shona or Ndebele values fall back to English.
