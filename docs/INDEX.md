"""
E-Commerce Project Documentation Index

This document serves as the central hub for all project documentation.
Navigate to specific areas using the links below.
"""

# 📚 E-Commerce Platform — Complete Documentation

## Quick Links

### Getting Started
- **[Installation Guide](INSTALLATION.md)** — Step-by-step setup instructions
- **[Architecture Overview](ARCHITECTURE.md)** — System design and components
- **[API Documentation](API.md)** — Complete endpoint reference

### Development
- **[Security Guide](SECURITY.md)** — Best practices and threat models
- **[Deployment Guide](DEPLOYMENT.md)** — Production deployment steps
- **[Development Guide](DEVELOPMENT.md)** — Contributing guidelines

---

## 📋 Project Structure Overview

```
E-Commerce/
├── backend/                    # FastAPI backend
│   ├── config/                # Configuration management (NEW)
│   ├── routes/                # API endpoints
│   │   └── v1/               # API version 1 (NEW)
│   ├── models/               # Data models
│   ├── services/             # Business logic
│   ├── middleware/           # Request processing
│   ├── utils/                # Utilities
│   ├── tests/                # Test suite (NEW)
│   └── main.py               # Application entry point
│
├── frontend/                  # Frontend assets
│   ├── auth/                 # Authentication pages
│   ├── customer/             # Customer portal
│   ├── admin/                # Admin dashboard
│   ├── rider/                # Rider app
│   └── shared/               # Shared resources
│
├── docs/                      # Documentation (NEW)
│   ├── API.md
│   ├── ARCHITECTURE.md
│   ├── INSTALLATION.md
│   └── INDEX.md (this file)
│
└── .env.example              # Environment template (NEW)
```

---

## 🚀 Quick Start

### Backend Setup (5 minutes)
```bash
cd E-Commerce
python -m venv venv
source venv/bin/activate  # or: venv\Scripts\activate (Windows)
pip install -r backend/requirements.txt
cp .env.example .env
# Edit .env with your MongoDB URI
python -m uvicorn backend.main:app --reload
```

### Frontend Setup
```bash
# Option 1: Live Server
# VS Code: Right-click index.html → "Open with Live Server"

# Option 2: Python Server
python -m http.server 5500 --directory frontend
```

### Access Application
- **Frontend:** http://localhost:5500/customer/index.html
- **API Docs:** http://localhost:8000/docs (if DOCS_ENABLED=true)
- **Admin:** http://localhost:5500/admin/login.html

---

## 🏗️ Architecture Highlights

### Backend (v2.0)
- **Framework:** FastAPI (async)
- **Database:** MongoDB Atlas
- **Auth:** JWT with refresh tokens
- **Security:** bcrypt, CORS, rate limiting, CSP headers
- **Logging:** MongoDB audit logs
- **Testing:** Pytest with fixtures

### Frontend (Vanilla)
- **Stack:** HTML5, CSS3, ES6 JavaScript
- **Architecture:** Module-based components
- **Security:** XSS prevention, CSRF protection
- **Theme:** Dark/Light mode
- **Animation:** Canvas-based neural network background

---

## 📊 Key Features

✅ **Complete E-Commerce Functionality**
- Product catalog with filtering and search
- Shopping cart and wishlist
- Order management with lifecycle tracking
- User authentication and profiles
- Admin dashboard and analytics
- Rider assignment and delivery tracking
- Promotional codes and discounts
- Product reviews and ratings

✅ **Production-Ready Security**
- JWT authentication with refresh tokens
- Role-based access control (Customer/Admin/Rider)
- Password hashing with bcrypt
- Input validation with Pydantic
- XSS prevention with DOM APIs
- CSRF protection with CORS
- Rate limiting per endpoint
- Security headers (CSP, HSTS, X-Frame-Options)
- Audit logging to database

✅ **Developer Experience**
- Organized project structure
- Type hints and validation
- Comprehensive API documentation
- Test suite with fixtures
- Environment-based configuration
- API versioning (v1, ready for v2+)
- Clear error messages

---

## 🔒 Security Overview

### Frontend Security
- ✅ No innerHTML — all content via DOM APIs
- ✅ Input validation before API calls
- ✅ Secure token storage with expiry
- ✅ CSRF protection via CORS

### Backend Security
- ✅ JWT token validation on protected routes
- ✅ Bcrypt password hashing
- ✅ Pydantic input validation
- ✅ MongoDB ObjectId validation
- ✅ Rate limiting (5-60 req/min per endpoint)
- ✅ Security headers enforced
- ✅ Audit logging for all operations
- ✅ CORS whitelist

### Database Security
- ✅ MongoDB Atlas with encryption at rest
- ✅ SSL/TLS in transit
- ✅ IP whitelist
- ✅ Database user with minimal privileges
- ✅ Connection pooling

---

## 📈 Performance Features

