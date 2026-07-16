# Schema & Contract Audit — STEP 0 findings

Scope: read backend/routes, services, models, schemas, middleware, database.py, main.py in full;
read frontend/shared/js, frontend/js, frontend/admin/js, and relevant inline `<script>` blocks.
This file is the field-inventory + divergence map required before any fix. Everything below is
grep/read-verified against the actual code, not assumed.

## Collections (database.py)
`users`, `products`, `orders`, `reviews`, `wishlist`, `promos`, `admin_users`, `riders`,
`inventory_history`, `audit_logs`. (`notifications` was declared but never referenced anywhere —
removed in the Phase 1 polish pass, see §10.)

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

## 7b. Found during implementation (not in original STEP 0 pass) — `log_to_db` call signature
`utils/logger.py::log_to_db(level, module, message, meta=None)` requires `module` as its 2nd
positional arg. `routes/admin.py`, `main.py`, `middleware/admin_auth.py`, and
`services/admin_auth.py` call it correctly with `__name__` as that argument. But
`routes/orders.py`, `routes/rider.py`, `routes/products.py`, `routes/promos.py`,
`routes/reviews.py`, and `routes/auth.py` all called it with only 3 positional args
(`level, message_text, meta_dict`) — so `message_text` landed in the `module` param and the meta
dict landed in the `message` param, silently discarding the intended `meta` (always `{}`). Every
audit-log entry written by those ~24 call sites had garbled `module`/`message` fields and no
`meta`, which is what the admin Logs page (`frontend/admin/logs.html`) reads. Fixed by inserting
`__name__` as the 2nd argument at every Pattern-B call site (mechanical, no behavior change to
the calling code otherwise) — found while implementing task 8's forgot-password logging, whose
own test needed to read `meta.reset_link` back out of `audit_logs_col`.

## 9. Polish-pass Phase 1 — timestamp standardization (2026-07-17)

Picked native `datetime` (BSON date) as the single standard, since it was already the majority
(52 vs 11 sites) and matches every `datetime` schema field in `backend/schemas/*.py` (Pydantic's
`datetime` validator accepts both a native object and an ISO string, so this was safe either way
for API responses — the real risk was intra-collection sort order, not serialization).

Converted the 11 remaining `datetime.utcnow().isoformat()` call sites to `datetime.utcnow()`:
`routes/admin.py` (rider assignment `updated_at`), `routes/wishlist.py` (`added_at`),
`routes/auth.py` (register `created_at`, change-password/reset-password/update-me `updated_at`,
forgot-password `reset_token_expires`), `routes/reviews.py` (`created_at`), `routes/rider.py`
(profile/status `updated_at`), `utils/logger.py::log_to_db` (`timestamp`), and `seed/seed_db.py`
(all product/user/order timestamps, 32 sites).

**Confirmed real bug, not just cosmetic:** `audit_logs_col` had two writers disagreeing on type —
`models/admin.py::audit_log_document` (native datetime, admin-panel actions) vs. the old
`utils/logger.py::log_to_db` (ISO string, ~24 call sites across every other route). This collection
is sorted by `timestamp: -1` in `services/admin_auth.py::AdminAuditService.get_logs` (backs the
admin Logs page). MongoDB's BSON type order ranks Date above String, so with mixed types a
"descending" sort groups all-native-first then all-string, not by actual time — the admin Logs
page has been silently showing entries out of chronological order whenever both writers
contributed. Same class of bug existed for `products_col.created_at` (seeded demo products wrote
ISO strings; admin-panel-created products already wrote native datetime via
`models/admin.py::product_document`), sorted in `services/product.py::list_products`.

**Migration for existing data:** added `backend/scripts/migrate_timestamps_to_datetime.py`
(idempotent, follows the same pattern as `migrate_products_to_variants.py`) — converts any
already-stored ISO-string `created_at`/`updated_at`/`added_at`/`timestamp`/`reset_token_expires`
fields (including `orders.status_history[].timestamp`) to native dates across every collection.
Run once against any existing dev/prod DB after deploying this change:
`python -m scripts.migrate_timestamps_to_datetime` (from `backend/`).

No schema/response-model changes were needed — every relevant Pydantic response field was already
typed `datetime`, never `str`.

## 10. Polish-pass Phase 1 — dead code removal (2026-07-17)

- `backend/routes/v1/` deleted — contained only an `__init__.py` with version constants, never
  imported/mounted anywhere (`main.py` mounts `auth`/`products`/`orders`/`reviews`/`wishlist`/
  `promos`/`rider`/`admin` directly, no `v1` prefix). No working routes existed under it, so there
  was nothing to "wire up" — pure scaffolding.
