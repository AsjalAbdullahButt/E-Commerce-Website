# Schema & Contract Audit — STEP 0 findings

Scope: read backend/routes, services, models, schemas, middleware, database.py, main.py in full;
read frontend/shared/js, frontend/js, frontend/admin/js, and relevant inline `<script>` blocks.
This file is the field-inventory + divergence map required before any fix. Everything below is
grep/read-verified against the actual code, not assumed.

## Collections (database.py)
`users`, `products`, `orders`, `reviews`, `wishlist`, `promos`, `admin_users`, `riders`,
`inventory_history`, `audit_logs`, `notifications` (notifications_col is declared but never
referenced anywhere — dead collection, out of scope to build a feature for it).

---

## 1. PRODUCTS — two incompatible writers on `products_col`

**Path A — flat schema (the one actually seeded and actually used by the live customer site):**
- `models/product.py::ProductCreate/ProductUpdate` — fields: `name, price, description, category,
  images, sizes: [str], colors: [{name,hex}], stock: int`. No `is_deleted`, no `variants`, no
  `total_stock`.
- `routes/products.py` — mounted at `/products` (main.py). POST/PUT write the flat doc above
  (`is_active`, `rating`, `review_count`, ISO-string `created_at/updated_at`). GET list/get read
  straight from the doc (query `{"is_active": True}`, no `is_deleted` filter — works with either
  shape, but that's incidental).
- `seed/seed_db.py` inserts products in this flat shape directly.
- `frontend/js/shop.js`, `frontend/js/product.js`, `frontend/js/checkout.js` (customer-facing,
  live) all call `GET /products` / `GET /products/{id}` and read `p.sizes`, `p.colors[].name`,
  `p.price` — i.e. they expect the flat shape.
- `routes/orders.py::place_order` (the REAL, mounted checkout endpoint) decrements stock with:
  ```
  products_col.update_one({"_id": oid, "stock": {"$gte": qty}}, {"$inc": {"stock": -qty}})
  ```
  This only matches documents that have a top-level `stock` field.

**Path B — variants[] schema (what the ADMIN PANEL actually writes today):**
- `schemas/admin.py::ProductCreate/ProductVariant` — fields: `name, description, category, price,
  discount_percentage, variants: [{size,color,sku,stock}], tags, images`.
- `models/admin.py::product_document()` — writes `variants`, `total_stock` (derived), `is_active:
  True`, **`is_deleted: False`**, native `datetime` timestamps.
- `services/product.py::ProductService` — `get_product`/`list_products`/`get_low_stock_items` all
  filter `{"is_deleted": False}`.
- `routes/admin.py` `/admin/products*` — calls `ProductService`. **Confirmed this is the endpoint
  the real admin UI hits**: `frontend/admin/js/admin-config.js` → `PRODUCTS.CREATE = '/admin/products'`,
  and `frontend/admin/js/products.js::getProductPayload()` builds exactly the `variants[]` shape
  and never touches `sizes/colors/stock`.

**Consequence (the Task-3 bug, confirmed):** a product created through the real, working admin UI
(Path B) has no top-level `stock` field. When a customer checks out, `place_order`'s atomic
decrement query `{"stock": {"$gte": qty}}` matches nothing → `modified_count == 0` →
`HTTPException("Stock was just taken ... please refresh")` on a product that has plenty of stock.
Read-side is partially masked because `place_order` does `product.get("stock",
product.get("total_stock", 0))` for the availability check (so the initial check passes), but the
write-side decrement silently fails every time. This is 100% reproducible: admin creates product →
customer buys it → order placement always 400s.

**Decision (per task instructions): variants[] is canonical.** Plan:
- Replace `models/product.py` flat `ProductCreate/ProductUpdate` and `routes/products.py`'s
  POST/PUT/DELETE with the variants[] shape (reuse `schemas/admin.py` models or a customer-safe
  subset), backed by `ProductService`/`InventoryService` so there is one write path.
- Rewrite `routes/products.py` GET list/get to serialize `variants[]` (already stored) and expose
  a derived `sizes`/`colors` convenience list for the frontend if useful, OR update the frontend to
  read `variants[]` directly (chosen: update frontend, see below, since variants carry
  size+color+stock combos the old flat shape can't express — needed for real per-variant stock).
- Rewrite `place_order`'s decrement to target the matching variant inside `variants[]`
  (`{"_id": oid, "variants": {"$elemMatch": {"size":..,"color":..,"stock": {"$gte": qty}}}}` with
  positional `$` update), recomputing `total_stock`.
- `is_deleted` vs `is_active`: **decision — drop `is_deleted`, make `is_active` the single
  visibility flag.** `product_document()` currently sets both; `ProductService` filters on
  `is_deleted` only (not `is_active`!) in `list_products`/`get_product`, meaning a product with
  `is_active: False` (soft-deleted via the OLD `routes/products.py::delete_product`, which only
  sets `is_active: False`) would still show up via `/admin/products`. Both delete paths need to
  collapse to one: set `is_active: False` only, everywhere, and remove `is_deleted` from every
  query/write. No migration needed for new field removal (extra field is harmless), but existing
  `is_deleted: True` docs (if any) must be migrated to `is_active: False` — write a one-time
  migration script.
- Frontend: `frontend/customer/product.html`'s size/color selectors are **hardcoded static HTML**
  (S/M/L/XL, Black/White/Blue swatches) — not wired to any product data at all, regardless of
  schema. This must be fixed too (task 10 explicitly requires "working size/color selectors"):
  `frontend/js/product.js` needs to render size/color options from `product.variants`, and only
  enable Add-to-Cart for combos with `stock > 0`; cart/checkout need to send the variant's
  size+color (already does, as free strings) so the backend can look up the right variant.

---

## 2. ORDERS — two incompatible writers on `orders_col`

**Path A — the real one (checkout, rider, seed data all agree on this shape):**
- `routes/orders.py::place_order` (mounted at `/orders`, real checkout) writes: `user_id, items[],
  shipping_address, payment_method, payment_reference, promo_code, subtotal, discount, tax,
  delivery_fee, total, status, rider_id, status_history: [{status,timestamp,note}]`. ISO-string
  timestamps. **No `is_deleted`.**
- `routes/rider.py` reads/writes the same shape (`status`, `status_history`, `rider_id`).
- `seed/seed_db.py` sample orders use this exact shape.
- `frontend/js/checkout.js`, `frontend/rider/*.html` all agree with this shape.

**Path B — dead-ish, but reachable via `/admin/orders*`:**
- `models/admin.py::order_document()` — `total_price, discount_applied, final_price, timeline: [...],
  is_deleted: False`. **Never actually called anywhere** (grepped `order_document` — zero call
  sites; it's genuinely dead code, unlike `product_document` which IS called).
- `services/order_user.py::OrderService` — reads/writes `is_deleted` filter, `timeline` (not
  `status_history`), and status-transition table `pending→confirmed→packed→shipped→delivered→returned`.
  This service backs `routes/admin.py`'s `/admin/orders*` endpoints (get/list/update-status/note),
  which the working admin UI (`admin-config.js` → `ORDERS.LIST = '/admin/orders'`) actually calls.

**Consequence:** admin panel's Orders page (if built out — currently `admin/orders.html` has no
JS wired to it at all, see §4 below) would call `/admin/orders` → `OrderService.list_orders()` →
filters `{"is_deleted": False}` → **matches zero real orders**, since real orders never set that
field. Symmetrically, `OrderService.get_order`/`update_order_status` push into `timeline`, a field
the rider app and customer tracking page never read (they read `status_history`). Whichever admin
order UI gets built must not go through the current `OrderService`.

**Decision (per task instructions): routes/orders.py's shape is canonical.**
- Rewrite `services/order_user.py::OrderService` to operate on `status`/`status_history`/`total`,
  drop the `is_deleted` filter entirely (no migration needed — just stop filtering; nothing sets it
  today except dead code).
- Delete `models/admin.py::order_document`/`order_status_timeline_entry` once nothing calls them
  (confirmed zero other call sites besides their own definitions).
- Status-transition validation currently exists ONLY in `OrderService.update_order_status`
  (`pending→confirmed→packed→shipped→delivered→returned`, `cancelled` terminal). The three other
  status-mutating endpoints have **no transition validation at all**:
  - `routes/orders.py::update_status` (PATCH `/orders/{id}/status`) — any status → any status, only
    checks role is admin/rider.
  - `routes/rider.py::update_delivery_status` — restricts to `{shipped, delivered}` values only,
    no check on the order's *current* status (a rider could "ship" an already-delivered order).
  - `routes/rider.py::complete_delivery` — the only one with a real transition check
    (`status == "shipped"` required).
  - `routes/orders.py::cancel_order` — correctly requires `status == "pending"`.
  Plan: extract one shared transition table + helper (e.g. `utils/order_transitions.py`) and apply
  it in all four places.

---

## 3. Checkout stock bug — root cause confirmed (see §1). Fix ships together with the products
migration (variant-aware atomic decrement) + new integration test per task 3/10.

---

## 4. RIDER MODULE — audit of what exists vs. what's missing

Backend (`routes/rider.py`, mounted `/rider`, guarded by `require_rider`):
`GET /orders` (assigned, non-delivered), `PATCH /orders/{id}/status`, `GET /profile`,
`PATCH /profile` (**query params** `name`/`phone`, not JSON body — confirmed bug #4 as described),
`PATCH /status` (availability), `GET /earnings`, `POST /orders/{id}/complete`, `GET /stats`,
`GET /orders/history`.

`GET /stats` returns `{delivered, active, earnings}` where `active = count({status != "delivered"})`
— this INCLUDES cancelled orders assigned to the rider as "active", which is arguably also a bug,
but not explicitly listed; noting it, low priority.

**Confirmed dashboard bug:** `frontend/rider/dashboard.html` inline script calls `GET /rider/orders`
(which explicitly filters `status: {"$in": ["shipped","confirmed","packed"]}` — i.e. **excludes**
delivered orders by design) and then computes `stat-delivered` as
`orders.filter(o => o.status === 'delivered').length` — always 0, exactly as described in the task.
Fix: point at `/rider/stats` or `/rider/earnings` instead, which correctly compute delivered counts
server-side.

**No admin-facing rider management exists at all** — confirmed via grep: zero endpoints in
`routes/admin.py` reference `riders_col`. `assign_rider` (`routes/orders.py`) takes a raw
`rider_id: str` query param and never validates it exists in `riders_col`, never checks
active/available status, never checks the order isn't already delivered/cancelled. There is also
no `POST /riders` (create) anywhere — the only way a `riders_col` document gets created today is
manual DB insert (no seed, no route). This is a hard blocker for testing task 10's e2e path and
must be built from scratch: `POST /admin/riders`, `GET /admin/riders`, `PATCH
/admin/riders/{id}/activate|deactivate`, `GET /admin/riders/{id}/active-orders`, plus
`frontend/admin/riders.html` + `frontend/admin/js/riders.js`.

Rider password field: `routes/auth.py`'s unified login checks `rider.get("password")` (not
`password_hash`) — so the new admin "create rider" endpoint must hash and store under `"password"`
to stay consistent with login.

---

## 5. ACCESS CONTROL duplication — confirmed exactly as described
`routes/users.py` (`/users/{id}/ban|unban`, DELETE `/users/{id}`) guarded by
`middleware/auth_middleware.py::require_admin`, which only checks role membership in
`{admin,super_admin,manager,support}` — no granular permission check. The real permission matrix
(`utils/permissions.py`) says `manager`/`support` do NOT have `user:ban`, but `/admin/users/*`
(routes/admin.py, the intended gated path) DOES enforce it via `check_permission(admin_data,
"user:ban")`.

**Extra finding not in the original list, same root cause:** `middleware/auth_middleware.py
::get_current_user` branches strictly on `role == "admin"` / `role == "rider"` / else-customer to
pick which collection to query. Any admin whose *actual* role is `super_admin`/`manager`/`support`
(JWT `role` claim carries the real sub-role — confirmed in `services/admin_auth.py
::AdminAuthService.authenticate`, which does `create_access_token(id, admin.get("role", "admin"))`)
falls into the `else` branch and gets looked up in `users_col` (wrong collection) → 401 "User not
found". So today, `require_admin`-gated routes (`routes/users.py`, `routes/orders.py`'s admin
paths) are in practice reachable only by the literal `role == "admin"` sub-role, not
super_admin/manager/support — despite `require_admin`'s allow-list claiming to include them. This
resolves itself once `routes/users.py` is deleted and callers go through `verify_admin_token`
(`middleware/admin_auth.py`), which correctly looks up `admin_users_col` regardless of the role
string.

Fix: delete `routes/users.py` + its `main.py` mount; confirm no frontend references `/users/*`
(grepped — none; admin frontend already uses `/admin/users/*` exclusively via `admin-config.js`).

---

## 6. Extra finding — admin authentication is split into two incompatible systems (not in
original list, but same "two schemas/two contracts" class of bug, directly blocks task 10's e2e
admin flow)

