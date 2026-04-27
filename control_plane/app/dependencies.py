from shared.config import ADMIN_SECRET_KEY, API_KEY_SECRET
from shared.utils import hash_api_key
from shared.db import get_db
from fastapi import Header, HTTPException, status, Depends
import hmac
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from control_plane.app.models.tenants import Tenant
from control_plane.app.models.api_keys import APIKey

async def verify_admin(x_admin_secret: str=Header(...)): #(...) in Header function means it is required. FastAPI will return a 422 if header is missing
    is_valid=hmac.compare_digest(x_admin_secret,ADMIN_SECRET_KEY)
    if not is_valid:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,detail="Invalid admin secret")
    
async def verify_tenant(tenant_id: int, x_api_key: str=Header(...), session: AsyncSession=Depends(get_db)):
    api_key_hash=hash_api_key(x_api_key,API_KEY_SECRET)

    #the API key hash must exist, belong to the given tenant_id, and that tenant must be active
    #we join through Tenant to verify tenant is_active without a separate query
    result=await session.execute(select(APIKey,Tenant).join(Tenant,APIKey.tenant_id==Tenant.id).where(APIKey.key_hash==api_key_hash, APIKey.revoked_at.is_(None)))
    
    row=result.one_or_none()
    if not row:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,detail="Invalid or revoked API key")

    api_key,tenant=row

    if api_key.tenant_id!=tenant_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,detail="Forbidden resource")
    
    if not tenant.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,detail="Tenant is inactive")