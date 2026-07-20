"""Timezone-aware datetime storage on top of MySQL, which has no real tz-aware column type.

MySQL's DATETIME (what every column in this schema uses) always stores and returns naive wall-
clock values — passing SQLAlchemy's `DateTime(timezone=True)` flag changes nothing about the
actual DDL or wire format on this dialect, unlike PostgreSQL's genuinely tz-aware TIMESTAMPTZ.
So there is no migration that could make the columns "more timezone-aware" at the database
level; what actually matters is that every value crossing the Python <-> MySQL boundary is
unambiguously UTC, both ways. UTCDateTime is a TypeDecorator that enforces exactly that:

  - On the way into the database (process_bind_param): a naive datetime is assumed to already be
    UTC (this codebase's long-standing convention); an aware one is converted to UTC first. The
    tzinfo is then stripped, since that's the only shape MySQL's driver accepts.
  - On the way out (process_result_value): the naive value MySQL hands back is re-stamped with
    UTC tzinfo, so application code never has to remember which timestamps are "trustworthy UTC"
    versus "naive and ambiguous" -- they're all tz-aware once loaded, and can be safely compared
    against `datetime.now(timezone.utc)` without raising.
"""
from datetime import datetime, timezone

from sqlalchemy import DateTime
from sqlalchemy.types import TypeDecorator


class UTCDateTime(TypeDecorator):
    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if value.tzinfo is not None:
            value = value.astimezone(timezone.utc)
        return value.replace(tzinfo=None)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return value.replace(tzinfo=timezone.utc)
