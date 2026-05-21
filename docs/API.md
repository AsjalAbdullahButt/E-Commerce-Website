# E-Commerce API Documentation

**API Version:** v1  
**Base URL:** `http://localhost:8000/api/v1`  
**Authentication:** JWT Bearer Token

---

## Table of Contents
1. [Authentication Endpoints](#authentication-endpoints)
2. [Product Endpoints](#product-endpoints)
3. [Order Endpoints](#order-endpoints)
4. [User Endpoints](#user-endpoints)
5. [Admin Endpoints](#admin-endpoints)
6. [Rate Limiting](#rate-limiting)
7. [Error Handling](#error-handling)

---

## Authentication Endpoints

### Register User
**POST** `/auth/register`

Request:
```json
{
  "email": "user@example.com",
  "password": "SecurePass123",
  "name": "John Doe"
}
```

Response (201):
```json
{
  "id": "507f1f77bcf86cd799439011",
  "email": "user@example.com",
  "name": "John Doe",
  "role": "customer"
}
```

Rate Limit: 3/minute

---

### Login
**POST** `/auth/login`

Request:
```json
{
  "email": "user@example.com",
  "password": "SecurePass123"
}
```

Response (200):
```json
{
  "access_token": "eyJhbGc...",
  "refresh_token": "eyJhbGc...",
  "user": {
    "id": "507f1f77bcf86cd799439011",
    "email": "user@example.com",
    "role": "customer"
  }
}
```

Rate Limit: 5/minute

---

## Product Endpoints

### Get All Products
**GET** `/products?category=electronics&skip=0&limit=20`

Response (200):
```json
{
  "total": 100,
  "items": [
    {
      "id": "507f1f77bcf86cd799439011",
      "name": "Product Name",
      "description": "Description",
      "price": 99.99,
      "stock": 50,
      "category": "electronics",
      "image_url": "https://...",
      "rating": 4.5
    }
  ]
}
```

---

### Get Product by ID
**GET** `/products/{product_id}`

Response (200):
```json
{
  "id": "507f1f77bcf86cd799439011",
  "name": "Product Name",
  "description": "Description",
  "price": 99.99,
  "stock": 50,
  "category": "electronics"
}
```

---

## Order Endpoints

### Create Order
**POST** `/orders`  
**Auth Required:** Yes

Request:
```json
{
  "items": [
    {
      "product_id": "507f1f77bcf86cd799439011",
      "quantity": 2
    }
  ],
  "shipping_address": "123 Main St, City, State",
  "promo_code": "SAVE10"
}
```

Response (201):
```json
{
  "id": "607f1f77bcf86cd799439012",
  "user_id": "507f1f77bcf86cd799439011",
  "total": 199.98,
  "status": "pending",
  "created_at": "2026-05-21T10:30:00Z"
}
```

---

### Get User Orders
**GET** `/orders`  
**Auth Required:** Yes

Response (200):
```json
{
  "total": 5,
  "items": [
    {
      "id": "607f1f77bcf86cd799439012",
      "total": 199.98,
      "status": "delivered",
      "created_at": "2026-05-21T10:30:00Z"
    }
  ]
}
```

---

## User Endpoints

### Get Profile
**GET** `/users/profile`  
**Auth Required:** Yes

Response (200):
```json
{
  "id": "507f1f77bcf86cd799439011",
  "email": "user@example.com",
  "name": "John Doe",
  "phone": "1234567890",
  "address": "123 Main St",
  "role": "customer"
}
```

---

### Update Profile
**PUT** `/users/profile`  
**Auth Required:** Yes

Request:
```json
{
  "name": "John Doe Updated",
  "phone": "0987654321",
  "address": "456 Oak Ave"
}
```

Response (200):
```json
{
  "id": "507f1f77bcf86cd799439011",
  "email": "user@example.com",
  "name": "John Doe Updated",
  "phone": "0987654321"
}
```

---

## Admin Endpoints

### Dashboard Stats
**GET** `/admin/dashboard`  
**Auth Required:** Yes (Admin only)

Response (200):
```json
{
  "total_users": 150,
  "total_orders": 320,
  "total_revenue": 15000.50,
  "pending_orders": 12,
  "top_products": [...]
}
```

---

### Get All Users (Admin)
**GET** `/admin/users?skip=0&limit=20`  
**Auth Required:** Yes (Admin only)

Response (200):
```json
{
  "total": 150,
  "items": [...]
}
```

---

## Rate Limiting

Endpoints are protected with rate limiting per IP:

| Endpoint Group | Limit |
|---|---|
| Login | 5/minute |
| Register | 3/minute |
| Orders | 10/minute |
| General | 60/minute |

**Response Header:**
```
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 45
X-RateLimit-Reset: 1621597800
```

**Rate Limit Exceeded (429):**
```json
{
  "detail": "429 Too Many Requests: 60 per 1 minute"
}
```

---

## Error Handling

### Standard Error Response

```json
{
  "detail": "Error message describing what went wrong"
}
```

### Common Status Codes

| Status | Meaning |
|---|---|
| 200 | Success |
| 201 | Created |
| 400 | Bad Request (validation error) |
| 401 | Unauthorized (missing/invalid auth) |
| 403 | Forbidden (insufficient permissions) |
| 404 | Not Found |
| 429 | Too Many Requests |
| 500 | Internal Server Error |

### Authentication Errors

**Missing Token (401):**
```json
{
  "detail": "Not authenticated"
}
```

**Invalid Token (401):**
```json
{
  "detail": "Invalid authentication credentials"
}
```

**Expired Token (401):**
```json
{
  "detail": "Token has expired"
}
```

---

## Headers

### Request Headers
```
Authorization: Bearer {access_token}
Content-Type: application/json
X-Requested-With: XMLHttpRequest
```

### Response Headers
```
Content-Type: application/json
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
X-XSS-Protection: 1; mode=block
```

---

## Pagination

List endpoints support pagination:

Query Parameters:
- `skip`: Number of items to skip (default: 0)
- `limit`: Number of items to return (default: 20, max: 100)

Example:
```
GET /products?skip=20&limit=10
```

---

## Timestamps

All timestamps use ISO 8601 format:
```
2026-05-21T10:30:00Z
```

---

## Webhooks & Events

### Order Status Update
When an order status changes, a webhook is sent to registered endpoints:

```json
{
  "event": "order.status_changed",
  "timestamp": "2026-05-21T10:30:00Z",
  "data": {
    "order_id": "607f1f77bcf86cd799439012",
    "status": "shipped",
    "updated_at": "2026-05-21T10:30:00Z"
  }
}
```

---

## Testing

### Using cURL

```bash
# Register
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"Pass123","name":"Test"}'

# Login
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"Pass123"}'

# Get Products
curl http://localhost:8000/api/v1/products
```

---

**Last Updated:** 2026-05-21  
**API Version:** v1.0.0
