"""
One-time migration: convert every remaining ISO-string timestamp field to a native BSON
date, so `created_at`/`updated_at`/`added_at`/`timestamp` are the same type everywhere.
See NOTES_schema_audit.md (timestamp consistency section) for the full writer-by-writer
inventory this closes out.

Why this matters, concretely: `audit_logs_col` is sorted by `timestamp` (services/admin_auth.py
`get_logs`) and `products_col`/`orders_col`/`reviews_col`/etc. are sorted by `created_at` in
several list endpoints. MongoDB's BSON type order ranks Date above String, so a collection with
both types for the same field sorts by type first, not chronologically — e.g. every admin-panel
audit-log entry (already native datetime) would sort before every entry written by the old
`log_to_db` (ISO string), regardless of actual time. Application code now writes
`datetime.utcnow()` everywhere (see utils/logger.py, routes/auth.py, routes/rider.py,
routes/reviews.py, routes/wishlist.py, routes/admin.py, seed/seed_db.py); this script fixes up
any documents that were written before that change.

Safe to re-run (idempotent) — only touches fields that are still strings.

Run: python -m scripts.migrate_timestamps_to_datetime   (from backend/, with .env configured)
"""
import asyncio
import sys
from datetime import datetime
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from database import (
    users_col, products_col, orders_col, reviews_col, wishlist_col, promos_col,
    admin_users_col, riders_col, audit_logs_col,
)

# (collection, [top-level timestamp fields to convert])
TARGETS = [
    (users_col, ["created_at", "updated_at", "reset_token_expires"]),
    (products_col, ["created_at", "updated_at"]),
    (orders_col, ["created_at", "updated_at"]),
    (reviews_col, ["created_at"]),
    (wishlist_col, ["added_at"]),
    (promos_col, ["created_at"]),
    (admin_users_col, ["created_at", "updated_at"]),
    (riders_col, ["created_at", "updated_at"]),
    (audit_logs_col, ["timestamp"]),
]

# orders also carry a status_history[] array of {status, timestamp, note} — convert those too.
ARRAY_TARGETS = [
    (orders_col, "status_history", "timestamp"),
]


def parse(value):
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


async def migrate_top_level(col, fields) -> int:
    n = 0
    query = {"$or": [{f: {"$type": "string"}} for f in fields]}
    async for doc in col.find(query):
        updates = {}
        for f in fields:
            parsed = parse(doc.get(f))
            if parsed is not None:
                updates[f] = parsed
        if updates:
            await col.update_one({"_id": doc["_id"]}, {"$set": updates})
            n += 1
    return n


async def migrate_array_field(col, array_field, ts_field) -> int:
    n = 0
    async for doc in col.find({f"{array_field}.{ts_field}": {"$type": "string"}}):
        entries = doc.get(array_field) or []
        changed = False
        for entry in entries:
            parsed = parse(entry.get(ts_field))
            if parsed is not None:
                entry[ts_field] = parsed
                changed = True
        if changed:
            await col.update_one({"_id": doc["_id"]}, {"$set": {array_field: entries}})
            n += 1
    return n


async def migrate() -> None:
    total = 0
    for col, fields in TARGETS:
        count = await migrate_top_level(col, fields)
        if count:
            print(f"  {col.name}: converted {count} document(s) — {fields}")
        total += count

    for col, array_field, ts_field in ARRAY_TARGETS:
        count = await migrate_array_field(col, array_field, ts_field)
        if count:
            print(f"  {col.name}: converted {count} document(s) — {array_field}[].{ts_field}")
        total += count

    print(f"\nDone. {total} document(s) updated." if total else "\nNothing to migrate — already consistent.")


if __name__ == "__main__":
    asyncio.run(migrate())
