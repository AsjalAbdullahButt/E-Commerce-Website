import csv
import io
from typing import Iterable

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.order import Order
from db.product import Product
from services.order_user import OrderService
from services.product import ProductService

# ── Export ───────────────────────────────────────────────────────────────

PRODUCT_CSV_COLUMNS = [
    "product_name", "description", "category", "price", "discount_percentage",
    "tags", "image_url", "is_active", "size", "color", "sku", "stock",
]

ORDER_CSV_COLUMNS = [
    "order_id", "customer", "status", "payment_method", "payment_status",
    "subtotal", "discount", "tax", "delivery_fee", "total",
    "full_name", "phone", "address", "city", "postal_code", "created_at",
]


def _csv_response_body(rows: Iterable[list], columns: list[str]) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(columns)
    writer.writerows(rows)
    return buf.getvalue()


async def export_products_csv(db: AsyncSession) -> str:
    """One row per (product, variant) — the same flat shape import_products_csv() expects back,
    so an admin can export, edit in a spreadsheet, and re-import. Reuses
    ProductService.list_products() rather than a fresh query (extends, doesn't duplicate)."""
    products, _ = await ProductService.list_products(db, limit=1_000_000, skip=0)
    rows = []
    for p in products:
        tags = ";".join(p.get("tags") or [])
        image_url = (p.get("images") or [None])[0] or ""
        variants = p.get("variants") or [{"size": "", "color": "", "sku": "", "stock": 0}]
        for v in variants:
            rows.append([
                p["name"], p["description"], p["category"], p["price"], p["discount_percentage"],
                tags, image_url, p["is_active"], v.get("size", ""), v.get("color", ""),
                v.get("sku", ""), v.get("stock", 0),
            ])
    return _csv_response_body(rows, PRODUCT_CSV_COLUMNS)


async def export_orders_csv(db: AsyncSession) -> str:
    """Reuses OrderService.list_orders() rather than a fresh query."""
    orders, _ = await OrderService.list_orders(db, limit=1_000_000, skip=0)
    rows = []
    for o in orders:
        customer = o.get("user_id") or o.get("guest_email") or ""
        rows.append([
            o["id"], customer, o["status"], o.get("payment_method", ""), o.get("payment_status", ""),
            o["subtotal"], o["discount"], o["tax"], o["delivery_fee"], o["total"],
            o["shipping_address"]["full_name"], o["shipping_address"]["phone"],
            o["shipping_address"]["address"], o["shipping_address"]["city"], o["shipping_address"]["postal_code"],
            o["created_at"].isoformat() if o.get("created_at") else "",
        ])
    return _csv_response_body(rows, ORDER_CSV_COLUMNS)


# ── Import ───────────────────────────────────────────────────────────────

def _parse_product_groups(file_bytes: bytes) -> tuple[list[dict], list[dict]]:
    """Parses the flat one-row-per-variant CSV into per-product groups, keyed by
    (name, category) in first-seen order. Returns (groups, parse_errors) — a malformed row is
    recorded and skipped rather than aborting the whole file."""
    text = file_bytes.decode("utf-8-sig")  # -sig strips an Excel-added BOM, if present
    reader = csv.DictReader(io.StringIO(text))

    groups: dict[tuple, dict] = {}
    order: list[tuple] = []
    errors: list[dict] = []

    for i, row in enumerate(reader, start=2):  # row 1 is the header
        try:
            name = (row.get("product_name") or "").strip()
            category = (row.get("category") or "").strip()
            if not name or not category:
                raise ValueError("product_name and category are required")

            price = float(row["price"])
            discount_percentage = float(row.get("discount_percentage") or 0)
            stock = int(float(row.get("stock") or 0))

            key = (name.lower(), category.lower())
            if key not in groups:
                groups[key] = {
                    "name": name,
                    "description": (row.get("description") or "").strip(),
                    "category": category,
                    "price": price,
                    "discount_percentage": discount_percentage,
                    "tags": [t.strip() for t in (row.get("tags") or "").split(";") if t.strip()],
                    "images": [row["image_url"].strip()] if (row.get("image_url") or "").strip() else [],
                    "is_active": str(row.get("is_active", "true")).strip().lower() not in ("false", "0", ""),
                    "variants": [],
                }
                order.append(key)

            groups[key]["variants"].append({
                "size": (row.get("size") or "").strip(),
                "color": (row.get("color") or "").strip(),
                "sku": (row.get("sku") or "").strip(),
                "stock": stock,
            })
        except (ValueError, KeyError) as e:
            errors.append({"row": i, "error": str(e)})

    return [groups[k] for k in order], errors


async def import_products_csv(db: AsyncSession, file_bytes: bytes, admin_id: str) -> dict:
    """Creates a new product per group whose (name, category) doesn't already exist, otherwise
    updates the existing one — ProductService.update_product() already replaces the whole variant
    set on update, so re-importing an edited export is the natural "upsert" path, not a special
    case. Each group is wrapped in its own SAVEPOINT (db.begin_nested()) so one bad group can't
    roll back groups that already succeeded earlier in the same file."""
    product_groups, errors = _parse_product_groups(file_bytes)

    created = 0
    updated = 0
    for group in product_groups:
        try:
            async with db.begin_nested():
                variants = group.pop("variants")
                is_active = group.pop("is_active")  # not a create_product() param — only applies on update
                existing = (await db.execute(
                    select(Product).where(Product.name == group["name"], Product.category == group["category"])
                )).scalar_one_or_none()

                if existing:
                    await ProductService.update_product(
                        db, existing.id, {**group, "is_active": is_active, "variants": variants}, admin_id,
                    )
                    updated += 1
                else:
                    await ProductService.create_product(db, variants=variants, admin_id=admin_id, **group)
                    created += 1
        except Exception as e:
            errors.append({"row": f"product '{group.get('name')}'", "error": str(e)})

    return {"created": created, "updated": updated, "errors": errors}


def _parse_order_status_rows(file_bytes: bytes) -> tuple[list[dict], list[dict]]:
    text = file_bytes.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))

    rows = []
    errors = []
    for i, row in enumerate(reader, start=2):
        order_id = (row.get("order_id") or "").strip()
        status = (row.get("status") or "").strip()
        if not order_id or not status:
            errors.append({"row": i, "error": "order_id and status are required"})
            continue
        rows.append({"order_id": order_id, "status": status, "note": (row.get("note") or "").strip()})
    return rows, errors


async def bulk_update_order_status_csv(db: AsyncSession, file_bytes: bytes, admin_id: str) -> dict:
    """Bulk order-status update via CSV (order_id,status,note columns) — e.g. importing a
    fulfillment center's "these orders shipped today" export. Reuses
    OrderService.update_order_status() for every row, so the same transition validation and
    customer-notification email as a single manual status change still apply — no parallel
    status-change code path. Each row gets its own SAVEPOINT so one invalid transition doesn't
    roll back the rows already applied earlier in the file."""
    update_rows, errors = _parse_order_status_rows(file_bytes)

    updated = 0
    for row in update_rows:
        try:
            async with db.begin_nested():
                await OrderService.update_order_status(db, row["order_id"], row["status"], row["note"], admin_id)
                updated += 1
        except HTTPException as e:
            errors.append({"row": row["order_id"], "error": e.detail})
        except Exception as e:
            errors.append({"row": row["order_id"], "error": str(e)})

    return {"updated": updated, "errors": errors}
