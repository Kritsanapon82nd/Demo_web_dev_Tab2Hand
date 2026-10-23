# Tab2Hand Library (REST API + Docker Compose)
Guitar-tab -> 3D left-hand pose library. Poses are produced offline by the research pipeline
(ik_poses_output.json) and stored/served here.

## Run
    docker compose up -d --build
    open http://localhost:8080        (web)    |  API under /api/  e.g. /api/health
Set DB_PASSWORD in a .env file for anything beyond local demo.

## Services
db (PostgreSQL 16) | api (FastAPI) | web (nginx: static page + proxy /api -> api)

## Endpoints (api, no /api prefix inside the container)
Auth: POST /register, /login, /logout, /change-password
Users: GET /me, GET /users (admin, ?page&page_size), GET|PUT|DELETE /users/{id} (self or admin), GET /check-username/{name}
Songs: POST /songs (login), GET /songs (public, ?q&page), GET /songs/{id}, GET /songs/{id}/poses, DELETE /songs/{id} (owner/admin)
First registered user becomes admin. Passwords: PBKDF2-SHA256. Tokens: random bearer, stored hashed, revocable (logout).

## Tables
users, sessions, songs (poses stored as JSON text)

## Known limits
Conversion (DP + IK) is NOT run online (takes minutes to an hour per song); songs are converted locally and uploaded.
Tested: API with SQLite via test_api.py. Postgres/Compose stack not yet run end-to-end.

## Deploy (Render + Neon)
Dockerfile.render builds one container: web (static viewer build in web/) at `/`, API at `/api`. Env: DATABASE_URL (Neon).
Put the viewer's `npm run build` output (dist/*) into web/ (keep admin.html). Admin page: /admin.html (first registered user = admin).
The viewer's library dialog reads songs from the SQL table through /api/status, /api/library, /api/jobs/{id}/(tab|poses).
Online conversion is disabled; convert locally (serve.py) and upload with admin.html.
