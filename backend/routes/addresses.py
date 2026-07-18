from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from middleware.auth_middleware import get_current_user
from schemas.address import AddressCreate, AddressResponse, AddressUpdate
from services.address import AddressService
from utils.ids import is_valid_id
from utils.limiter import limiter

router = APIRouter()


@router.get("", response_model=list[AddressResponse])
@limiter.limit("30/minute")
async def list_addresses(request: Request, user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await AddressService.list_addresses(db, str(user["_id"]))


@router.post("", response_model=AddressResponse)
@limiter.limit("20/minute")
async def create_address(request: Request, body: AddressCreate, user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await AddressService.create_address(db, str(user["_id"]), body.model_dump())


@router.put("/{address_id}", response_model=AddressResponse)
@limiter.limit("20/minute")
async def update_address(request: Request, address_id: str, body: AddressUpdate, user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if not is_valid_id(address_id):
        raise HTTPException(status_code=400, detail="Invalid address ID")
    return await AddressService.update_address(db, str(user["_id"]), address_id, body.model_dump())


@router.delete("/{address_id}")
@limiter.limit("20/minute")
async def delete_address(request: Request, address_id: str, user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if not is_valid_id(address_id):
        raise HTTPException(status_code=400, detail="Invalid address ID")
    await AddressService.delete_address(db, str(user["_id"]), address_id)
    return {"message": "Address deleted"}


@router.post("/{address_id}/default", response_model=AddressResponse)
@limiter.limit("20/minute")
async def set_default_address(request: Request, address_id: str, user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if not is_valid_id(address_id):
        raise HTTPException(status_code=400, detail="Invalid address ID")
    return await AddressService.set_default(db, str(user["_id"]), address_id)