- **Real, working flow:** `frontend/admin/login.html` → `adminAPI.login()` → `POST
  /admin/auth/login` → stores `admin_access_token` / `admin_refresh_token` / `admin_data` in
  localStorage (`STORAGE_KEYS` from `admin-config.js`). `frontend/admin/products.js` and
  `promos.js` correctly gate on `STORAGE_KEYS.AUTH_TOKEN`/`ADMIN_DATA` and call `/admin/*` via
  `admin-api.js`, which attaches `Authorization: Bearer <admin_access_token>`. This path works
  end-to-end and matches `verify_admin_token`.
- **Broken flow:** `frontend/admin/dashboard.html` and `frontend/admin/orders.html` each have an
  inline "AUTH GUARD" `<script>` that checks `localStorage.ecom_token` / `ecom_user` (the
  *customer* shared-login keys from `frontend/shared/js/auth.js`, set only by `POST /auth/login`)
  — **not** `admin_access_token`/`admin_data`. Since `admin/login.html` never sets `ecom_token`,
  visiting `dashboard.html` right after a successful admin login immediately fails the guard and
  redirects to `../auth/login.html`. `dashboard.html` does go on to load `admin-api.js`/
  `analytics.js` (which use the correct keys) — but the inline guard runs first and bounces the
  user away before that code ever executes. **Net effect: the admin dashboard is unreachable from
  the real admin login page today.**
