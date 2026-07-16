from datetime import datetime
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.promo import Promo
from utils.logger import get_logger

logger = get_logger(__name__)


def _serialize(promo: Promo) -> dict:
    return {c.name: getattr(promo, c.name) for c in Promo.__table__.columns}


class DiscountService:
    """Discount and coupon management service backed by the `promos` table."""

    @staticmethod
    async def create_discount(
        db: AsyncSession,
        code: str,
        description: str,
        discount_type: str,
        discount_value: float,
        max_usage: int,
        min_order_value: float,
        expiry_date: datetime,
        admin_id: str,
    ) -> str:
        """Create new discount/coupon"""
        existing = await db.execute(select(Promo).where(Promo.code == code.upper()))
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Discount code already exists"
            )

        discount_type_value = getattr(discount_type, "value", discount_type)

        promo = Promo(
            code=code.upper(),
            description=description,
            discount_type=discount_type_value,
            discount_value=discount_value,
            max_uses=max_usage,
            uses=0,
            min_order=min_order_value,
            expires_at=expiry_date,
            created_by=admin_id,
            is_active=True,
        )
        db.add(promo)
        await db.flush()

        # Log audit
        from services.admin_auth import AdminAuditService
        await AdminAuditService.log_action(
            admin_id=admin_id,
            admin_name="System",
            action="create_discount",
            entity_type="discount",
            entity_id=promo.id,
            changes={"code": {"old": None, "new": code}},
            ip_address="0.0.0.0"
        )

        logger.info(f"Discount created: {code} by admin {admin_id}")
        return promo.id

    @staticmethod
    async def get_discount(db: AsyncSession, discount_id: str) -> dict:
        """Get discount by ID"""
        promo = await db.get(Promo, discount_id)

        if not promo:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Discount not found"
            )

        return _serialize(promo)

    @staticmethod
    async def update_discount(
        db: AsyncSession,
        discount_id: str,
        updates: dict,
        admin_id: str,
    ) -> dict:
        """Update discount"""
        current = await DiscountService.get_discount(db, discount_id)
        promo = await db.get(Promo, discount_id)

        for key, value in updates.items():
            setattr(promo, key, value)
        promo.updated_at = datetime.utcnow()

        # Log audit
        from services.admin_auth import AdminAuditService
        await AdminAuditService.log_action(
            admin_id=admin_id,
            admin_name="System",
            action="update_discount",
            entity_type="discount",
            entity_id=discount_id,
            changes={k: {"old": current.get(k), "new": v} for k, v in updates.items()},
            ip_address="0.0.0.0"
        )

        logger.info(f"Discount updated: {discount_id}")
        return await DiscountService.get_discount(db, discount_id)

    @staticmethod
    async def list_discounts(
        db: AsyncSession,
        is_active: Optional[bool] = None,
        limit: int = 50,
        skip: int = 0,
    ) -> tuple:
        """List discounts"""
        query = select(Promo)
        count_query = select(func.count()).select_from(Promo)

        if is_active is not None:
            query = query.where(Promo.is_active == is_active)
            count_query = count_query.where(Promo.is_active == is_active)

        query = query.order_by(Promo.created_at.desc()).offset(skip).limit(limit)

        result = await db.execute(query)
        discounts = [_serialize(p) for p in result.scalars().all()]

        total = (await db.execute(count_query)).scalar_one()
        return discounts, total
