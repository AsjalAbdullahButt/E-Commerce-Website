from datetime import datetime

from sqlalchemy.dialects.mysql import CHAR as MySQLCHAR
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from utils.ids import new_id

# Hex digits are always ASCII — using ascii/ascii_bin instead of the table default (utf8mb4) on
# every ID column saves up to 3 bytes/char and avoids unnecessary collation work on every PK/FK
# comparison and index lookup.
ID_TYPE = MySQLCHAR(24, charset="ascii", collation="ascii_bin")


class Base(DeclarativeBase):
    pass


class IDMixin:
    id: Mapped[str] = mapped_column(ID_TYPE, primary_key=True, default=new_id)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
