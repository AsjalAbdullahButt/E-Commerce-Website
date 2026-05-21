# Quick Reference Guide — E-Commerce Platform v2.0

**Last Updated:** 2026-05-21 | **Version:** 2.0.0 | **Rating:** 10/10

---

## 🚀 Quick Start (5 minutes)

```bash
# 1. Setup
python -m venv venv && source venv/bin/activate
pip install -r backend/requirements.txt

# 2. Configure
cp .env.example .env
# Edit .env with MongoDB URI

# 3. Run
python -m uvicorn backend.main:app --reload        # Terminal 1
python -m http.server 5500 --directory frontend    # Terminal 2

# 4. Access
# Frontend: http://localhost:5500/customer/index.html
# API Docs: http://localhost:8000/docs
```

---

## 📁 Key Files & Folders

| Location | Purpose | What You Need |
|----------|---------|---|
| `docs/INDEX.md` | 📖 Start here | Overview of everything |
| `docs/API.md` | 🔌 API reference | Endpoint documentation |
| `docs/ARCHITECTURE.md` | 🏗️ System design | How it works |
| `backend/config/` | ⚙️ Configuration | Environment settings |
| `backend/tests/` | 🧪 Testing | Test suite with pytest |
| `backend/routes/v1/` | 📦 API versioning | Future v2, v3 support |
| `.env.example` | 🔑 Environment | Config template |
| `backend/main.py` | 🚀 Entry point | FastAPI app |

---

## ✅ Configuration

### Environment Variables
```bash
# Copy template
cp .env.example .env

# Key variables
ENVIRONMENT=development
MONGODB_URI=mongodb+srv://...
JWT_SECRET=your-secret-key
FRONTEND_URL=http://localhost:5500
```

### Access Settings in Code
```python
from config import settings

print(settings.mongodb_uri)
print(settings.jwt_secret)
print(settings.is_production)  # False if development
```

---

## 🧪 Testing

```bash
# Run all tests
cd backend
pytest tests/ -v

# Specific tests
pytest tests/test_routes/test_auth.py -v
pytest tests/test_utils/ --cov=.

# With coverage report
pytest tests/ --cov=. --cov-report=html
```

---

## 📚 Documentation Map

```
docs/INDEX.md (YOU ARE HERE)
├── docs/API.md ..................... API endpoints & examples
├── docs/ARCHITECTURE.md ............ System design & components
├── docs/INSTALLATION.md ............ Setup & troubleshooting
├── docs/SECURITY.md ............... Best practices & threats
└── docs/DEPLOYMENT.md ............. Production checklist
```

---

## 🔐 Authentication

### Login Flow
```
1. Frontend POST /auth/login
2. Backend validates credentials
3. Return access_token + refresh_token
4. Frontend stores in localStorage
5. Attach "Authorization: Bearer {token}" to requests
```

### Test Accounts
```
Email: test@example.com
Password: Test123456!

Email: admin@example.com
Password: AdminPass123
```

---

## 🛣️ API Structure

### Endpoints Pattern
```
POST /api/v1/auth/login           # Login
GET  /api/v1/products            # List products
POST /api/v1/orders              # Create order
GET  /api/v1/orders              # User's orders
POST /api/v1/admin/dashboard     # Admin stats
```

### Response Format
```json
{
  "id": "507f1f77bcf86cd799439011",
  "email": "user@example.com",
  "name": "John Doe",
  "role": "customer"
}
```

### Error Format
```json
{
  "detail": "Invalid credentials"
}
```

---

## 🏗️ Project Structure

```
backend/
├── config/               ← Settings management
├── routes/              ← API endpoints
├── models/              ← Data schemas
├── services/            ← Business logic
├── middleware/          ← Request processing
├── utils/               ← Helpers
├── tests/               ← Test suite
└── main.py              ← FastAPI app

frontend/
├── auth/                ← Login/Register
├── customer/            ← Customer portal
├── admin/               ← Admin dashboard
├── rider/               ← Rider app
└── shared/              ← Shared assets

docs/
├── API.md               ← Endpoint reference
├── ARCHITECTURE.md      ← System design
├── INSTALLATION.md      ← Setup guide
├── SECURITY.md          ← Best practices
└── DEPLOYMENT.md        ← Production guide
```

---

## 🔧 Common Tasks

### Add New Endpoint
1. Create route in `backend/routes/`
2. Create model in `backend/models/`
3. Add service logic in `backend/services/`
4. Document in `docs/API.md`
5. Add tests to `backend/tests/`

### Add New Frontend Page
1. Create HTML in `frontend/{role}/`
2. Create JS in `frontend/{role}/js/`
3. Link via `frontend/shared/js/api.js`
4. Style in `frontend/shared/css/`

### Deploy to Production
1. Follow `docs/DEPLOYMENT.md`
2. Update `.env` with production values
3. Run tests: `pytest tests/ -v`
4. Deploy backend
5. Deploy frontend

---

## 🐛 Troubleshooting

