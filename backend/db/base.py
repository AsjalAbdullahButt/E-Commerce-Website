from datetime import datetime, timezone

from sqlalchemy.dialects.mysql import CHAR as MySQLCHAR
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from utils.db_types import UTCDateTime
from utils.ids import new_id

# Hex digits are always ASCII — using ascii/ascii_bin instead of the table default (utf8mb4) on
# every ID column saves up to 3 bytes/char and avoids unnecessary collation work on every PK/FK
# comparison and index lookup.
ID_TYPE = MySQLCHAR(24, charset="ascii", collation="ascii_bin")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    # Every `Mapped[datetime]` / `Mapped[Optional[datetime]]` column across the schema goes
    # through UTCDateTime (utils/db_types.py) by default, so a plain annotation is enough to get
    # timezone-safe read/write behavior without repeating the type on every column. Columns that
    # pass an explicit type to mapped_column() (e.g. the pre-Phase-3 `DateTime` columns being
    # migrated one file at a time) override this map entry as usual.
    type_annotation_map = {
        datetime: UTCDateTime,
    }


class IDMixin:
    id: Mapped[str] = mapped_column(ID_TYPE, primary_key=True, default=new_id)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        default=_utcnow, onupdate=_utcnow, nullable=False
    )
