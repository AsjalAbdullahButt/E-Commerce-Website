# E-Commerce Platform

A full-stack e-commerce application built with **FastAPI** backend and **Vanilla JavaScript** frontend.

## Quick Start

### Prerequisites
- Python 3.11+
- MongoDB Atlas account (free tier available)
- Git

### Setup Backend
```bash
cd backend
python -m venv venv
source venv/bin/activate  # macOS/Linux or venv\Scripts\activate on Windows
pip install -r requirements.txt
cp ..\.env.example ..\env
python -m uvicorn main:app --reload
```

### Setup Frontend
```bash
python -m http.server 5500 --directory frontend
```

### Access the App
- **Single entry point:** http://localhost:5500/ — routes to the right home page (customer/admin/rider) based on your session, or to login/register if you're not signed in
- **Customer shop directly:** http://localhost:5500/customer/index.html
- **Admin login directly:** http://localhost:5500/admin/login.html
- **API Docs:** http://localhost:8000/docs

## Project Structure

```
E-Commerce/
├── backend/               # FastAPI application
│   ├── config.py         # Configuration settings
│   ├── main.py          # App entry point
│   ├── database.py      # MongoDB connection
│   ├── models/          # Data models
│   ├── routes/          # API endpoints
│   ├── services/        # Business logic
│   ├── middleware/      # Middleware
│   ├── utils/           # Utilities
│   ├── seed/            # Database seeding
│   └── requirements.txt # Dependencies
│
└── frontend/            # Frontend assets
    ├── auth/           # Login/Register
    ├── customer/       # Customer portal
    ├── admin/          # Admin dashboard
    ├── rider/          # Rider app
    ├── shared/         # Shared JS/CSS
    └── images/         # Static images
```

## Features

- **User Management** - Customer, Admin, and Rider roles
- **Product Catalog** - Browse, search, and filter products
- **Shopping Cart** - Add/remove items, manage wishlist
- **Order System** - Place orders, track status, delivery management
- **Admin Dashboard** - Analytics, product management, user management
- **Promotion System** - Discount codes and promotional campaigns
- **Review System** - Product ratings and reviews
- **Security** - JWT authentication, password hashing, rate limiting

## Technology Stack

- **Backend:** FastAPI, MongoDB, Motor (async driver), Pydantic
- **Frontend:** Vanilla JavaScript, CSS3, HTML5
- **Auth:** JWT, bcrypt
- **Database:** MongoDB Atlas
- **Hosting:** Any cloud platform (Render, Railway, Heroku, AWS, etc.)

## Configuration

Create a `.env` file in the root directory:

```env
MONGODB_URI=mongodb+srv://user:password@cluster.mongodb.net/ecommerce
JWT_SECRET=your_secret_key_here
ENVIRONMENT=development
```

See `.env.example` for all available options.

## Testing

```bash
cd backend
pytest tests/ -v
```

## API Endpoints

### Authentication
- `POST /auth/register` - Register new user
- `POST /auth/login` - Login user
- `POST /auth/refresh` - Refresh JWT token

### Products
- `GET /products` - List all products
- `GET /products/{id}` - Get product details
- `POST /products` - Create product (admin only)
- `PATCH /products/{id}` - Update product (admin only)
- `DELETE /products/{id}` - Delete product (admin only)

### Orders
- `POST /orders` - Create new order
- `GET /orders/me` - Get my orders
- `GET /orders/{id}` - Get order details
- `PATCH /orders/{id}/cancel` - Cancel order

### Admin
- `GET /admin/dashboard` - Dashboard stats
- `GET /admin/analytics/revenue` - Revenue analytics
- `GET /admin/users` - List all users
- `PATCH /admin/users/{id}/ban` - Ban user

## Default Credentials

### Admin Account
- Email: `admin@example.com`
- Password: `AdminPass123`

### Admin Dashboard Accounts
- Email: `superadmin@example.com` / Password: `SuperAdmin@123`
- Email: `admin@example.com` / Password: `AdminPass123`
- Email: `manager@example.com` / Password: `Manager@123456`
- Email: `support@example.com` / Password: `Support@123456`

### Customer Account
- Email: `test@example.com`
- Password: `Test123456!`

## Deployment

