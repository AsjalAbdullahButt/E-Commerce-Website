# 🛍️ E-COM — Full-Stack E-Commerce Platform

Role-based (customer / admin / rider) e-commerce platform. **FastAPI + async SQLAlchemy + MySQL** on the backend, **vanilla JavaScript** on the frontend — no framework, no runtime bundler.

![Python](https://img.shields.io/badge/python-3.11+-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.139-009688)
![MySQL](https://img.shields.io/badge/MySQL-8.0-4479A1)
![License](https://img.shields.io/badge/license-MIT-green)

## ⚡ Quick Start

```bash
# 1. Install & configure
cd backend && python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cd .. && cp .env.example .env        # then set MYSQL_PASSWORD + JWT_SECRET (openssl rand -hex 32)

# 2. Database
mysql -u root -p -e "CREATE DATABASE ecommerce; CREATE DATABASE ecommerce_test;"
cd backend && alembic upgrade head
python -m seed.seed_admin && python -m seed.seed_db   # optional: admins + sample catalog

# 3. Run (two terminals)
python -m uvicorn main:app --reload --port 8000       # terminal 1 — API
python -m http.server 5500 --directory ../frontend    # terminal 2 — web app
```

| 🔗 | URL |
|---|---|
| 🛒 Customer site | <http://localhost:5500/> |
| 🛠️ Admin panel | <http://localhost:5500/admin/login.html> |
| 🛵 Rider app | <http://localhost:5500/rider/dashboard.html> |
| 📚 API docs | <http://localhost:8000/docs> *(needs `DOCS_ENABLED=true`)* |

**Or one-command Docker:**

```bash
cp .env.example .env && docker compose up --build   # MySQL + backend + frontend
```

## ✨ Features

- 🔐 **Multi-role auth** — JWT access tokens + rotating httpOnly refresh cookies, CSRF-protected
- 🛒 **Checkout** — guest or account, atomic stock reservation, idempotent order placement
- 💳 **Payments** — Stripe, JazzCash, EasyPaisa (webhook-verified) + Cash on Delivery, all optional
- 📦 **Catalog** — size/color/SKU variants, image upload (disk or S3), CSV import/export
- 🔁 **Returns & refunds** — customer requests → admin approve/reject → auto stock restore
- 🛵 **Rider delivery** with proof-of-photo · 🧾 PDF invoices · 📧 transactional email
- 📊 **Admin dashboard** — revenue/order trends, audit log, Excel report export
- 🛡️ **Security-first** — rate limiting, CSP/HSTS, fail-fast config validation

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| API | FastAPI (async) + Pydantic v2 |
| Database | MySQL 8 via SQLAlchemy 2.0 (async) + Alembic |
| Auth | python-jose (JWT) + passlib/bcrypt |
| Integrations | Stripe · JazzCash · EasyPaisa · SendGrid · S3 |
| Frontend | Vanilla JS/HTML/CSS + Tailwind utilities |
| Testing | pytest (real MySQL) + GitHub Actions CI |

## 📁 Structure

```text
backend/    main.py, routes/, models/, schemas/, services/, alembic/, seed/, tests/
frontend/   auth/, customer/, admin/, rider/, shared/ (JS components, CSS, API client)
```

## ⚙️ Configuration

All settings live in `.env` (copy from `.env.example`). Required: `MYSQL_*`, `JWT_SECRET` (32+ chars). Everything else — `STRIPE_*`, `JAZZCASH_*`, `EASYPAISA_*`, `SENDGRID_*`, `S3_*` — is **optional and off by default**; the app runs fully on Cash on Delivery + local storage with zero third-party accounts.

## 📡 API Overview

Full interactive docs at `/docs`. Key prefixes: `/auth`, `/products`, `/orders`, `/payments`, `/addresses`, `/reviews` · `/wishlist` · `/promos`, `/rider`, `/admin`.

## 🧪 Testing

```bash
cd backend && pytest
```

Runs against a real MySQL database (`MYSQL_TEST_DATABASE`). CI runs the same suite on every push.

## 🚢 Deployment

```bash
alembic upgrade head
WEB_CONCURRENCY=1 gunicorn -w 1 -k uvicorn.workers.UvicornWorker backend.main:app
```

> **Single worker only** unless Redis is enabled (`REDIS_ENABLED=true`) — the in-memory cache/rate-limiter aren't shared across workers otherwise.

Production stack: `docker compose -f docker-compose.prod.yml up -d --build` (Redis included, MySQL not exposed, `restart: always`). Before going live: `ENVIRONMENT=production`, `DOCS_ENABLED=false`, `COOKIE_SECURE=true`, a real `JWT_SECRET`, and a least-privilege MySQL user.

**Backups** — MySQL is the single source of truth; daily `mysqldump --single-transaction` + off-host copy is enough for a store this size. Test the restore path periodically.

## 📄 License

MIT

## 🤝 Contributing

1. Fork → `git checkout -b feature/your-feature`
2. Add/update tests under `backend/tests/`
3. `pytest` locally, then open a PR describing **what** and **why**