- **Async/Await:** Non-blocking I/O throughout
- **Indexing:** Optimized MongoDB indexes
- **Rate Limiting:** Per-endpoint throttling
- **Caching:** Redis-ready utilities
- **Pagination:** 20 items/page with skip/limit
- **Lazy Loading:** Frontend pagination

---

## 🧪 Testing

### Unit Tests
```bash
pytest tests/test_utils/ -v
```

### Integration Tests
```bash
pytest tests/test_routes/ -v
```

### All Tests
```bash
pytest tests/ --cov=. --cov-report=html
```

### Manual Testing
- [See API.md](API.md) for cURL examples
- Use Postman collection (available in admin dashboard)
- Test credentials in [INSTALLATION.md](INSTALLATION.md)

---

## 🚢 Deployment

### Local Development
```bash
python -m uvicorn backend.main:app --reload
```

### Production Deployment
```bash
# Using Gunicorn + Uvicorn workers
gunicorn backend.main:app -w 4 -k uvicorn.workers.UvicornWorker

# Using Docker
docker build -t ecommerce . && docker run -p 8000:8000 ecommerce
```

### Hosting Options
- **Backend:** Render, Railway, Heroku, AWS EC2
- **Frontend:** Vercel, Netlify, GitHub Pages, S3
- **Database:** MongoDB Atlas (SaaS)
- **CDN:** CloudFlare (free tier available)

---

## 📚 Documentation Files

| File | Purpose |
|------|---------|
| [API.md](API.md) | Complete endpoint reference with examples |
| [ARCHITECTURE.md](ARCHITECTURE.md) | System design, components, data flow |
| [INSTALLATION.md](INSTALLATION.md) | Setup guide with troubleshooting |
| [SECURITY.md](SECURITY.md) | Security practices and threat models |
| [DEPLOYMENT.md](DEPLOYMENT.md) | Production deployment checklist |
| [DEVELOPMENT.md](DEVELOPMENT.md) | Contributing guidelines |

---

## 🔧 Configuration

### Environment Variables (.env)
```
ENVIRONMENT=development
MONGODB_URI=mongodb+srv://user:pass@cluster.mongodb.net/
DATABASE_NAME=E_Commerce
JWT_SECRET=your-secret-key
FRONTEND_URL=http://localhost:5500
ALLOWED_ORIGINS=http://localhost:5500
```

See `.env.example` for all available options.

---

## 🛠️ Common Tasks

### Add New Endpoint
1. Create route in `backend/routes/`
2. Create Pydantic model in `backend/models/`
3. Create schema in `backend/schemas/`
4. Add service logic to `backend/services/`
5. Document in [API.md](API.md)
6. Add tests to `backend/tests/`

### Add New Page
1. Create HTML in `frontend/{role}/`
2. Create JS module in `frontend/{role}/js/` or `frontend/shared/js/`
3. Update navigation in relevant pages
4. Ensure API integration via `frontend/shared/js/api.js`
5. Style with CSS in `frontend/shared/css/`

### Deploy to Production
1. Follow [DEPLOYMENT.md](DEPLOYMENT.md) checklist
2. Update environment variables
3. Run database backups
4. Test all endpoints
5. Monitor logs and errors

---

## 🆘 Troubleshooting

### Common Issues
- **API not responding:** Check backend is running on port 8000
- **Database connection failed:** Verify MongoDB URI and IP whitelist
- **CORS errors:** Check ALLOWED_ORIGINS in .env
- **Rate limit exceeded:** Increase limits in .env and restart
- **Token expired:** Clear localStorage and re-login

See [INSTALLATION.md](INSTALLATION.md#troubleshooting) for detailed solutions.

---

## 📞 Support & Resources

### Official Documentation
- FastAPI: https://fastapi.tiangolo.com
- MongoDB: https://docs.mongodb.com
- Python: https://docs.python.org/3

### Community
- FastAPI Discord: https://discord.gg/VQjSZaeJmf
- MongoDB Community: https://community.mongodb.com

---

## 📝 Version History

| Version | Date | Status |
|---------|------|--------|
| 2.0.0 | 2026-05-21 | Production Ready ✅ |
| 1.5.0 | 2026-05-01 | Phase 4: Security Hardening |
| 1.0.0 | 2026-04-01 | Initial Release |

---

## ✨ What's New in 2.0.0

✅ **Structural Improvements**
- Organized test suite with pytest
- Centralized configuration management
- API versioning support (v1)
- Comprehensive documentation

✅ **New Documentation**
- Complete API reference
- Architecture diagrams
- Security best practices
- Deployment guide

✅ **Developer Experience**
- Better error messages
- Configuration flexibility
- Test fixtures for development
- Environment-based settings

---

**Last Updated:** 2026-05-21  
**Platform Version:** 2.0.0  
**Status:** ✅ Production Ready