- `orders.html` has the same broken guard, AND loads a script `../js/admin.js` that **does not
  exist anywhere in the repo** (confirmed via glob) — so even past the auth guard, the page has
  zero wiring to load or render orders. This page is currently a non-functional stub.
- Fix: make `dashboard.html`/`orders.html` use the same `requireAuth()`-style guard as
  `products.js`/`promos.js` (checking `STORAGE_KEYS`), and build `frontend/admin/js/orders.js`
  (there is currently no admin order-management UI at all — needed for task 10's e2e path: "order
  appears in ... the admin orders list").
- This sits on top of task 8's explicitly-listed refresh-token duplication (customer: httpOnly
  cookie via `/auth/refresh`; admin: Authorization-header refresh via `/admin/auth/refresh`) — two
  separate problems in the same area, both need reconciling.

---

## 7. Other confirmed-but-not-yet-fixed items from the original task list (verified present)
- `main.py`: `TrustedHostMiddleware` commented out — confirmed (lines 30-34).
- `routes/admin.py::change_password` (`/admin/auth/change-password`) takes `old_password`/
  `new_password` as bare function params → FastAPI treats as **query params**. `routes/auth.py`
  already has the correct body-based pattern (`ChangePasswordRequest`) to mirror.
- `config/settings.py::jwt_secret: str` — no length/entropy validation at startup.
- No forgot-password flow anywhere (grepped `forgot`, `reset_token` — zero hits).
- `AdminAuthService.unlock_account` exists (`services/admin_auth.py`) but **no route calls it** —
  confirmed via grep, zero references outside its own definition.
