# E-COM — Full-Stack E-Commerce Platform

A role-based (customer / admin / rider) e-commerce platform: FastAPI + async SQLAlchemy + MySQL on the backend, vanilla JavaScript on the frontend.

![Python](https://img.shields.io/badge/python-3.11+-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.139-009688)
![MySQL](https://img.shields.io/badge/MySQL-8.0-4479A1)
![License](https://img.shields.io/badge/license-MIT-green)

## Features

- **Multi-role auth** — customer, admin (super_admin/admin/manager/support), and rider accounts, each in their own table, unified behind one `/auth/login` endpoint plus a dedicated `/admin/auth/*` flow for the admin panel
- **JWT access + httpOnly refresh cookies** — short-lived bearer access tokens with a rotating httpOnly, `SameSite=Strict` refresh cookie and double-submit CSRF protection on `/auth/refresh`
- **Product catalog** — variant-based inventory (size/color/SKU/stock), category filtering, search, low-stock reporting
- **Orders & delivery** — cart checkout, atomic stock reservation, an enforced order-status state machine (`utils/order_transitions.py`), rider assignment and delivery tracking
- **Admin dashboard** — revenue/order/user analytics, product & inventory management, discount codes, user bans, audit log viewer
- **Promotions** — percentage/fixed discount codes with expiry and usage-limit validation
- **Reviews & wishlist** — per-product ratings/reviews, customer wishlists
- **Rate limiting** — per-route limits via slowapi (login, register, orders, general traffic)
- **Security headers & CSRF** — CSP, HSTS (when `COOKIE_SECURE=true`), X-Frame-Options, TrustedHost enforcement in production, double-submit CSRF cookies on cookie-authenticated endpoints

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| API framework | FastAPI 0.139 (async) |
| ORM / DB driver | SQLAlchemy 2.0 (async) + aiomysql |
| Database | MySQL 8.0 |
| Migrations | Alembic |
| Auth | python-jose (JWT), passlib/bcrypt |
| Rate limiting | slowapi |
| Validation | Pydantic v2 |
| Frontend | Vanilla JavaScript, HTML5, CSS3 (no build step, no framework) |
| Testing | pytest + FastAPI `TestClient` against a real MySQL test database |

## 📁 Structure

```text
├── backend/
│   ├── main.py              # App entry point, middleware, startup/shutdown hooks
│   ├── database.py          # Async SQLAlchemy engine/session setup
│   ├── config/               # Settings (pydantic-settings) + environment enum
│   ├── db/                   # SQLAlchemy ORM models (one module per domain)
│   ├── models/, schemas/     # Pydantic request/response models
│   ├── routes/                # API routers (auth, products, orders, admin, rider, ...)
│   ├── services/              # Business logic (admin auth, dashboard aggregation, ...)
│   ├── middleware/            # Auth middleware (JWT bearer, admin session)
│   ├── utils/                 # cache, rate limiter, CSRF, logging, ID generation, helpers
│   ├── alembic/                # Migration environment + versions
│   ├── seed/                   # Sample-data and admin-account seed scripts
│   └── tests/                   # pytest suite (unit + integration)
│
└── frontend/
    ├── auth/                # Login / register / password reset pages
    ├── customer/            # Shop, product, cart, checkout, profile, tracking
    ├── admin/               # Admin dashboard, products, orders, riders, promos, audit logs
    ├── rider/               # Rider dashboard and assigned-orders view
    └── shared/              # Shared JS (api client, auth, cart) and CSS
```

## Prerequisites

- Python 3.11+
- MySQL 8.0 (running locally or reachable over the network)
- A modern browser; no Node.js/build tooling required for the frontend

## 📦 Setup

```bash
# 1. Clone and enter the backend
cd backend
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS/Linux

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment
cd ..
cp .env.example .env
# edit .env: set MYSQL_PASSWORD and a real JWT_SECRET (32+ random chars, e.g. `openssl rand -hex 32`)

# 4. Create the MySQL databases referenced by .env
#    (MYSQL_DATABASE for the app, MYSQL_TEST_DATABASE for pytest)
mysql -u root -p -e "CREATE DATABASE ecommerce; CREATE DATABASE ecommerce_test;"

# 5. Apply migrations
cd backend
alembic upgrade head

# 6. Seed sample data (optional but recommended)
python -m seed.seed_admin   # creates 4 admin accounts — requires SEED_*_PASSWORD in .env
python -m seed.seed_db      # creates 20 products, 3 customers, 3 sample orders

# 7. Run the API
python -m uvicorn main:app --reload --port 8000
```

In a second terminal, serve the static frontend:

```bash
python -m http.server 5500 --directory frontend
```

Then open:

- **Customer site:** <http://localhost:5500/>
- **Admin panel:** <http://localhost:5500/admin/login.html>
- **Rider app:** <http://localhost:5500/rider/dashboard.html>
- **API docs:** <http://localhost:8000/docs> (only when `DOCS_ENABLED=true`)

## ⚙️ Configuration

Every variable below has a matching field in `backend/config/settings.py` and a documented default in `.env.example`.

| Variable | Default | Description |
|---|---|---|
| `ENVIRONMENT` | `development` | `development` / `staging` / `production` — gates TrustedHost enforcement and the single-worker check |
| `API_VERSION` | `v1` | Informational API version string |
| `MYSQL_HOST` / `MYSQL_PORT` | `localhost` / `3306` | MySQL connection host/port |
| `MYSQL_USER` / `MYSQL_PASSWORD` | `root` / — | MySQL credentials (`MYSQL_PASSWORD` required, no default) |
| `MYSQL_DATABASE` | `ecommerce` | Application database name |
| `MYSQL_TEST_DATABASE` | `ecommerce_test` | Database used by the pytest suite |
| `SQL_ECHO` | `false` | Log every SQL statement (SQLAlchemy `echo`) |
| `JWT_SECRET` | — | Required, 32+ chars, must not be a placeholder value |
| `JWT_ALGORITHM` | `HS256` | JWT signing algorithm |
| `JWT_ACCESS_EXPIRE_MINUTES` | `15` | Access token lifetime |
| `JWT_REFRESH_EXPIRE_MINUTES` | `10080` | Refresh token lifetime (7 days) |
| `FRONTEND_URL` | `http://localhost:3000` | Used to build links (e.g. password-reset emails/logs) |
| `ALLOWED_ORIGINS` | see `.env.example` | Comma-separated CORS allow-list |
| `TRUSTED_HOSTS` | `localhost,127.0.0.1` | Comma-separated Host-header allow-list; enforced only when `ENVIRONMENT=production` |
| `COOKIE_SECURE` | `false` | Set `true` in production (requires HTTPS) — controls the `Secure` cookie flag and HSTS header |
| `DOCS_ENABLED` | `false` | Enables `/docs` (Swagger UI) |
| `WEB_CONCURRENCY` | `1` | Must match the actual number of worker processes — see [Deployment](#-deployment) |
| `CACHE_MAX_ENTRIES` | `5000` | Upper bound on the in-memory cache before LRU eviction kicks in |
| `RATE_LOGIN` / `RATE_REGISTER` / `RATE_ORDER` / `RATE_GENERAL` | `5/minute` / `3/minute` / `10/minute` / `60/minute` | slowapi per-route rate limits |
| `LOG_LEVEL` | `INFO` | Python logging level |
| `LOG_FILE` | `logs/app.log` | Log file path (rotates daily, 30-day retention) |
| `SEED_SUPERADMIN_PASSWORD` etc. | — | Only read by `seed/seed_admin.py` to create local demo admin accounts |

## 🔐 Security

- **Passwords:** bcrypt via passlib (12 rounds)
- **Tokens:** short-lived JWT access tokens (bearer, `Authorization` header) + a rotating JWT refresh token stored in an httpOnly, `SameSite=Strict` cookie — never exposed to JavaScript. The frontend keeps its access token in memory only (not localStorage) and silently re-fetches it via `/auth/refresh` on page load
- **CSRF:** a double-submit cookie (`csrf_token` / `admin_csrf_token`) is required on the one cookie-authenticated endpoint per flow (`/auth/refresh`, `/admin/auth/refresh`); every other endpoint requires an explicit bearer token, which isn't forgeable cross-site
- **Rate limiting:** slowapi, per-route (see `RATE_*` variables above)
- **Security headers:** CSP, `X-Content-Type-Options`, `X-Frame-Options: DENY`, `Referrer-Policy`, `Cache-Control: no-store`, and HSTS when `COOKIE_SECURE=true`
- **Host validation:** `TrustedHostMiddleware`, enforced when `ENVIRONMENT=production`
- **Input sanitization:** free-text fields are stripped of control characters and rejected if they contain legacy NoSQL-operator patterns (`$where`, `$regex`, ...), in addition to Pydantic type validation

## API Endpoints

All routes are mounted with the prefixes below (see `backend/main.py`). Full interactive docs at `/docs` when `DOCS_ENABLED=true`.

| Router | Prefix | Highlights |
|---|---|---|
| Auth | `/auth` | `POST /register`, `POST /login`, `POST /refresh`, `POST /logout`, `GET /me`, `PUT /profile`, `POST /change-password`, `POST /forgot-password`, `POST /reset-password` |
| Products | `/products` | `GET /` (search/filter/paginate), `GET /categories`, `GET /{id}` |
| Orders | `/orders` | `POST /` (checkout), `GET /me`, `GET /{id}`, `PATCH /{id}/status`, `POST /{id}/cancel` |
| Reviews | `/reviews` | `POST /`, `GET /{product_id}` |
| Wishlist | `/wishlist` | `GET /`, `POST /{product_id}`, `DELETE /{product_id}` |
| Promos | `/promos` | `POST /validate`, `POST /`, `GET /`, `DELETE /{id}` |
| Rider | `/rider` | `GET /orders`, `PATCH /orders/{id}/status`, `POST /orders/{id}/complete`, `GET /stats`, `GET /earnings`, `GET /profile`, `PATCH /status` |
| Admin | `/admin` | Dedicated `/admin/auth/*` login/refresh/logout, plus `/products`, `/orders`, `/users`, `/riders`, `/inventory`, `/discounts`, `/dashboard/*`, `/analytics/*`, `/audit-logs` |

## 🧪 Testing

```bash
cd backend
pytest
```

Tests run against the real MySQL database named by `MYSQL_TEST_DATABASE` (schema is dropped and recreated once per test session; tables are truncated before each test). Set `MYSQL_TEST_DATABASE` and the shared MySQL credentials in `.env` before running.

## 🚢 Deployment

> **Single worker only, by default.** `utils/cache.py` (product/list cache) and `utils/limiter.py` (rate limiting) are process-local, in-memory stores with no Redis or other shared backend. Running more than one worker process means each worker has its own independent cache and rate-limit counters — a write in one worker won't invalidate a stale read cached by another, and a client can exceed a rate limit by roughly (worker count)×. `main.py` fails fast at startup if `WEB_CONCURRENCY > 1` while `ENVIRONMENT=production` (it only warns outside production). Scaling horizontally requires swapping both modules for a Redis-backed implementation first — `utils/cache.py`'s functions are already written with Redis-compatible async signatures to make that swap mechanical.

Production checklist:

- [ ] `ENVIRONMENT=production`
- [ ] `DOCS_ENABLED=false`
- [ ] `COOKIE_SECURE=true` (requires HTTPS)
- [ ] `JWT_SECRET` set to a real, unique 32+ character secret
- [ ] `ALLOWED_ORIGINS` and `TRUSTED_HOSTS` set to your actual frontend domain(s)
- [ ] `WEB_CONCURRENCY=1` unless a shared cache/limiter backend has been wired in
- [ ] `alembic upgrade head` run against the production database
- [ ] MySQL reachable with least-privilege credentials (not `root`)

```bash
# Migrations
alembic upgrade head

# Single-worker Gunicorn
WEB_CONCURRENCY=1 gunicorn -w 1 -k uvicorn.workers.UvicornWorker backend.main:app
```

The frontend is static HTML/CSS/JS — serve `frontend/` with any static file host (nginx, S3+CloudFront, etc.), pointing `frontend/shared/js/config.js`'s `API_BASE` at your deployed API URL.

### Docker

A self-contained local/self-hosted stack (MySQL + backend + static frontend):

```bash
cp .env.example .env
# edit .env: set MYSQL_PASSWORD and a real JWT_SECRET, at minimum

docker compose up --build
```

This builds `backend/Dockerfile` (single-worker Gunicorn + Uvicorn worker, matching the
single-process constraint above), waits for MySQL to become reachable, runs `alembic upgrade
head` automatically on every start (`backend/docker-entrypoint.sh`), and serves the frontend on
port 5500 via `python -m http.server`. Same three URLs as the non-Docker setup above.

`frontend/Dockerfile` is a multi-stage build: a `node:20-slim` stage runs `npm run build`
(Tailwind CLI + esbuild minifying every CSS/JS file into `frontend/dist/`, HTML untouched — see
`frontend/scripts/build-dist.js`), then a `python:3.12-slim` stage serves that `dist/` output.
Outside Docker, `python -m http.server 5500 --directory frontend` (above) keeps serving the raw,
unminified source directly — no build step needed for day-to-day dev.

Product images and other local-disk uploads (`services/image_storage.py`, active when
`S3_ENABLED=false`) persist in the `backend_uploads` named volume across `docker compose down`/`up`.

## License

MIT — see [LICENSE](LICENSE) if present, otherwise treat as MIT per this notice.

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/your-feature`)
3. Make your changes, add/adjust tests under `backend/tests/`
4. Open a pull request describing the change and why
