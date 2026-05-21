# Installation & Setup Guide

**E-Commerce Platform v2.0.0**  
**Last Updated:** 2026-05-21

---

## Table of Contents
1. [Prerequisites](#prerequisites)
2. [Backend Setup](#backend-setup)
3. [Frontend Setup](#frontend-setup)
4. [Database Setup](#database-setup)
5. [Configuration](#configuration)
6. [Running the Application](#running-the-application)
7. [Testing](#testing)
8. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### System Requirements
- **OS**: Windows, macOS, or Linux
- **Python**: 3.11+
- **Node.js**: 16+ (optional, for frontend tooling)
- **Git**: For version control

### Required Software
```bash
# Install Python 3.11+
# Download from https://python.org

# Verify installation
python --version
python -m pip --version
```

---

## Backend Setup

### Step 1: Clone Repository
```bash
cd E-Commerce
```

### Step 2: Create Virtual Environment
```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS/Linux
python3 -m venv venv
source venv/bin/activate
```

### Step 3: Install Dependencies
```bash
pip install -r backend/requirements.txt
```

### Step 4: Verify Installation
```bash
python -c "import fastapi; import motor; import pydantic; print('✓ All dependencies installed')"
```

---

## Frontend Setup

### Option 1: Local HTML Files
No setup required. Open HTML files directly in browser or serve with Python:

```bash
# Windows
python -m http.server 5500 --directory frontend

# macOS/Linux
python3 -m http.server 5500 --directory frontend
```

Then access: `http://localhost:5500/customer/index.html`

### Option 2: Live Server Extension (VS Code)
1. Install "Live Server" extension by Ritwick Dey
2. Right-click `index.html` → "Open with Live Server"

---

## Database Setup

### Step 1: Create MongoDB Atlas Account
1. Visit https://mongodb.com/cloud/atlas
2. Create free account
3. Create a new cluster (M0 Free tier)
4. Wait for cluster to initialize (~5-10 minutes)

### Step 2: Create Database User
1. Go to **Database Access** → **Add New User**
2. Set username: `ecommerce_user`
3. Set password: Generate strong password
4. Click **Add User**

### Step 3: Whitelist IP Address
1. Go to **Network Access** → **Add IP Address**
2. Click **Allow Access from Anywhere** (for development)
3. For production, whitelist only your server IPs

### Step 4: Get Connection String
1. Click **Connect** on cluster
2. Select **Drivers** → **Python** → **3.11 or higher**
3. Copy connection string
4. Replace `<password>` with your database password
5. Example: `mongodb+srv://ecommerce_user:yourpassword@cluster.mongodb.net/?retryWrites=true&w=majority`

---

## Configuration

### Step 1: Create .env File
```bash
# Copy template
cp .env.example .env
```

### Step 2: Edit .env File
```
# .env file content
ENVIRONMENT=development
MONGODB_URI=mongodb+srv://ecommerce_user:yourpassword@cluster.mongodb.net/?retryWrites=true&w=majority
DATABASE_NAME=E_Commerce
JWT_SECRET=your-super-secret-jwt-key-change-in-production-at-least-32-chars
JWT_ALGORITHM=HS256
JWT_ACCESS_EXPIRE_MINUTES=15
JWT_REFRESH_EXPIRE_MINUTES=10080
FRONTEND_URL=http://localhost:5500
ALLOWED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000,http://localhost:8080,http://127.0.0.1:8080,http://localhost:5500,http://127.0.0.1:5500
COOKIE_SECURE=false
DOCS_ENABLED=false
RATE_LOGIN=5/minute
RATE_REGISTER=3/minute
RATE_ORDER=10/minute
RATE_GENERAL=60/minute
LOG_LEVEL=INFO
LOG_FILE=logs/app.log
API_VERSION=v1
```

### Step 3: Update Config Values
```python
# backend/config/settings.py
# Verify your settings are being read:
from config import settings
print(f"MongoDB URI: {settings.mongodb_uri}")
print(f"Environment: {settings.environment}")
print(f"API Version: {settings.api_version}")
```

---

## Running the Application

### Option 1: Standard Development Server
```bash
# Navigate to backend
cd backend

# Start server
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000

# API will be at: http://localhost:8000
# Docs at: http://localhost:8000/docs (if DOCS_ENABLED=true)
```

### Option 2: With VS Code
1. Open `backend/main.py`
2. Install **Python** extension
3. Click **Run and Debug** → **Python**

### Option 3: With FastAPI CLI
```bash
fastapi dev backend/main.py
```

### Step 1: Verify Backend is Running
```bash
# In another terminal, test connection
curl http://localhost:8000/api/v1/products
```

### Step 2: Start Frontend Server
```bash
# In third terminal
python -m http.server 5500 --directory frontend
```

### Step 3: Open in Browser
```
http://localhost:5500/customer/index.html
```

---

## Testing

### Run All Tests
```bash
cd backend

# Install pytest if not already installed
pip install pytest pytest-cov

# Run tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=. --cov-report=html
```

### Run Specific Test File
```bash
pytest tests/test_routes/test_auth.py -v
```

### Test Configuration
```bash
# Tests use pytest fixtures from tests/conftest.py
# Test data is provided by @pytest.fixture functions
# Tests automatically set ENVIRONMENT=development
```

### Manual API Testing
```bash
# Test Register
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"Test123456!","name":"Test User"}'

# Test Login
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"Test123456!"}'

# Test Get Products
curl http://localhost:8000/api/v1/products
```

---

## Database Seeding (Optional)

### Seed Admin User
```bash
# From backend directory
python seed/seed_admin.py
```

Default Admin Credentials:
- Email: `admin@example.com`
- Password: `AdminPass123`

### Seed Sample Data
```bash
python seed/seed_db.py
```

This populates:
- Sample products
- Sample categories
- Sample reviews
- Sample orders

---

## Troubleshooting

### Issue: "ModuleNotFoundError: No module named 'fastapi'"
**Solution:**
```bash
# Ensure virtual environment is activated
source venv/bin/activate  # macOS/Linux
# or
venv\Scripts\activate  # Windows

# Reinstall requirements
pip install -r backend/requirements.txt
```

### Issue: "MongoDB connection refused"
**Solution:**
```bash
# Verify connection string in .env
# Check MongoDB Atlas cluster is running
# Verify IP whitelist includes your IP
# Test connection
python backend/test_connection.py
```

### Issue: "CORS error in browser console"
**Solution:**
```bash
# Verify FRONTEND_URL in .env matches your frontend URL
# Verify ALLOWED_ORIGINS includes your frontend origin
# Ensure backend server is running
# Check backend console for errors
```

### Issue: "JWT token expired"
**Solution:**
```bash
# Clear browser localStorage
# Delete ecom_token from developer tools → Application → LocalStorage
# Login again
```

### Issue: "404 Not Found on /api/v1/..."
**Solution:**
```bash
# Verify backend is running (should see "Uvicorn running on http://0.0.0.0:8000")
# Check route exists in backend/routes/*.py
# Verify API_VERSION in .env matches route path
# Check for typos in endpoint URL
```

### Issue: "Rate limit exceeded"
**Solution:**
```bash
# Increase rate limits in .env
RATE_GENERAL=120/minute

# Restart backend server
# Wait for rate limit window to reset (usually 1 minute)
```

### Issue: "Database logs not appearing"
**Solution:**
```bash
# Verify LOG_FILE path is writable
# Create logs directory if missing
mkdir backend/logs

# Verify MongoDB audit_logs collection is created
# Check permissions on log file
```

---

## Production Checklist

Before deploying to production:

- [ ] Change `ENVIRONMENT=production`
- [ ] Set strong `JWT_SECRET` (32+ characters)
- [ ] Set `COOKIE_SECURE=true`
- [ ] Set `DOCS_ENABLED=false`
- [ ] Update `ALLOWED_ORIGINS` to production domain
- [ ] Set `MONGODB_URI` to production database
- [ ] Update `FRONTEND_URL` to production domain
- [ ] Enable SSL/TLS certificate
- [ ] Setup automatic backups for MongoDB
- [ ] Configure rate limits appropriately
- [ ] Setup error monitoring (Sentry, etc.)
- [ ] Setup logging aggregation (DataDog, etc.)
- [ ] Test all endpoints on production server
- [ ] Setup CI/CD pipeline
- [ ] Document deployment process

---

## Getting Help

### Documentation
- API Documentation: [docs/API.md](API.md)
- Architecture: [docs/ARCHITECTURE.md](ARCHITECTURE.md)
- Security: [docs/SECURITY.md](SECURITY.md)

### Community Resources
- FastAPI Docs: https://fastapi.tiangolo.com
- MongoDB Docs: https://docs.mongodb.com
- Python Docs: https://docs.python.org/3

### Support
If you encounter issues:
1. Check [Troubleshooting](#troubleshooting) section
2. Review error messages in backend console
3. Check browser developer console
4. Verify all prerequisites are installed

---

**Last Updated:** 2026-05-21  
**Version:** 2.0.0