> **Single worker only.** The in-memory cache (`utils/cache.py`) and rate limiter
> (`utils/limiter.py`) have no Redis or other shared backend — each worker process keeps its own
> independent cache and rate-limit counters. Running more than one worker means cache
> invalidation and rate limits are no longer consistent across requests. Set `WEB_CONCURRENCY=1`
> (the app fails fast on startup in production if this isn't 1). Scaling horizontally requires
> wiring up a shared Redis-backed cache/limiter first.

### Using Gunicorn
```bash
WEB_CONCURRENCY=1 gunicorn -w 1 -k uvicorn.workers.UvicornWorker backend.main:app
```

### Using Docker
```bash
docker build -t ecommerce . && docker run -p 8000:8000 ecommerce
```

### Cloud Platforms
- **Render.com** - Deploy with git push
- **Railway** - Native MongoDB support
- **Heroku** - Traditional PaaS
- **AWS EC2** - Full control with auto-scaling

## License

MIT License - see LICENSE file for details

## Support

For issues or questions:
1. Check the [documentation](./docs/) folder
2. Review [API documentation](./docs/API.md)
3. Create a GitHub issue with details

---

**Made with ❤️ for e-commerce excellence**

### [1️⃣ Multi-Role Authentication](#️⃣-multi-role-authentication-1)
- **Customers:** Browse products, place orders, track deliveries
- **Admins:** Manage everything (products, orders, users, promos)
- **Riders:** Accept deliveries, update status, earn commission
- **Roles stored in JWT:** Fast authorization without DB lookup

### [2️⃣ Shopping Experience](#️⃣-shopping-experience-1)
- **Real-time inventory:** Stock checked atomically before order placement
- **Price sync at checkout:** Fetches latest prices from backend to catch changes
- **Promo code validation:** Checks expiry, usage limits, and discount type (% or fixed)
- **Cart persistence:** localStorage syncs across browser sessions

### [3️⃣ Admin Dashboard](#️⃣-admin-dashboard-1)
- **Analytics pipelines:** MongoDB $group aggregation for instant stats
- **Product CRUD:** Full lifecycle management with image URLs
- **Order management:** Filter by status, assign to riders, track revenue
- **User administration:** Ban/unban customers, view transaction history

### [4️⃣ Rider Operations](#️⃣-rider-operations-1)
- **Order assignment:** Automatic or manual assignment from admin
- **Status updates:** Pending → Confirmed → Packed → Shipped → Delivered
- **Earnings tracking:** Automatic commission calculation (₹100 per delivery)
- **Order history:** Full delivery record with customer ratings

### [5️⃣ Security & Performance](#️⃣-security--performance-1)
- **HTTP-only cookies:** JWT tokens in secure, httpOnly cookies (production)
- **Rate limiting:** Prevent brute-force on login, DOS on orders
- **Compound indexes:** (status, created_at), (rider_id, status) for fast queries
- **Cache management:** Redis-ready structure (currently in-memory stub)
- **HSTS header:** Force HTTPS in production (cookie_secure=true)
- **HSTS header:** Force HTTPS in production (cookie_secure=true)

---

## 🔧 Configuration

### Environment Variables (.env)

```ini
# MongoDB Connection
MONGODB_URI=mongodb+srv://user:pass@cluster.mongodb.net/

# JWT Configuration
JWT_SECRET=your_min_32_char_random_string_here
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=15              # Access token: 15 minutes
JWT_REFRESH_EXPIRE_MINUTES=10080   # Refresh token: 7 days

# URLs
FRONTEND_URL=http://localhost:5500
ALLOWED_ORIGINS=http://localhost:5500,http://127.0.0.1:5500

# Security
DOCS_ENABLED=false                 # Set true only in development
COOKIE_SECURE=false                # Set true for production HTTPS

# Rate Limits (requests/minute)
RATE_LOGIN=5/minute
RATE_REGISTER=3/minute
RATE_ORDER=10/minute
RATE_GENERAL=60/minute
```

### Frontend Configuration (frontend/shared/js/config.js)

```javascript
const CONFIG = {
  API_BASE: 'http://localhost:8000',
  API_TIMEOUT: 10000,
  JWT_ACCESS_KEY: 'access_token',
  JWT_REFRESH_KEY: 'refresh_token',
  CART_KEY: 'shopping_cart'
};
```

---

## 📊 Database Initialization

### First-Time Setup

```bash
# Seed admin users (creates 4 admin accounts with different roles)
cd backend
python -m seed.seed_admin

# Output:
# ✅ SUPER_ADMIN → superadmin@ecom.local / SuperAdmin@123
# ✅ ADMIN → admin@ecom.local / Admin@123456
# ✅ MANAGER → manager@ecom.local / Manager@123456
# ✅ SUPPORT → support@ecom.local / Support@123456

# Seed sample data (creates 20 products, 3 users, 3 sample orders)
python -m seed.seed_db

# Output:
# ✅ Created 20 products (12 clothing + 8 accessories)
# ✅ Created 3 demo customers
# ✅ Created 3 demo orders
```

---

## 🧪 Testing

### Manual API Testing with curl

```bash
# Register customer
curl -X POST "http://localhost:8000/auth/register" \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"Test@1234","name":"Test User"}'

# Login
curl -X POST "http://localhost:8000/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"Test@1234"}'

# Get all products
curl "http://localhost:8000/products?limit=10"

# Search products
curl "http://localhost:8000/products?search=shirt&category=clothing"

# Place order (requires auth)
curl -X POST "http://localhost:8000/orders" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "items": [{"product_id":"...", "quantity": 2}],
    "shipping_address": "123 Street, City",
    "payment_method": "credit_card"
  }'
```

---

## 🚀 Deployment

### Production Checklist

- [ ] Set `DOCS_ENABLED=false` in .env
- [ ] Set `COOKIE_SECURE=true` in .env (requires HTTPS)
- [ ] Configure `JWT_SECRET` to a cryptographically secure 32+ character string
- [ ] Set `ALLOWED_ORIGINS` to your actual frontend domain
- [ ] Enable HTTPS/TLS certificates on your server
- [ ] Use production MongoDB Atlas cluster with IP whitelisting
- [ ] Configure rate limits based on expected traffic
- [ ] Set up monitoring and alerting for errors
- [ ] Deploy with exactly one worker process (`WEB_CONCURRENCY=1`) — the in-memory cache and
      rate limiter are not shared across workers (see "Deployment" note above)

### Using Docker (Optional)

```bash
# Build backend image
docker build -t ecommerce-backend ./backend

# Run backend container
docker run -p 8000:8000 \
  -e MONGODB_URI="..." \
  -e JWT_SECRET="..." \
  ecommerce-backend

# Frontend is static HTML/CSS/JS (serve with nginx, Apache, etc.)
```

### Using Heroku (Optional)

```bash
# Install Heroku CLI, then:
heroku create your-ecommerce-app
heroku config:set MONGODB_URI="mongodb+srv://..."
heroku config:set JWT_SECRET="..."
git push heroku main
```

---

## 🐛 Troubleshooting

### Backend won't start
```bash
# Check Python version (requires 3.11+)
python --version

# Reinstall dependencies
pip install -r requirements.txt --force-reinstall

# Check MongoDB connection
python -c "import pymongo; print(pymongo.__version__)"
```

### Frontend can't connect to API
```bash
# Verify backend is running
curl http://localhost:8000/docs

# Check CORS settings in backend/main.py
# Ensure ALLOWED_ORIGINS includes your frontend URL

# Check browser console for specific error messages
```

### Authentication failing
```bash
# Verify JWT_SECRET is set in .env (min 32 characters)
# Check that tokens aren't expired (15 min access, 7 day refresh)
# Clear browser localStorage and try login again
```

### MongoDB connection errors
```bash
# Test connection string
python -c "from pymongo import MongoClient; MongoClient('YOUR_MONGODB_URI')"

# Verify:
# - IP address is whitelisted in MongoDB Atlas
# - Username/password is correct
# - Database name matches MONGODB_URI
```

---

## 📚 Documentation

- **[API Docs](/docs)** — Interactive Swagger documentation (DOCS_ENABLED=true)
- **[Backend Code Structure](/backend)** — Detailed backend organization
- **[Frontend Code Structure](/frontend)** — Detailed frontend organization
- **[Database Schema](/backend/models)** — Pydantic model definitions

---

## 🤝 Contributing

Contributions are welcome! Please follow these steps:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/YourFeature`)
3. Make your changes and commit (`git commit -m 'Add YourFeature'`)
4. Push to the branch (`git push origin feature/YourFeature`)
5. Open a Pull Request

---

## 📄 License

This project is licensed under the MIT License. See [LICENSE](LICENSE) file for details.

---

## 👨‍💻 Author

**Abdul Basit Butt**

- GitHub: [@AsjalAbdullahButt](https://github.com/AsjalAbdullahButt)
- Email: abdul@example.com

---

## 📞 Support

For issues, questions, or suggestions:

1. **Check existing issues** — [GitHub Issues](https://github.com/AsjalAbdullahButt/E-Commerce-Website/issues)
2. **Search documentation** — Use the guides above
3. **Open a new issue** — Include error logs and steps to reproduce

---

<div align="center">


⭐ If you find this project helpful, please consider starring it on GitHub!

[Back to Top](#-e-commerce-store)

</div>