- `notifications_col` (`database.py`) deleted — zero read/write call sites anywhere in
  `backend/routes|services|middleware|main.py`; only reference was `tests/conftest.py`'s generic
  per-test collection-clear loop, updated to match.
- Three zero-call-site service methods deleted (confirmed via full-repo grep, each had no
  reference besides its own definition): `DiscountService.deactivate_discount` (services/discount.py
  — the admin UI's "Deactivate" button already goes through `update_discount({"is_active": False})`
  instead), `DiscountService.apply_discount_to_order` (services/discount.py — dead, which
  transitively left `get_discount_by_code` dead too since that was its only caller; the live
  customer-facing promo-code path is `routes/promos.py`'s independent implementation, per §8 below),
  `OrderService.get_pending_orders` (services/order_user.py — admin dashboard/stats compute the
  pending count directly via `orders_col.count_documents(...)` instead). Removed the now-unused
  `orders_col` import from `services/discount.py` left over from the second deletion.
- `class Security` in `backend/utils/helpers.py` deleted — a "backward-compatible wrapper" around
  the module-level `hash_password`/`verify_password`/`create_access_token`/`create_refresh_token`/
  `decode_token` functions; every real caller (`routes/auth.py`, `services/admin_auth.py`,
  `services/rider.py`, `middleware/admin_auth.py`) already used the module-level functions
  directly, never `Security.*`.

Verified via full `pytest` run after all Phase 1 changes (timestamps + dead code): 26/26 passing,
no import errors.

## 11. Polish-pass Phase 2 — CSRF protection + auth reconciliation (2026-07-17)

**Threat-modeled before adding anything.** Every protected endpoint (`middleware/auth_middleware.py
::get_current_user`, `middleware/admin_auth.py::verify_admin_token`/`AdminAuthMiddleware`) requires
an `Authorization: Bearer <token>` header — a cross-site request cannot forge that without already
having XSS, at which point CSRF is moot. The refresh cookies (`refresh_token`/`admin_refresh_token`)
are httpOnly + `Secure` + `SameSite=Strict`, which already blocks the cookie from being attached to
*any* cross-site request in modern browsers. So `/auth/logout` and `/admin/auth/logout` (which both
require the bearer token) were never CSRF-exploitable. The **only** genuinely cookie-only-
authenticated, state-changing endpoints are `POST /auth/refresh` and `POST /admin/auth/refresh` —
added double-submit-cookie CSRF protection there specifically (`backend/utils/csrf.py`), as explicit
defense-in-depth on top of `SameSite=Strict` (covers browsers/proxies that don't enforce it, and any
future accidental weakening of the cookie's SameSite setting).

- New non-httpOnly `csrf_token`/`admin_csrf_token` cookie, issued alongside the refresh cookie at
  login/register/refresh, rotated on every refresh. `verify_csrf()` does a constant-time compare of
  the cookie value against an `X-CSRF-Token` request header; `/refresh` checks refresh-cookie
  presence first (401 "No refresh token" if absent) then CSRF (403 if missing/mismatched), so the
  status code still distinguishes "not logged in" from "CSRF check failed."
- Frontend: `frontend/shared/js/api.js` and `frontend/admin/js/admin-api.js` read the CSRF cookie via
  `document.cookie` and echo it back as `X-CSRF-Token` on refresh calls.
- **Found and fixed a real bug while doing this:** `POST /auth/register` returned the raw
  `refresh_token` in the JSON response body (a secret leaking into the response) and never set the
  refresh/CSRF cookies at all — so a freshly-registered user had no cookie session and couldn't use
  `/auth/refresh` until they separately logged in. Now matches `/login`'s cookie contract exactly
  (verified the frontend never read `data.refresh_token` from the register response, so this is a
  pure fix, not a breaking change).
- **Found and fixed a second real bug:** the customer-facing `apiRequest()` in `shared/js/api.js`
  never called `/auth/refresh` at all — any 401 immediately cleared the session and redirected to
  login, meaning customers were silently logged out every 15 minutes (the access-token lifetime).
  The admin panel (`admin-api.js::request()`) already retried once via `refreshAccessToken()` on 401.
  Customer `apiRequest()` now does the same (dedup'd via a shared in-flight promise to avoid a
  refresh stampede when several calls 401 at once), so the two flows are now behaviorally identical,
  not just structurally identical.
- Net result: customer and admin auth are now one consistent, documented strategy — httpOnly+Secure+
  SameSite=Strict refresh cookie, sibling CSRF cookie, Bearer access token for all other calls,
  auto-refresh-and-retry-once on 401 — differing only in cookie *names* (`refresh_token`/`csrf_token`
  vs `admin_refresh_token`/`admin_csrf_token`), which is intentional so both sessions can coexist in
  the same browser without clobbering each other.

Tests: `backend/tests/test_integration/test_refresh_token.py` covers both flows — missing CSRF
header (403), wrong CSRF header (403), correct header (200 + rotation), and the pre-existing
no-cookie-at-all case (401). Full suite: 29/29 passing.

## 12. Polish-pass Phase 2 — input validation + dependency vulnerability scanning (2026-07-17)

**Input validation.** `utils/helpers.py::sanitize_input` previously only rejected NoSQL-operator
strings; extended it with control-character stripping and a `max_length` parameter (default 500,
backward compatible with every existing caller). Added Pydantic `field_validator`s calling it on
every free-text field that had none: `models/review.py::ReviewCreate.comment` (max 1000, rejects
empty-after-strip), `models/order.py::ShippingAddress` (all 5 fields) and `OrderStatusUpdate.note`,
`schemas/rider.py::RiderProfileUpdate.name/phone`, `schemas/admin.py::ProductCreate`/`ProductUpdate`
`name`/`description`/`category`. Three admin endpoints take free text as bare (query-param) function
arguments rather than a Pydantic body — `adjust_stock`'s `reason`, `add_order_note`'s `note`,
`ban_user`'s `reason` — sanitized inline in `routes/admin.py` with `ValueError` mapped to HTTP 422.
Also deleted `backend/models/product.py` (found while auditing product validation): zero call sites
anywhere in the backend — the flat `ProductCreate`/`ProductUpdate` it defined was already fully
superseded by `schemas/admin.py`'s variants[] shape per §1's migration; `routes/products.py` never
imported it. Tests: `backend/tests/test_integration/test_input_validation.py` (12 cases — oversized
input, NoSQL-operator injection, empty-after-strip, and the normal-input happy path for each
surface).

**Dependency vulnerability scanning.** `pip-audit -r backend/requirements.txt` found 23 known CVEs
across 5 packages — `requirements.txt` was pinned to versions several minors/majors behind what was
actually installed in `.venv` (and what every test in this pass has been running against all along).
Repinned to the installed, already-tested versions: `fastapi` 0.111.0→0.139.0, `uvicorn` 0.29.0→
0.51.0, `motor` 3.4.0→3.7.1, `pymongo` 4.7.1→4.17.0, `python-dotenv` 1.0.1→1.2.2, `python-jose`
3.3.0→3.5.0, `pydantic` 2.7.1→2.13.4, `pydantic-settings` 2.2.1→2.14.2, `python-multipart` 0.0.9→
0.0.32, `slowapi` 0.1.9→0.1.10 (`passlib` unchanged, already latest). This fixed 22 of 23 CVEs.
Also fixed a `FastAPIDeprecationWarning` this bump surfaced: `routes/rider.py::set_status`'s
`Query(..., regex=...)` → `Query(..., pattern=...)`.

The 1 remaining finding, `ecdsa` `PYSEC-2026-1325`, is allow-listed in CI (not silently ignored):
`ecdsa` is a transitive dependency of `python-jose` with **no fix release available upstream** (a
pure-Python ECDSA timing-side-channel class the maintainers have stated won't be patched), and this
app signs/verifies every JWT with HS256 only (`config/settings.py::jwt_algorithm`) — the vulnerable
ECDSA code path is never exercised here. Re-evaluate this exception if the app ever adds an
ECDSA-based JWT algorithm.

Added `.github/workflows/dependency-scan.yml`: runs `pip-audit` against `backend/requirements.txt`
on every push/PR that touches it, plus a weekly Monday cron (catches newly-disclosed CVEs against
unchanged pins). Verified the exact CI command passes locally (exit 0) before committing it as a
would-be-required check. No `npm audit` job yet — the frontend has no `package.json`/npm dependency
tree to scan (matches Phase 5's lint/build tooling, not yet built); a note in the workflow flags
where to add it once one exists.

Full backend suite: 41/41 passing after every change in this section (dependency repin, JWT algo
Query fix, and the input-validation additions together).

## 8. Fields NOT touched by this audit (confirmed consistent, no divergence found)
`wishlist_col`, `promos_col` (both `routes/promos.py` and `services/discount.py` write compatible
`code/discount_type/discount_value/min_order/max_uses/uses/is_active/expires_at` shapes — the admin
`/admin/discounts` path via `DiscountService` and the customer `/promos` path via
`routes/promos.py` independently write the *same* field names, so no conflict today, though they
are still two separate code paths for the same collection worth noting for a future consolidation
— not in original list, low priority, not fixing now), `reviews_col`, `audit_logs_col`.
