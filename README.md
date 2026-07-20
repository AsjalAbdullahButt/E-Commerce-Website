# 🛍️ E-COM — Full-Stack E-Commerce Platform

A role-based (customer / admin / rider) e-commerce platform. **FastAPI + async SQLAlchemy + MySQL** on the backend, **vanilla JavaScript** on the frontend — no framework, no runtime bundler.

![Python](https://img.shields.io/badge/python-3.11+-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.139-009688)
![MySQL](https://img.shields.io/badge/MySQL-8.0-4479A1)
![License](https://img.shields.io/badge/license-MIT-green)

## ✨ Features

- 🔐 **Multi-role auth** — customer, admin (super_admin/admin/manager/support), and rider accounts behind JWT access tokens + rotating httpOnly refresh cookies, with double-submit CSRF protection
- 🛒 **Guest & account checkout** — cart, atomic stock reservation, an enforced order-status state machine, idempotent order placement
- 💳 **Payments** — Stripe, JazzCash, and EasyPaisa, all off by default and gateway-webhook-verified (a client can never self-report "paid"); Cash on Delivery always works with zero setup
- 📦 **Product catalog** — variant-based inventory (size/color/SKU/stock), search/filter, image uploads (local disk or S3-compatible), CSV import/export
- 🔁 **Returns & refunds** — customer-submitted return requests, admin approve/reject queue with automatic stock restoration
- 📍 **Saved addresses**, 🧾 **PDF invoices**, 📧 **transactional email** (order/status/return/low-stock, SendGrid), 🛵 **rider delivery** with proof-of-photo
- 📊 **Admin dashboard** — revenue/order trend analytics, inventory, discounts, audit log, Excel sales report export
- 🌐 **SEO** — dynamic sitemap, per-product meta tags, robots.txt
- 🛡️ **Security-first** — rate limiting, CSP/HSTS/security headers, NoSQL-operator input rejection, fail-fast config validation for every optional integration

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| API | FastAPI 0.139 (async), Pydantic v2 |
| Database | MySQL 8.0 via SQLAlchemy 2.0 (async) + aiomysql, Alembic migrations |
| Auth | python-jose (JWT), passlib/bcrypt |
| Payments / Email / Storage | Stripe, JazzCash, EasyPaisa · SendGrid · local disk / S3 |
| Frontend | Vanilla JS, HTML5, CSS3 + Tailwind utilities (no runtime bundler) |
| Testing / CI | pytest against a real MySQL database, GitHub Actions |

## 🚀 Quick Start

```bash
# 1. Backend deps
cd backend
python -m venv .venv && .venv\Scripts\activate      # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt

# 2. Configure
cd .. && cp .env.example .env
# edit .env — at minimum: MYSQL_PASSWORD and JWT_SECRET (openssl rand -hex 32)

# 3. Database
mysql -u root -p -e "CREATE DATABASE ecommerce; CREATE DATABASE ecommerce_test;"
cd backend && alembic upgrade head

# 4. Seed sample data (optional)
python -m seed.seed_admin   # 4 admin accounts — needs SEED_*_PASSWORD in .env
python -m seed.seed_db      # 20 products, 3 customers, 3 orders

# 5. Run
python -m uvicorn main:app --reload --port 8000
```

In a second terminal:

```bash
python -m http.server 5500 --directory frontend
```

| | URL |
|---|---|
| 🛒 Customer site | <http://localhost:5500/> |
| 🛠️ Admin panel | <http://localhost:5500/admin/login.html> |
| 🛵 Rider app | <http://localhost:5500/rider/dashboard.html> |
| 📚 API docs | <http://localhost:8000/docs> *(needs `DOCS_ENABLED=true`)* |

**Or with Docker** (MySQL + backend + frontend, one command):

```bash
cp .env.example .env   # set MYSQL_PASSWORD and JWT_SECRET
docker compose up --build
```

## 📁 Structure

```text
backend/
├── main.py, database.py     # App entry point, engine/session setup
├── config/                  # Settings (pydantic-settings)
├── db/, models/, schemas/   # ORM models + Pydantic request/response models
├── routes/                  # API routers
├── services/                # Business logic (payments, email, reports, ...)
├── middleware/, utils/      # Auth, cache, rate limiting, CSRF, IDs
├── alembic/, seed/          # Migrations + sample-data scripts
└── tests/                   # pytest suite (29 files, unit + integration)

frontend/
├── auth/, customer/, admin/, rider/   # Pages by role
└── shared/                            # Shared JS components, CSS, API client
```

## ⚙️ Configuration

Every setting lives in `.env` (copy from `.env.example`) and maps 1:1 to `backend/config/settings.py`. The essentials:

| Variable | Required | Notes |
|---|---|---|
| `MYSQL_HOST/PORT/USER/PASSWORD/DATABASE` | ✅ | `MYSQL_TEST_DATABASE` for pytest |
| `JWT_SECRET` | ✅ | 32+ chars, rejected if it looks like a placeholder |
| `ENVIRONMENT` | — | `development` (default) / `staging` / `production` |
| `WEB_CONCURRENCY` | — | Keep at `1` — see [Deployment](#-deployment) |
| `STRIPE_*` / `JAZZCASH_*` / `EASYPAISA_*` | — | Optional; each gateway fails fast at boot if enabled without real credentials |
| `SENDGRID_*` | — | Optional; emails log to console instead of sending when unset |
| `S3_*` | — | Optional; falls back to local-disk image storage |

Every optional integration (payments, email, S3) is **off by default** — the app runs fully on Cash on Delivery + local storage with zero third-party accounts.

## 🔐 Security

- **Passwords:** bcrypt (12 rounds) · **Tokens:** short-lived JWT access + rotating httpOnly `SameSite=Strict` refresh cookie, kept in memory only on the frontend (never localStorage)
- **CSRF:** double-submit cookie on the two cookie-authenticated endpoints (`/auth/refresh`, `/admin/auth/refresh`); every other route requires a bearer token
- **Payments:** every gateway webhook is signature-verified server-side — a client can never mark its own order paid
- **Headers:** CSP, HSTS (when `COOKIE_SECURE=true`), X-Frame-Options, TrustedHost enforcement in production
- **Input validation:** free-text fields reject NoSQL-operator patterns and control characters on top of Pydantic type checks

## 📡 API Overview

Full interactive docs at `/docs` (set `DOCS_ENABLED=true`). Routers, by prefix:

| Prefix | Covers |
|---|---|
| `/auth` | Register, login, refresh, password reset, profile |
| `/products` | Catalog search/filter/detail |
| `/orders` | Checkout (guest or account), status, cancel, invoice, return request |
| `/payments` | Gateway methods, initiate, webhook, status |
| `/addresses` | Saved shipping addresses |
| `/reviews`, `/wishlist`, `/promos` | Ratings, wishlist, discount codes |
| `/rider` | Assigned orders, delivery completion, earnings |
| `/admin` | Auth, catalog/order/user/rider management, returns queue, CSV import/export, reports, audit log |
| `/sitemap.xml` | SEO sitemap |

## 🧪 Testing

```bash
cd backend
pytest
```

Runs against a real MySQL database (`MYSQL_TEST_DATABASE`) — schema is created once per session, tables truncated between tests. CI runs the same suite on every push via GitHub Actions (`.github/workflows/ci.yml`), plus a weekly `pip-audit` dependency scan.

## 🚢 Deployment

> **Single worker only, by default.** The in-memory cache and rate limiter have no shared backend — running multiple workers desyncs both. The app fails fast at startup if `WEB_CONCURRENCY > 1` in production.

```bash
alembic upgrade head
WEB_CONCURRENCY=1 gunicorn -w 1 -k uvicorn.workers.UvicornWorker backend.main:app
```

Or `docker compose up --build` for the full self-hosted stack — see `docker-compose.yml`. The frontend builds to minified static files (`frontend/Dockerfile`, Tailwind + esbuild) and can be served from any static host.

**Before going live:** `ENVIRONMENT=production`, `DOCS_ENABLED=false`, `COOKIE_SECURE=true`, a real `JWT_SECRET`, your real `ALLOWED_ORIGINS`/`TRUSTED_HOSTS`, and a least-privilege MySQL user (not `root`).

## 📄 License

MIT

## 🤝 Contributing

1. Fork the repo and create a branch: `git checkout -b feature/your-feature`
2. Make your changes — add or update tests under `backend/tests/` for any backend change
3. Run `pytest` locally and make sure everything passes
4. Open a pull request describing **what** changed and **why**

Bug reports and feature ideas are welcome via GitHub Issues.
