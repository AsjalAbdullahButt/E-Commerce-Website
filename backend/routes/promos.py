from datetime import datetime

from fastapi import APIRouter, HTTPException, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from db.promo import Promo
from models.promo import PromoCreate, PromoValidate
from middleware.auth_middleware import get_current_user, require_admin
from utils.limiter import limiter
from utils.logger import get_logger, log_to_db
from utils.ids import is_valid_id

logger = get_logger(__name__)

router = APIRouter()

@router.post("/validate")
@limiter.limit("10/minute")
async def validate_promo(request: Request, body: PromoValidate, _=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Promo).where(Promo.code == body.code.upper(), Promo.is_active == True))  # noqa: E712
    promo = result.scalar_one_or_none()
    if not promo:
        raise HTTPException(status_code=404, detail="Invalid or expired promo code")
    if promo.expires_at and promo.expires_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Promo code has expired")
    if promo.max_uses and promo.uses >= promo.max_uses:
        raise HTTPException(status_code=400, detail="Promo code usage limit reached")
    if body.order_total < promo.min_order:
        raise HTTPException(status_code=400, detail=f"Minimum order of Rs {promo.min_order} required")

    discount = (body.order_total * promo.discount_value / 100
                if promo.discount_type == "percentage"
                else float(promo.discount_value))
    return {
        "valid":           True,
        "discount_type":   promo.discount_type,
        "discount_value":  promo.discount_value,
        "discount_amount": round(discount, 2),
        "code":            promo.code,
    }

@router.post("")
@limiter.limit("20/minute")
async def create_promo(request: Request, body: PromoCreate, _=Depends(require_admin), db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(Promo).where(Promo.code == body.code.upper()))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Promo code already exists")
    promo = Promo(
        code=body.code.upper(), discount_type=body.discount_type, discount_value=body.discount_value,
        min_order=body.min_order, max_uses=body.max_uses, uses=0, expires_at=body.expires_at,
        is_active=True,
    )
    db.add(promo)
    return {"message": "Promo created"}

@router.get("")
@limiter.limit("30/minute")
async def list_promos(request: Request, _=Depends(require_admin), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Promo))
    promos = result.scalars().all()
    return [
        {c.name: getattr(p, c.name) for c in Promo.__table__.columns}
        for p in promos
    ]

@router.delete("/{promo_id}")
@limiter.limit("20/minute")
async def delete_promo(request: Request, promo_id: str, _=Depends(require_admin), db: AsyncSession = Depends(get_db)):
    if not is_valid_id(promo_id):
        await log_to_db("INVALID_PROMO_ID", __name__, f"admin tried invalid promo ID {promo_id}", {})
        raise HTTPException(status_code=400, detail="Invalid promo ID")
    promo = await db.get(Promo, promo_id)
    if promo:
        await db.delete(promo)
    return {"message": "Promo deleted"}
