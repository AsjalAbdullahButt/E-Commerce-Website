# E-Commerce Platform — Architecture Documentation

**Platform Version:** 2.0.0  
**Environment:** Production-Grade  
**Last Updated:** 2026-05-21

---

## Table of Contents
1. [System Architecture](#system-architecture)
2. [Technology Stack](#technology-stack)
3. [Directory Structure](#directory-structure)
4. [Component Overview](#component-overview)
5. [Data Flow](#data-flow)
6. [Security Architecture](#security-architecture)
7. [Deployment](#deployment)

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Frontend Layer                              │
├──────────────────────┬──────────────────────┬──────────────────────┤
│  Customer Portal     │  Admin Dashboard     │  Rider App           │
│  (HTML/CSS/JS)       │  (HTML/CSS/JS)       │  (HTML/CSS/JS)       │
└──────────────────────┴──────────────────────┴──────────────────────┘
                              │
                              │ HTTP/REST/CORS
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│                    API Gateway & Middleware                         │
├─────────────────────────────────────────────────────────────────────┤
│  Rate Limiting │ CORS │ Auth Validation │ Logging │ Error Handling  │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│                      FastAPI Backend (v1)                           │
├──────────────────────┬──────────────────────┬──────────────────────┤
│  Routes/Handlers     │  Business Logic      │  Utilities           │
│  - Auth              │  - Product Service   │  - Password Hashing  │
│  - Products          │  - Order Service     │  - Token Generation  │
│  - Orders            │  - Discount Service  │  - Sanitization      │
│  - Users             │  - Dashboard Service │  - Validation        │
│  - Admin             │                      │  - Logging           │
│  - Rider             │                      │  - Rate Limiting     │
│  - Reviews/Promos    │                      │                      │
└──────────────────────┴──────────────────────┴──────────────────────┘
                              │
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│                      Data Access Layer                              │
├─────────────────────────────────────────────────────────────────────┤
│  Pydantic Models │ MongoDB Async Driver │ Query Builders          │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│                    MongoDB Atlas (Cloud)                            │
├──────────────────────┬──────────────────────┬──────────────────────┤
│  Collections:        │                      │                      │
│  - users             │  - reviews           │  - audit_logs        │
│  - products          │  - promos            │  - riders            │
│  - orders            │  - wishlist          │  - admin_users       │
└──────────────────────┴──────────────────────┴──────────────────────┘
```

---

## Technology Stack

### Backend
- **Framework:** FastAPI 0.111
- **Runtime:** Python 3.11+
- **Database:** MongoDB Atlas (Cloud)
- **Database Driver:** Motor (Async PyMongo)
- **Authentication:** JWT (PyJWT)
- **Password Security:** bcrypt
- **Validation:** Pydantic 2.0
- **Rate Limiting:** SlowAPI
- **Server:** Uvicorn

### Frontend
- **Language:** Vanilla JavaScript (ES6+)
- **Styling:** CSS3
- **HTTP Client:** Fetch API
- **Theme:** Dark/Light Mode
- **Animation:** Canvas-based Neural Network Background
- **Storage:** LocalStorage (tokens, user data)

### Infrastructure
- **Hosting:** Cloud-Ready (Deployed to Render/Railway/Heroku)
- **CDN:** CloudFlare (CSS), Google Fonts
- **Database:** MongoDB Atlas
- **Logging:** MongoDB Audit Log Collection
- **Environment:** Docker-Ready

---

## Directory Structure

```
E-Commerce/
├── backend/
│   ├── config/                 # Configuration management
│   │   ├── __init__.py
│   │   ├── settings.py        # Centralized settings
│   │   └── environments.py    # Environment definitions
│   ├── routes/
│   │   ├── v1/               # API v1 endpoints (future versioning)
│   │   ├── auth.py           # Authentication endpoints
│   │   ├── products.py       # Product catalog
│   │   ├── orders.py         # Order management
│   │   ├── users.py          # User management
│   │   ├── admin.py          # Admin dashboard
│   │   ├── rider.py          # Rider operations
│   │   ├── reviews.py        # Product reviews
│   │   ├── promos.py         # Promotional codes
│   │   └── wishlist.py       # User wishlist
│   ├── models/
│   │   ├── user.py           # User data model
│   │   ├── product.py        # Product data model
│   │   ├── order.py          # Order data model
│   │   ├── admin.py          # Admin data model
│   │   ├── review.py         # Review data model
│   │   ├── promo.py          # Promo data model
│   │   └── __init__.py
│   ├── schemas/
│   │   ├── user.py           # User schemas (request/response)
│   │   ├── product.py        # Product schemas
│   │   ├── order.py          # Order schemas
│   │   ├── admin.py          # Admin schemas
│   │   └── __init__.py
│   ├── services/
│   │   ├── admin_auth.py     # Admin authentication logic
│   │   ├── product.py        # Product business logic
│   │   ├── order_user.py     # Order processing logic
│   │   ├── discount.py       # Discount calculations
│   │   ├── dashboard.py      # Dashboard statistics
│   │   └── __init__.py
│   ├── middleware/
│   │   ├── auth_middleware.py      # JWT validation
│   │   ├── admin_auth.py           # Admin authorization
│   │   └── __init__.py
│   ├── utils/
│   │   ├── helpers.py         # Password hashing, JWT creation
│   │   ├── logger.py          # Logging utilities
│   │   ├── limiter.py         # Rate limiting setup
│   │   ├── cache.py           # Caching utilities
│   │   ├── permissions.py     # Permission checks
│   │   └── __init__.py
│   ├── seed/
│   │   ├── seed_admin.py      # Admin seeding
│   │   ├── seed_db.py         # Database seeding
│   │   └── __init__.py
│   ├── tests/                 # Test suite
│   │   ├── conftest.py        # Pytest configuration
│   │   ├── test_routes/       # Route tests
│   │   ├── test_services/     # Service tests
│   │   ├── test_models/       # Model tests
│   │   ├── test_utils/        # Utility tests
│   │   └── __init__.py
│   ├── logs/                  # Application logs
│   │   └── app.log
│   ├── config.py              # Deprecated (use config/settings.py)
│   ├── database.py            # Database connections
│   ├── main.py                # FastAPI app entry point
│   ├── requirements.txt        # Python dependencies
│   └── test_connection.py     # Connection testing script
│
├── frontend/
│   ├── auth/
│   │   ├── login.html
│   │   └── register.html
│   ├── customer/
│   │   ├── index.html         # Home page
│   │   ├── shop.html          # Product listing
│   │   ├── product.html       # Product detail
│   │   ├── checkout.html      # Checkout page
│   │   ├── profile.html       # User profile
│   │   ├── tracking.html      # Order tracking
│   │   ├── about.html         # About page
│   │   └── contact.html       # Contact page
│   ├── admin/
│   │   ├── dashboard.html     # Admin dashboard
│   │   ├── products.html      # Product management
│   │   ├── orders.html        # Order management
│   │   ├── promos.html        # Promo management
│   │   ├── logs.html          # System logs
│   │   ├── js/
│   │   │   ├── admin-api.js
│   │   │   ├── admin-ui.js
│   │   │   ├── admin-config.js
│   │   │   └── analytics.js
│   │   └── css/
│   │       └── admin-style.css
│   ├── rider/
│   │   ├── dashboard.html
│   │   └── assigned-orders.html
│   ├── shared/
│   │   ├── js/               # Shared utilities
│   │   │   ├── api.js        # API client wrapper
│   │   │   ├── auth.js       # Auth utilities
│   │   │   ├── cart.js       # Cart management
│   │   │   ├── config.js     # Configuration
│   │   │   ├── sanitize.js   # XSS prevention
│   │   │   └── neural-bg.js  # Background animation
│   │   └── css/              # Shared styles
│   │       ├── global.css
│   │       ├── auth.css
│   │       ├── home.css
│   │       ├── shop.css
│   │       ├── product.css
│   │       ├── checkout.css
│   │       ├── profile.css
│   │       ├── tracking.css
│   │       ├── admin.css
│   │       └── about.css
│   ├── js/                   # Customer-specific JS
│   │   ├── home.js
│   │   ├── shop.js
│   │   ├── product.js
│   │   ├── checkout.js
│   │   ├── profile.js
│   │   ├── tracking.js
│   │   └── contact.js
│   └── images/              # Static images
│
├── docs/
│   ├── API.md                # API documentation
│   ├── ARCHITECTURE.md       # This file
│   ├── INSTALLATION.md       # Setup guide
│   ├── SECURITY.md           # Security practices
│   └── DEPLOYMENT.md         # Deployment guide
│
├── .env.example              # Environment template
├── .gitignore
├── README.md                 # Project overview
└── package.json              # Frontend dependencies (optional)
```

---

## Component Overview

### Backend Components

#### 1. **Routes (API Endpoints)**
- **auth.py**: User registration, login, token refresh
- **products.py**: Product listing, filtering, search
- **orders.py**: Order creation, status updates, history
- **users.py**: Profile management, account updates
- **admin.py**: Dashboard, user management, reports
- **rider.py**: Rider assignments, order updates
- **reviews.py**: Product reviews and ratings
- **promos.py**: Promotional code management
- **wishlist.py**: User wishlist operations

#### 2. **Models (Data Schemas)**
Pydantic models for:
- User (authentication, profile)
- Product (catalog, inventory)
- Order (transactions, tracking)
- Review (ratings, feedback)
- Admin (privileges, access control)
- Promo (discounts, campaigns)

#### 3. **Services (Business Logic)**
- **admin_auth.py**: Admin authentication and validation
- **product.py**: Product operations and filtering
- **order_user.py**: Order processing and calculations
- **discount.py**: Promo code validation and discounts
- **dashboard.py**: Statistics and analytics

#### 4. **Middleware (Request Processing)**
- **auth_middleware.py**: JWT validation on protected routes
- **admin_auth.py**: Admin role verification
- **CORS**: Cross-origin request handling
- **Rate Limiting**: SlowAPI-based request throttling
- **Security Headers**: CSP, HSTS, XSS protection

#### 5. **Utils (Helpers)**
- **helpers.py**: Password hashing, JWT creation, data sanitization
- **logger.py**: Structured logging to MongoDB
- **limiter.py**: Rate limiting configuration
- **cache.py**: Caching strategies
- **permissions.py**: Role-based access control

### Frontend Components

#### 1. **HTML Pages**
- **Auth**: Login, Register with validation
- **Customer**: Home, Shop, Product Detail, Checkout, Profile, Tracking
- **Admin**: Dashboard, Product/Order/Promo Management, Logs
- **Rider**: Dashboard, Assigned Orders

#### 2. **JavaScript Modules**
- **api.js**: Centralized API client with auto-auth
- **auth.js**: Token management, login/logout
- **cart.js**: Shopping cart state management
- **sanitize.js**: XSS prevention utilities
- **config.js**: Frontend configuration
- **neural-bg.js**: Animated background canvas

#### 3. **CSS Styling**
- **global.css**: Global styles, theme variables
- **auth.css**: Login/register styling
- **home.css**: Homepage styling
- **shop.css**: Product listing styling
- **checkout.css**: Checkout flow styling
- **admin.css**: Admin dashboard styling

---

## Data Flow

### 1. Authentication Flow
```
User Input (Email/Password)
    ↓
Frontend: auth.js → Fetch POST /api/v1/auth/login
    ↓
Backend: auth.py → Validate credentials
    ↓
Database: Query users_col
    ↓
Backend: helpers.py → Create JWT tokens
    ↓
Response: access_token, refresh_token
    ↓
Frontend: localStorage → Store tokens
    ↓
Redirect to Dashboard
```

### 2. Product Browsing Flow
```
User: Browse products
    ↓
Frontend: shop.js → Fetch GET /api/v1/products?category=X
    ↓
Backend: products.py → Query products_col with filters
    ↓
Backend: services/product.py → Apply business logic
    ↓
Response: Product array with pagination
    ↓
Frontend: DOM rendering via sanitize.js
    ↓
User: Views product catalog
```

### 3. Order Processing Flow
```
User: Click Checkout
    ↓
Frontend: checkout.js → POST /api/v1/orders (with JWT)
    ↓
Backend: auth_middleware.py → Validate JWT
    ↓
Backend: orders.py → Create order document
    ↓
Backend: services/order_user.py → Calculate total, apply discounts
    ↓
Database: Insert to orders_col, update products_col stock
    ↓
Backend: logger.py → Log transaction to audit_logs_col
    ↓
Response: Order confirmation
    ↓
Frontend: Display order summary, redirect to tracking
```

---

## Security Architecture

### Frontend Security
- **XSS Prevention**: All innerHTML replaced with DOM APIs
- **CSRF Protection**: Same-site cookies, CORS validation
- **Data Validation**: Client-side input validation
- **Secure Storage**: Tokens in localStorage with auto-expiry
- **Content Security Policy**: Enforced headers from backend

### Backend Security
- **Password Security**: bcrypt hashing with random salt
- **JWT Security**: HS256 algorithm, expiring tokens
- **Role-Based Access**: Middleware checks user.role
- **Rate Limiting**: Per-endpoint request throttling
- **Input Validation**: Pydantic models enforce type/length
- **SQL Injection Prevention**: MongoDB ObjectId validation
- **CORS**: Whitelist of allowed origins
- **Security Headers**:
  - `X-Content-Type-Options: nosniff`
  - `X-Frame-Options: DENY`
  - `X-XSS-Protection: 1; mode=block`
  - `Strict-Transport-Security` (production)

### Database Security
- **MongoDB Atlas**: Cloud-hosted with encryption at rest
- **Connection**: SSL/TLS encryption in transit
- **IP Whitelist**: Allow only application servers
- **Access Control**: Database users with minimal privileges
- **Audit Logging**: All operations logged to audit_logs_col

---

## Configuration Management

### Environment Variables (.env)
```
ENVIRONMENT=development
MONGODB_URI=mongodb+srv://...
DATABASE_NAME=E_Commerce
JWT_SECRET=your-secret-key
JWT_ALGORITHM=HS256
FRONTEND_URL=http://localhost:3000
ALLOWED_ORIGINS=...
```

### Configuration Hierarchy
1. **Environment Variables** (.env file)
2. **config/settings.py** (Pydantic Settings)
3. **Default Values** (hardcoded in Settings class)
4. **Environment-Specific Overrides** (is_production, is_development)

---

## Deployment

### Development
```bash
# Install dependencies
pip install -r backend/requirements.txt

# Set environment
export ENVIRONMENT=development

# Run server
python -m uvicorn backend.main:app --reload
```

### Production
```bash
# Use Gunicorn with Uvicorn workers
gunicorn backend.main:app \
  -w 4 \
  -k uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000
```

### Docker
```dockerfile
FROM python:3.11
WORKDIR /app
COPY backend/requirements.txt .
RUN pip install -r requirements.txt
COPY backend .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0"]
```

### Hosting Recommendations
- **Backend**: Render, Railway, Heroku, AWS EC2
- **Frontend**: Vercel, Netlify, GitHub Pages
- **Database**: MongoDB Atlas (Cloud)
- **CDN**: CloudFlare

---

## Future Enhancements (v3.0)

- [ ] GraphQL API support alongside REST
- [ ] WebSocket real-time notifications
- [ ] Payment gateway integration (Stripe, PayPal)
- [ ] Email notifications (SendGrid)
- [ ] Search optimization (Elasticsearch)
- [ ] Caching layer (Redis)
- [ ] Microservices architecture
- [ ] Kubernetes orchestration
- [ ] Machine learning recommendations
- [ ] Multi-currency support

---

**Last Updated:** 2026-05-21  
**Version:** 2.0.0 (Production-Ready)
