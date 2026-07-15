"""
One-time migration: unify the `products` collection onto the single canonical schema
(variants[] + total_stock + is_active). See NOTES_schema_audit.md §1.

Handles two legacy situations, both safe to re-run (idempotent):
  1. Flat-schema documents (`stock`/`sizes`/`colors`, no `variants`) written by the old
     routes/products.py POST/PUT endpoints or seed/seed_db.py — rebuilt into variants[],
     stock distributed evenly across the size x color combinations so total_stock is preserved.
  2. Any document still carrying a stale `is_deleted` field (either schema) — collapsed onto
     `is_active` (the single visibility flag) and the field removed.

Run: python -m scripts.migrate_products_to_variants   (from backend/, with .env configured)
"""
import asyncio
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from database import products_col


def slugify(value: str) -> str:
    return "-".join("".join(c.lower() if c.isalnum() else " " for c in str(value)).split())


def build_variants_from_flat(doc: dict) -> list[dict]:
    sizes = doc.get("sizes") or [""]
    colors = doc.get("colors") or [{"name": "Default"}]
    color_names = [c.get("name", "Default") if isinstance(c, dict) else str(c) for c in colors] or ["Default"]
    size_labels = sizes or [""]

    combos = [(s, c) for s in size_labels for c in color_names]
    total_stock = int(doc.get("stock", 0) or 0)
    base_name = doc.get("name", "product")

    n = len(combos) or 1
    per_variant = total_stock // n
    remainder = total_stock - per_variant * n

    variants = []
    for i, (size, color) in enumerate(combos):
        stock = per_variant + (1 if i < remainder else 0)
        size_label = size or "One Size"
        sku = f"{slugify(base_name)}-{slugify(size_label)}-{slugify(color)}-{i + 1}".replace("--", "-")
        variants.append({"size": size_label, "color": color, "sku": sku, "stock": stock})
    return variants


async def migrate() -> None:
    migrated_flat = 0
    cleaned_is_deleted = 0

    async for doc in products_col.find({}):
        updates: dict = {}
        unset: dict = {}

        if "variants" not in doc and "stock" in doc:
            variants = build_variants_from_flat(doc)
            updates["variants"] = variants
            updates["total_stock"] = sum(v["stock"] for v in variants)
            updates["discount_percentage"] = doc.get("discount_percentage", 0.0)
            unset["stock"] = ""
            unset["sizes"] = ""
            unset["colors"] = ""
            migrated_flat += 1

        if "is_deleted" in doc:
            if doc.get("is_deleted") and doc.get("is_active", True):
                updates["is_active"] = False
            unset["is_deleted"] = ""
            cleaned_is_deleted += 1

        if updates or unset:
            op: dict = {}
            if updates:
                op["$set"] = updates
            if unset:
                op["$unset"] = unset
            await products_col.update_one({"_id": doc["_id"]}, op)

    print(f"Migrated {migrated_flat} flat-schema product(s) to variants[].")
    print(f"Cleaned is_deleted off {cleaned_is_deleted} product(s).")


if __name__ == "__main__":
    asyncio.run(migrate())