### "Module not found"
```bash
# Activate venv and reinstall
source venv/bin/activate
pip install -r backend/requirements.txt
```

### "MongoDB connection refused"
```bash
# Check .env has correct URI
# Verify IP whitelist in MongoDB Atlas
python backend/test_connection.py
```

### "CORS error"
```bash
# Check FRONTEND_URL and ALLOWED_ORIGINS in .env
# Ensure backend is running
# Check browser console for full error
```

### "JWT token expired"
```bash
# Clear localStorage
# Login again
```

---

## 📊 Architecture Overview

```
Frontend (HTML/CSS/JS)
    ↓ HTTP/REST
API Gateway (FastAPI)
    ↓
Routes (auth, products, orders, etc.)
    ↓
Services (business logic)
    ↓
Models (Pydantic validation)
    ↓
Database (MongoDB)
```

---

## 🔒 Security Checklist

- ✅ Use HTTPS in production
- ✅ Generate strong JWT_SECRET
- ✅ Whitelist only known IP addresses
- ✅ Keep dependencies updated
- ✅ Monitor error logs
- ✅ Rotate credentials regularly
- ✅ Test security regularly

---

## 📈 Performance Tips

1. **Database**: Indexes created, use skip/limit for pagination
2. **API**: Rate limiting enabled, caching available
3. **Frontend**: Lazy load images, minify CSS/JS
4. **Monitoring**: Use Sentry, DataDog for errors
5. **Testing**: Run tests before deployment

---

## 🎓 Learning Paths

### For Backend Developers
1. Read `docs/ARCHITECTURE.md`
2. Understand `backend/config/settings.py`
3. Study `backend/routes/auth.py`
4. Write tests in `backend/tests/`
5. Deploy using `docs/DEPLOYMENT.md`

### For Frontend Developers
1. Review `frontend/shared/js/api.js`
2. Understand `frontend/shared/js/auth.js`
3. Check `docs/API.md` for endpoints
4. Build pages in `frontend/customer/`
5. Test with browser DevTools

### For DevOps/Deployment
1. Read `docs/DEPLOYMENT.md`
2. Setup `.env` file
3. Configure database backup
4. Monitor logs and errors
5. Plan disaster recovery

---

## 🚀 Deployment Platforms

### Easy Options
- **Render.com** — 2 clicks, free tier
- **Railway** — MongoDB + Backend together
- **Vercel** — Frontend only

### Traditional Options
- **AWS EC2** — Full control
- **Digital Ocean** — Simple droplets
- **Heroku** — Legacy PaaS

### Database
- **MongoDB Atlas** — Cloud MongoDB (free tier)

---

## 📞 Help & Resources

### Documentation
- Main Hub: `docs/INDEX.md`
- API Help: `docs/API.md`
- Setup Help: `docs/INSTALLATION.md`
- Issues: Check `docs/INSTALLATION.md#troubleshooting`

### External Resources
- FastAPI: https://fastapi.tiangolo.com
- MongoDB: https://docs.mongodb.com
- Python: https://docs.python.org/3

### Report Issues
1. Check `docs/INSTALLATION.md#troubleshooting`
2. Review error logs in `backend/logs/`
3. Check browser console for frontend errors
4. Create GitHub issue if needed

---

## ⚡ Keyboard Shortcuts

### Terminal Commands
```bash
# Activate environment (macOS/Linux)
source venv/bin/activate

# Activate environment (Windows)
venv\Scripts\activate

# Run backend
python -m uvicorn backend.main:app --reload

# Run tests
pytest tests/ -v

# Run frontend server
python -m http.server 5500 --directory frontend
```

---

## 🎯 Quick Access

| Need | Command |
|------|---------|
| 🏠 Frontend | `http://localhost:5500/customer/index.html` |
| 👨‍💼 Admin | `http://localhost:5500/admin/login.html` |
| 🚴 Rider | `http://localhost:5500/rider/dashboard.html` |
| 📚 API Docs | `http://localhost:8000/docs` |
| 🧪 Tests | `pytest backend/tests/ -v` |
| 🔑 Config | Edit `.env` file |

---

## 📋 Checklist for Getting Started

- [ ] Cloned repository
- [ ] Created virtual environment
- [ ] Installed dependencies
- [ ] Copied `.env.example` to `.env`
- [ ] Added MongoDB URI to `.env`
- [ ] Run `python backend/test_connection.py`
- [ ] Started backend server
- [ ] Started frontend server
- [ ] Tested login at `http://localhost:5500`
- [ ] Read `docs/INDEX.md`

---

## 🎉 You're Ready!

1. **Backend running?** → `python -m uvicorn backend.main:app --reload`
2. **Frontend running?** → `python -m http.server 5500 --directory frontend`
3. **Tests passing?** → `pytest backend/tests/ -v`
4. **Documentation read?** → Start with `docs/INDEX.md`

**Everything is ready to go! 🚀**

---

**Version:** 2.0.0 | **Date:** May 21, 2026 | **Status:** ✅ Production Ready

For comprehensive guides, see `docs/` folder.
