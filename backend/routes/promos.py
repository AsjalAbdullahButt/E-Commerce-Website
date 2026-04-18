from fastapi import APIRouter, HTTPException, Depends
from database import promos_col
from models.promo import PromoCreate, PromoValidate
from middleware.auth_middleware import get_current_user, require_admin
from datetime import datetime
from bson import ObjectId

router = APIRouter()

@router.post("/validate")
async def validate_promo(body: PromoValidate, _=Depends(get_current_user)):
    """Validate promo code for order"""
    promo = await promos_col.find_one({
        "code": body.code.upper(),
        "is_active": True
    })
    
    if not promo:
        raise HTTPException(status_code=404, detail="Invalid or expired promo code")
    
    # Check expiry
    if promo.get("expires_at") and promo["expires_at"] < datetime.utcnow().isoformat():
        raise HTTPException(status_code=400, detail="Promo code has expired")
    
    # Check usage limit
    if promo.get("max_uses") and promo.get("uses", 0) >= promo["max_uses"]:
        raise HTTPException(status_code=400, detail="Promo code usage limit reached")
    
    # Check minimum order
    if body.order_total < promo.get("min_order", 0):
        min_order = promo.get("min_order", 0)
        raise HTTPException(status_code=400, detail=f"Minimum order of Rs {min_order} required")
    
    # Calculate discount
    if promo["discount_type"] == "percentage":
        discount = body.order_total * (promo["discount_value"] / 100)
    else:
        discount = promo["discount_value"]
    
    return {
        "valid": True,
        "discount_type": promo["discount_type"],
        "discount_value": promo["discount_value"],
        "discount_amount": round(discount, 2),
        "code": promo["code"]
    }

@router.post("")
async def create_promo(body: PromoCreate, _=Depends(require_admin)):
    """Create promo code (admin only)"""
    existing = await promos_col.find_one({"code": body.code.upper()})
    if existing:
        raise HTTPException(status_code=400, detail="Promo code already exists")
    
    doc = {
        **body.dict(),
        "code": body.code.upper(),
        "uses": 0,
        "is_active": True,
        "created_at": datetime.utcnow().isoformat()
    }
    await promos_col.insert_one(doc)
    return {"message": "Promo created"}

@router.get("")
async def list_promos(_=Depends(require_admin)):
    """List all promos (admin only)"""
    promos = await promos_col.find({}).to_list(length=100)
    for p in promos:
        p["id"] = str(p.pop("_id"))
    return promos

@router.delete("/{promo_id}")
async def delete_promo(promo_id: str, _=Depends(require_admin)):
    """Delete promo code (admin only)"""
    try:
        oid = ObjectId(promo_id)
    except:
        raise HTTPException(status_code=400, detail="Invalid promo ID")
    
    await promos_col.delete_one({"_id": oid})
    return {"message": "Promo deleted"}
