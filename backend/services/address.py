from fastapi import HTTPException
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from db.address import Address


class AddressService:
    """Saved shipping addresses — at most one `is_default` per user, enforced here (not a DB
    constraint) by unsetting any previous default in the same transaction whenever a new one is
    flagged. The very first address a customer saves always becomes the default regardless of
    what they pass, so there's never a zero-default state to handle downstream."""

    @staticmethod
    async def list_addresses(db: AsyncSession, user_id: str) -> list[Address]:
        result = await db.execute(
            select(Address).where(Address.user_id == user_id).order_by(Address.is_default.desc(), Address.created_at.desc())
        )
        return result.scalars().all()

    @staticmethod
    async def _unset_other_defaults(db: AsyncSession, user_id: str, except_id: str = None) -> None:
        stmt = update(Address).where(Address.user_id == user_id, Address.is_default == True)  # noqa: E712
        if except_id:
            stmt = stmt.where(Address.id != except_id)
        await db.execute(stmt.values(is_default=False))

    @staticmethod
    async def create_address(db: AsyncSession, user_id: str, data: dict) -> Address:
        existing_count = (await db.execute(select(Address).where(Address.user_id == user_id))).scalars().all()
        make_default = data.get("is_default", False) or len(existing_count) == 0

        address = Address(user_id=user_id, **{**data, "is_default": make_default})
        db.add(address)
        await db.flush()

        if make_default:
            await AddressService._unset_other_defaults(db, user_id, except_id=address.id)
        return address

    @staticmethod
    async def update_address(db: AsyncSession, user_id: str, address_id: str, data: dict) -> Address:
        address = await db.get(Address, address_id)
        if not address or address.user_id != user_id:
            raise HTTPException(status_code=404, detail="Address not found")

        was_default = address.is_default
        for field, value in data.items():
            setattr(address, field, value)

        if address.is_default:
            await AddressService._unset_other_defaults(db, user_id, except_id=address_id)
        elif was_default:
            # This address was the default and the update just unset it — never leave a customer
            # with saved addresses but no default. Promote another if one exists, otherwise this
            # is their only address, so it stays the default regardless of what was submitted.
            next_default = (await db.execute(
                select(Address).where(Address.user_id == user_id, Address.id != address_id)
                .order_by(Address.created_at.desc())
            )).scalars().first()
            if next_default:
                next_default.is_default = True
            else:
                address.is_default = True
        return address

    @staticmethod
    async def delete_address(db: AsyncSession, user_id: str, address_id: str) -> None:
        address = await db.get(Address, address_id)
        if not address or address.user_id != user_id:
            raise HTTPException(status_code=404, detail="Address not found")

        was_default = address.is_default
        await db.delete(address)
        await db.flush()

        if was_default:
            # Promote the most recently added remaining address to default, if any — never leave
            # a customer with saved addresses but no default.
            next_default = (await db.execute(
                select(Address).where(Address.user_id == user_id).order_by(Address.created_at.desc())
            )).scalars().first()
            if next_default:
                next_default.is_default = True

    @staticmethod
    async def set_default(db: AsyncSession, user_id: str, address_id: str) -> Address:
        address = await db.get(Address, address_id)
        if not address or address.user_id != user_id:
            raise HTTPException(status_code=404, detail="Address not found")

        address.is_default = True
        await AddressService._unset_other_defaults(db, user_id, except_id=address_id)
        return address
