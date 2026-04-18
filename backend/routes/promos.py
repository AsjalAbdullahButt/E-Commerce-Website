from fastapi import APIRouter, HTTPException, Depends, Request
from database import promos_col
from models.promo import PromoCreate, PromoValidate
from middleware.auth_middleware import get_current_user, require_admin
from utils.limiter import limiter
from datetime import datetime
from bson import ObjectId

router = APIRouter()

@router.post("/validate")
@limiter.limit("10/minute")
async def validate_promo(request: Request, body: PromoValidate, _=Depends(get_current_user)):
    promo = await promos_col.find_one({"code": body.code.upper(), "is_active": True})
    if not promo:
        raise HTTPException(status_code=404, detail="Invalid or expired promo code")
    if promo.get("expires_at") and promo["expires_at"] < datetime.utcnow().isoformat():
        raise HTTPException(status_code=400, detail="Promo code has expired")
    if promo.get("max_uses") and promo.get("uses", 0) >= promo["max_uses"]:
        raise HTTPException(status_code=400, detail="Promo code usage limit reached")
    if body.order_total < promo.get("min_order", 0):
        raise HTTPException(status_code=400, detail=f"Minimum order of Rs {promo.get('min_order', 0)} required")

    discount = (body.order_total * promo["discount_value"] / 100
                if promo["discount_type"] == "percentage"
                else float(promo["discount_value"]))
    return {
        "valid":           True,
        "discount_type":   promo["discount_type"],
        "discount_value":  promo["discount_value"],
        "discount_amount": round(discount, 2),
        "code":            promo["code"],
    }

@router.post("")
@limiter.limit("20/minute")
async def create_promo(request: Request, body: PromoCreate, _=Depends(require_admin)):
    existing = await promos_col.find_one({"code": body.code.upper()})
    if existing:
        raise HTTPException(status_code=400, detail="Promo code already exists")
    doc = {**body.dict(), "code": body.code.upper(), "uses": 0, "is_active": True, "created_at": datetime.utcnow().isoformat()}
    await promos_col.insert_one(doc)
    return {"message": "Promo created"}

@router.get("")
@limiter.limit("30/minute")
async def list_promos(request: Request, _=Depends(require_admin)):
    promos = await promos_col.find({}).to_list(length=100)
    for p in promos:
        p["id"] = str(p.pop("_id"))
    return promos

@router.delete("/{promo_id}")
@limiter.limit("20/minute")
async def delete_promo(request: Request, promo_id: str, _=Depends(require_admin)):
    try:
        oid = ObjectId(promo_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid promo ID")
    await promos_col.delete_one({"_id": oid})
    return {"message": "Promo deleted"}
