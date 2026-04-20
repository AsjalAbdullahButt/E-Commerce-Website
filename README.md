<div align="center">

# 🛍️ E-COM — Full-Stack E-Commerce Platform

**Production-grade e-commerce built with FastAPI + MongoDB + Vanilla JS**

### Tech Stack
![Python](https://img.shields.io/badge/Python-3.13-3776ab?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688?logo=fastapi&logoColor=white)
![MongoDB](https://img.shields.io/badge/MongoDB-Atlas-47a248?logo=mongodb&logoColor=white)
![JavaScript](https://img.shields.io/badge/JavaScript-ES6+-F7DF1E?logo=javascript&logoColor=black)
![HTML5](https://img.shields.io/badge/HTML5-E34C26?logo=html5&logoColor=white)
![CSS3](https://img.shields.io/badge/CSS3-1572B6?logo=css3&logoColor=white)

</div>

---

## ✨ Features

| Area | What's included |
|---|---|
| 🔐 **Auth** | JWT login/register, bcrypt password hashing, role-based access (customer / admin / rider) |
| 🛒 **Shopping** | Product catalogue, cart, wishlist, promo codes, real-time order placement |
| 📦 **Orders** | Full order lifecycle — pending → confirmed → packed → shipped → delivered |
| 🚴 **Rider Portal** | Rider dashboard, delivery status updates |
| 🛡️ **Security** | Rate limiting on every route, server-side price validation, security headers, TrustedHost middleware |
| 🎨 **Frontend** | Dark/light theme, neural-network animated background, sidebar with categories + filters, responsive design |
| ⚙️ **Admin** | Product CRUD, order management, promo management, user list |

---

## ⚙️ Prerequisites

| Tool | Version |
|---|---|
| Python | 3.11 or higher |
| pip | Latest |
| Git | Any recent version |
| MongoDB | Atlas free tier or local |
| Browser | Chrome 90+ / Firefox 90+ |

---

## 🚀 Installation & Setup

### 1️⃣ Clone the repository

```bash
git clone https://github.com/AsjalAbdullahButt/E-Commerce-Website.git
cd E-Commerce-Website
```

### 2️⃣ Configure environment variables

```bash
cp .env.example .env
```

Open `.env` and fill in your values:

```env
MONGODB_URI=mongodb+srv://<user>:<password>@<cluster>.mongodb.net/
JWT_SECRET=your-super-secret-key-minimum-32-characters-long
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=1440
FRONTEND_URL=http://localhost:5500
ALLOWED_ORIGINS=http://localhost:5500,http://127.0.0.1:5500
DOCS_ENABLED=true
```

> ⚠️ **Never commit `.env` to Git.** It is already in `.gitignore`.

### 3️⃣ Install Python dependencies

```bash
cd backend
pip install -r requirements.txt
```

### 4️⃣ (Optional) Seed the database with sample data

```bash
cd backend
python seed/seed_db.py
```

---

## ▶️ Running the Application

### Start the backend

```bash
cd backend
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

You should see:

```
╔════════════════════════════════════╗
║   🛍️  E-COMMERCE API v2.0  🛍️      ║
╠════════════════════════════════════╣
║  📊 Connecting to Database...     ║
╚════════════════════════════════════╝

✅  MongoDB connected — server ready on :8000
```

### Start the frontend

Open a **new terminal**:

```bash
cd frontend
python -m http.server 5500
```

Then open your browser at:

```
http://localhost:5500
```

---

## 🌐 API Reference

Interactive docs are available at `http://localhost:8000/docs` (when `DOCS_ENABLED=true`).

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `POST` | `/auth/register` | ❌ | Register new user |
| `POST` | `/auth/login` | ❌ | Login, receive JWT |
| `GET` | `/auth/me` | ✅ | Get current user |
| `GET` | `/products` | ❌ | List products (paginated, filterable) |
| `GET` | `/products/{id}` | ❌ | Single product |
| `POST` | `/products` | 🔑 Admin | Create product |
| `PUT` | `/products/{id}` | 🔑 Admin | Update product |
| `DELETE` | `/products/{id}` | 🔑 Admin | Deactivate product |
| `POST` | `/orders` | ✅ | Place order |
| `GET` | `/orders/me` | ✅ | My orders |
| `GET` | `/orders` | 🔑 Admin | All orders |
| `POST` | `/promos/validate` | ✅ | Validate promo code |
| `GET` | `/wishlist` | ✅ | My wishlist |
| `POST` | `/reviews` | ✅ | Add review (must have purchased) |
| `GET` | `/rider/orders` | 🔑 Rider | My deliveries |

---

## 🔐 Security

This project implements multiple layers of protection:

- **Password Hashing** — bcrypt via passlib (never stored in plain text)
- **JWT Auth** — HS256 signed tokens, 24-hour expiry
- **Rate Limiting** — SlowAPI on every route (login: 5/min, register: 3/min, orders: 10/min)
- **Server-Side Pricing** — Item prices are always fetched from the database; client-supplied prices are ignored
- **Security Headers** — `X-Frame-Options`, `X-Content-Type-Options`, `Strict-Transport-Security`, `X-XSS-Protection`, `Referrer-Policy`, `Cache-Control: no-store`
- **TrustedHost Middleware** — Prevents Host-header injection
- **Input Validation** — Pydantic models on all request bodies; search length capped at 100 chars
- **Pagination Cap** — `limit` max 100 to prevent DB dump attacks
- **Role Guards** — `require_admin`, `require_rider` dependency functions

---

## 🧪 Test Accounts

After running the seeder (`python seed/seed_db.py`):

| Role | Email | Password |
|---|---|---|
| 👑 Admin | `admin@ecommerce.com` | `admin123` |
| 👤 Customer | `customer@ecommerce.com` | `customer123` |
| 🚴 Rider | `rider@ecommerce.com` | `rider123` |

---

## 🤝 Contributing

1. Fork the repo
2. Create a feature branch: `git checkout -b feature/your-feature`
3. Commit changes: `git commit -m "feat: add your feature"`
4. Push: `git push origin feature/your-feature`
5. Open a Pull Request
