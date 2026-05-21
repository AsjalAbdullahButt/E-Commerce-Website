# Deployment & Production Guide

**E-Commerce Platform v2.0.0**  
**Last Updated:** 2026-05-21

---

## Table of Contents
1. [Pre-Deployment Checklist](#pre-deployment-checklist)
2. [Environment Configuration](#environment-configuration)
3. [Backend Deployment](#backend-deployment)
4. [Frontend Deployment](#frontend-deployment)
5. [Database Setup](#database-setup)
6. [Monitoring & Logging](#monitoring--logging)
7. [Performance Optimization](#performance-optimization)
8. [Disaster Recovery](#disaster-recovery)

---

## Pre-Deployment Checklist

### Security Review
- [ ] All secrets rotated (JWT_SECRET, DB passwords)
- [ ] HTTPS certificate configured
- [ ] CORS origins updated to production domain
- [ ] Docs endpoint disabled (`DOCS_ENABLED=false`)
- [ ] Debug mode disabled
- [ ] Database backups enabled

### Code Quality
- [ ] All tests passing (`pytest tests/ -v`)
- [ ] No console.log statements in production code
- [ ] No hardcoded credentials in code
- [ ] All dependencies security-audited (`pip audit`)
- [ ] Code reviewed by team

### Infrastructure
- [ ] Database cluster provisioned
- [ ] Server resources allocated
- [ ] CDN configured
- [ ] DNS records updated
- [ ] Email service configured (SMTP)
- [ ] Monitoring tools installed

### Performance
- [ ] Database indexes created
- [ ] Caching strategy implemented
- [ ] API response times < 200ms
- [ ] Frontend load time < 3 seconds
- [ ] Database connection pooling optimized

---

## Environment Configuration

### Production .env Template

```bash
# ── Environment ────────────────────────────────────────────────────────
ENVIRONMENT=production
API_VERSION=v1

# ── Database ───────────────────────────────────────────────────────────
MONGODB_URI=mongodb+srv://username:password@prod-cluster.mongodb.net/?retryWrites=true&w=majority&ssl=true
DATABASE_NAME=E_Commerce_Production

# ── JWT Authentication ────────────────────────────────────────────────
JWT_SECRET=<generate-with: python -c "import secrets; print(secrets.token_urlsafe(32))">
JWT_ALGORITHM=HS256
JWT_ACCESS_EXPIRE_MINUTES=15
JWT_REFRESH_EXPIRE_MINUTES=10080

# ── Frontend & CORS ───────────────────────────────────────────────────
FRONTEND_URL=https://example.com
ALLOWED_ORIGINS=https://example.com,https://www.example.com,https://admin.example.com

# ── Security ──────────────────────────────────────────────────────────
COOKIE_SECURE=true
DOCS_ENABLED=false

# ── Rate Limiting (conservative for production) ────────────────────────
RATE_LOGIN=5/minute
RATE_REGISTER=3/minute
RATE_ORDER=10/minute
RATE_GENERAL=60/minute

# ── Logging ───────────────────────────────────────────────────────────
LOG_LEVEL=WARNING
LOG_FILE=/var/log/ecommerce/app.log
```

### Generate Strong Secrets

```bash
# Generate JWT_SECRET
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Generate Database Password
python -c "import secrets; print(secrets.token_urlsafe(24))"

# Generate API Keys (if needed)
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

---

## Backend Deployment

### Option 1: Traditional Server (Linux/Ubuntu)

#### Step 1: Clone Repository
```bash
cd /opt
sudo git clone https://github.com/yourname/ecommerce.git
cd ecommerce
```

#### Step 2: Setup Python Environment
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r backend/requirements.txt
pip install gunicorn
```

#### Step 3: Create Systemd Service
```bash
sudo nano /etc/systemd/system/ecommerce.service
```

```ini
[Unit]
Description=E-Commerce API Service
After=network.target

[Service]
Type=notify
User=ecommerce
WorkingDirectory=/opt/ecommerce
Environment="PATH=/opt/ecommerce/venv/bin"
EnvironmentFile=/opt/ecommerce/.env
ExecStart=/opt/ecommerce/venv/bin/gunicorn \
    -w 4 \
    -k uvicorn.workers.UvicornWorker \
    --bind 0.0.0.0:8000 \
    --timeout 60 \
    --access-logfile /var/log/ecommerce/access.log \
    --error-logfile /var/log/ecommerce/error.log \
    backend.main:app

Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

#### Step 4: Start Service
```bash
sudo systemctl daemon-reload
sudo systemctl enable ecommerce
sudo systemctl start ecommerce
sudo systemctl status ecommerce
```

#### Step 5: Configure Nginx Reverse Proxy
```bash
sudo nano /etc/nginx/sites-available/ecommerce
```

```nginx
upstream ecommerce_backend {
    server localhost:8000;
}

server {
    listen 443 ssl http2;
    server_name api.example.com;

    # SSL Certificate
    ssl_certificate /etc/letsencrypt/live/api.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api.example.com/privkey.pem;

    # Security headers
    add_header Strict-Transport-Security "max-age=63072000; includeSubDomains" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-Frame-Options "DENY" always;
    add_header X-XSS-Protection "1; mode=block" always;

    # Proxy settings
    location / {
        proxy_pass http://ecommerce_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 60s;
    }
}

# Redirect HTTP to HTTPS
server {
    listen 80;
    server_name api.example.com;
    return 301 https://$server_name$request_uri;
}
```

#### Step 6: Enable Nginx
```bash
sudo nginx -t  # Test config
sudo systemctl enable nginx
sudo systemctl start nginx
```

### Option 2: Docker Container

#### Dockerfile
```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY backend .

# Create non-root user
RUN useradd -m -u 1000 ecommerce && \
    mkdir -p /app/logs && \
    chown -R ecommerce:ecommerce /app

USER ecommerce

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/products || exit 1

EXPOSE 8000

CMD ["gunicorn", "-w", "4", "-k", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8000", "main:app"]
```

#### Build & Run
```bash
# Build image
docker build -t ecommerce:latest .

# Run container
docker run -d \
  --name ecommerce \
  --restart always \
  -p 8000:8000 \
  --env-file .env \
  -v ecommerce_logs:/app/logs \
  ecommerce:latest

# Monitor
docker logs -f ecommerce
```

### Option 3: Cloud Platforms

#### Render.com
```yaml
# render.yaml
services:
  - type: web
    name: ecommerce-api
    env: python
    buildCommand: pip install -r backend/requirements.txt
    startCommand: gunicorn -w 4 -k uvicorn.workers.UvicornWorker backend.main:app
    envVars:
      - key: ENVIRONMENT
        value: production
      - key: MONGODB_URI
        sync: false
```

#### Heroku
```bash
# Create Procfile
web: gunicorn -w 4 -k uvicorn.workers.UvicornWorker backend.main:app

# Deploy
git push heroku main
```

#### AWS EC2
```bash
# Create AMI with:
# - Python 3.11
# - Nginx
# - Systemd service
# - CloudWatch logs agent

# Scale with:
# - Application Load Balancer
# - Auto Scaling Group
# - RDS for database (optional)
```

---

## Frontend Deployment

### Option 1: Static Hosting (Vercel/Netlify)

```bash
# Deploy to Vercel
npm install -g vercel
vercel --prod

# Or Netlify
npm install -g netlify-cli
netlify deploy --prod --dir=frontend
```

### Option 2: CDN (CloudFlare)

```bash
# Configure in CloudFlare:
# 1. Add domain
# 2. Update nameservers
# 3. Create Page Rule:
#    - URL: example.com/api/v1/*
#    - Bypass Cache
#    - Forward to: api.example.com
# 4. Cache Everything else
# 5. Enable HTTPS
```

### Option 3: S3 + CloudFront

```bash
# Upload to S3
aws s3 sync frontend/ s3://example.com --delete

# Create CloudFront distribution
# - Origin: S3 bucket
# - Cache behaviors
# - SSL certificate
# - Alias: example.com
```

---

## Database Setup

### MongoDB Atlas Configuration

1. **Create Cluster**
   - Cloud Provider: AWS/GCP/Azure
   - Region: Same as backend (us-east-1)
   - Tier: M5 (2 vCPU, 4GB RAM) for production
   - Enable backup

2. **Configure Network**
   - IP Whitelist: Only backend server IP
   - Enable VPC peering (if backend in private network)

3. **Create Database User**
   ```
   Username: ecommerce_prod
   Password: [generate strong password]
   Permissions: readWrite on E_Commerce_Production only
   ```

4. **Enable Audit Logs**
   - Project Settings → Audit
   - Log all operations

5. **Setup Backup**
   - Backup frequency: Daily
   - Retention: 7 days
   - Backup location: us-east-1

### Create Indexes
```javascript
db.users.createIndex({ email: 1 }, { unique: true });
db.users.createIndex({ role: 1 });
db.products.createIndex({ category: 1 });
db.products.createIndex({ name: "text", description: "text" });
db.orders.createIndex({ user_id: 1, created_at: -1 });
```

---

## Monitoring & Logging

### Application Monitoring

```bash
# Option 1: Sentry (Error Tracking)
pip install sentry-sdk

# In main.py
import sentry_sdk
sentry_sdk.init(
    dsn="https://key@sentry.io/project",
    environment="production",
    traces_sample_rate=0.1
)

# Option 2: DataDog
pip install datadog

# Option 3: New Relic
pip install newrelic
```

### Log Aggregation

```bash
# Centralize logs to MongoDB
# Already configured in utils/logger.py

# Or use external service:
# - DataDog
# - Splunk
# - ELK Stack
# - CloudWatch

# Tail logs
docker logs -f ecommerce

# Or Nginx logs
tail -f /var/log/nginx/access.log
```

### Performance Monitoring

```bash
# Application Insights (Azure)
pip install opencensus-ext-azure

# Key metrics to monitor:
# - API response time (target: < 200ms)
# - Database query time (target: < 100ms)
# - Error rate (target: < 0.1%)
# - CPU usage (target: < 70%)
# - Memory usage (target: < 80%)
# - Disk usage (target: < 85%)
```

---

## Performance Optimization

### Backend Optimization

```python
# Enable caching
from fastapi_cache2 import FastAPICache2
from fastapi_cache2.backends.redis import RedisBackend

# Or use MongoDB for caching
# - Cache product listings
# - Cache user profiles
# - Cache admin dashboards

# Connection pooling
# - Already optimized with Motor (async)
# - Connection pool size: 50-100

# Query optimization
# - Use indexes (created above)
# - Pagination (20 items/page)
# - Select only needed fields

db.products.find(
    {},
    { "name": 1, "price": 1 }  # Only needed fields
).skip(20).limit(20)
```

### Frontend Optimization

```html
<!-- Compress assets -->
<!-- Images: WebP format, optimized -->
<!-- CSS: Minified in production -->
<!-- JS: Bundled and minified -->

<!-- Lazy loading -->
<img src="product.jpg" loading="lazy" />

<!-- Async scripts -->
<script src="api.js" async></script>

<!-- Prefetch DNS -->
<link rel="dns-prefetch" href="//api.example.com" />
```

### Database Optimization

```
1. ✅ Indexes on frequently queried fields
2. ✅ Pagination (20-100 items/page)
3. ✅ Query projection (select needed fields only)
4. ✅ Connection pooling (50-100 connections)
5. ✅ Read preference: nearest (primary + replicas)
6. ✅ Write concern: acknowledged
```

---

## Disaster Recovery

### Backup Strategy

```bash
# Automated Backups
# MongoDB Atlas: Daily snapshots (7-day retention)

# Manual Backup
mongodump --uri="mongodb+srv://..." --out=./backup

# Restore from Backup
mongorestore --uri="mongodb+srv://..." ./backup
```

### Recovery Procedures

#### Scenario 1: Database Corrupted
1. Restore from latest backup
2. Verify data integrity
3. Update frontend cache
4. Run health checks

#### Scenario 2: Server Down
1. Restart application (systemctl restart ecommerce)
2. Verify database connection
3. Run migration scripts
4. Monitor for issues

#### Scenario 3: Security Breach
1. Revoke all active tokens (clear token blacklist)
2. Reset user passwords
3. Review audit logs
4. Apply security patch
5. Notify users

#### Scenario 4: Data Loss
1. Restore from backup
2. Replay audit logs if partial restore
3. Verify data consistency
4. Update frontend cache
5. Communicate with users

### Health Checks

```bash
# API Health
curl https://api.example.com/api/v1/products -I

# Database Health
python -c "from database import client; client.admin.command('ping')"

# Disk Space
df -h | grep -E "^/dev"

# Memory Usage
free -h

# Process Status
systemctl status ecommerce
```

---

## Deployment Checklist (Final)

### 1 Week Before
- [ ] Review security checklist
- [ ] Verify all environment variables
- [ ] Test database backup/restore
- [ ] Run full test suite
- [ ] Code review completed

### 1 Day Before
- [ ] Notify team of deployment
- [ ] Prepare rollback plan
- [ ] Document deployment steps
- [ ] Verify DNS records
- [ ] Test SSL certificate

### Deployment Day
- [ ] Disable analytics (don't count internal traffic)
- [ ] Deploy backend
- [ ] Deploy frontend
- [ ] Run smoke tests
- [ ] Monitor logs and errors
- [ ] Enable analytics

### After Deployment
- [ ] Monitor for 24 hours
- [ ] Check error rates
- [ ] Verify API response times
- [ ] Test all major features
- [ ] Collect user feedback
- [ ] Document any issues

---

**Last Updated:** 2026-05-21  
**Version:** 2.0.0  
**Status:** ✅ Production Ready
