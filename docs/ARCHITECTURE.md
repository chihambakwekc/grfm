# GRFM Architecture

GRFM follows the same full-stack architecture pattern as the source system: Django REST backend, Vite React frontend, PostgreSQL, Redis, Nginx reverse proxy, Docker development setup, and production Compose setup.

## Portal layout

- Public frontend portal: frontend/src/portals/public
- Internal frontend portal: frontend/src/portals/internal
- Public backend app boundary: backend/apps/public_portal
- Internal backend app boundary: backend/apps/internal_portal
- Shared backend foundation remains in backend/apps/core until GRFM domain modules are defined.