- `utils/cache.py`/`utils/limiter.py` are process-local (`dict` + `asyncio.Lock`, and slowapi's
  default in-memory store) — confirmed, no Redis anywhere in requirements.txt or code.
- Revenue aggregations (`routes/admin.py::legacy_stats`, `dashboard_summary`, `revenue_analytics`,
  `services/dashboard.py::get_dashboard_stats/get_revenue_trend`) all `$sum: "$total"` /
  `$final_price"` over **all** orders (some scoped to `status: "delivered"`, but
  `legacy_stats`/`dashboard_summary`/`revenue_analytics` sum every order including `cancelled`) —
  confirmed, needs an explicit named gross/net split.
- Timestamps: `routes/orders.py`/`routes/products.py`/`routes/rider.py`/`routes/users.py`/
  `routes/promos.py`/`routes/wishlist.py` all use `datetime.utcnow().isoformat()` (ISO **strings**);
  `services/*.py` + `models/admin.py` use native `datetime.utcnow()` (BSON dates). Confirmed mixed
  across the codebase — standardizing means touching every write path listed here.
- Reviews: `routes/reviews.py::add_review` already DOES check for a delivered order containing the
  product before allowing a review (`orders_col.find_one({"user_id":..., "status": "delivered",
  "items.product_id": ...})`) — **this one is already correct**, not a bug. (Once orders schema is
  unified this still works since it only reads `status`/`items.product_id`, both present in the
  real order shape.)

## 8. Fields NOT touched by this audit (confirmed consistent, no divergence found)
`wishlist_col`, `promos_col` (both `routes/promos.py` and `services/discount.py` write compatible
`code/discount_type/discount_value/min_order/max_uses/uses/is_active/expires_at` shapes — the admin
`/admin/discounts` path via `DiscountService` and the customer `/promos` path via
`routes/promos.py` independently write the *same* field names, so no conflict today, though they
are still two separate code paths for the same collection worth noting for a future consolidation
— not in original list, low priority, not fixing now), `reviews_col`, `audit_logs_col`.
