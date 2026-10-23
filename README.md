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

## Pages
/login.html (sign in / create account / account + change password), /admin.html (songs + users, admin only).
A "Sign in" button is added to the viewer's top bar by /site-nav.js (injected into index.html by the server, or by nginx sub_filter in docker-compose).

## Adding many songs
python tools/import_library.py --site https://<your-site> --library "<viewer_copy>\library"   (use --dry-run first)

## Song picker / track names
The viewer page gets a Songs button (site-nav.js): lists the library and opens a song through the viewer's own library dialog. admin.html reads the track names from the chosen tab file (alphaTab 1.8.4 from jsDelivr) and offers them in a dropdown.

## Direct "open song" hook (recommended, one small viewer change)
In the viewer copy, src/convert/useConverter.ts, paste this directly above the line `const running = job?.state === ...`:

    // Lets the site's "Songs" button open a stored song directly.
    useEffect(() => {
      ;(window as unknown as { __t2hOpen?: (id: string) => Promise<void> }).__t2hOpen = async (id: string) => {
        const items = await convApi.library()
        const it = items.find((x) => x.id === id)
        if (!it) throw new Error('song not found')
        await openItem(it)
      }
    }, [openItem])

Then `npm run build` and copy dist/ into web/ as before. Without it the Songs button falls back to clicking through the viewer's own dialog.
