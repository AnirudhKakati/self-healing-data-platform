from control_plane.app.models.tenants import Tenant
from control_plane.app.models.api_keys import APIKey
from control_plane.app.schemas.api_keys import APIKeyCreate
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import defer
from sqlalchemy import select
from shared.config import API_KEY_SECRET
from shared.utils import hash_api_key, generate_secure_key
from datetime import datetime


async def create_api_key_service(tenant_id: int, key_data: APIKeyCreate, session: AsyncSession):
    #we verify if the tenant exists or not
    tenant=await session.get(Tenant,tenant_id)
    if not tenant: 
        return None, None #route will handle 404 tenant not found
    
    api_key_dict=key_data.model_dump() #converts the pydantic object to a plain dictionary
    api_key_dict["tenant_id"]=tenant_id

    #create the actual API key
    raw_api_key=generate_secure_key()

    api_key_dict["key_prefix"]=raw_api_key[:16]
    key_hash=hash_api_key(raw_api_key, API_KEY_SECRET)
    api_key_dict["key_hash"]=key_hash
    api_key=APIKey(**api_key_dict)

    try:
        session.add(api_key)
        await session.commit()
        await session.refresh(api_key)
        
        return api_key, raw_api_key
    
    except SQLAlchemyError:
        await session.rollback() 
        raise
    
async def get_api_key_service(tenant_id: int, key_id: int, session: AsyncSession):
    #we check both the key id as well as the tenant id to ensure only the correct tenant can get the key
    result=await session.execute(select(APIKey).where(APIKey.id==key_id,APIKey.tenant_id==tenant_id).options(defer(APIKey.key_hash)))
    #using 'defer' here ensures the APIKey.key_hash is not called from the database (unless it is explicitly accessed later by doing key_data.key_hash. In that case SQLAlchemy will trigger a second query to fetch it)
    #we could've fetched the whole APIKey object from database and let the pydantic schema take care of excluding the key_hash field. But this prevents the field from being fetched from the DB.
    key_data=result.scalar_one_or_none()

    return key_data

async def get_all_api_keys_service(tenant_id: int, session:AsyncSession, limit: int | None=None, offset: int=0): 

    tenant=await session.get(Tenant, tenant_id) #first we check if this tenant exists
    if not tenant:
        return None  #route will handle 404 tenant not found
    
    statement=select(APIKey).where(APIKey.tenant_id==tenant_id).order_by(APIKey.id).options(defer(APIKey.key_hash)).offset(offset)
    if limit is not None:
        statement=statement.limit(limit)

    result=await session.execute(statement)
    api_keys=result.scalars().all()
    return api_keys
        
async def revoke_api_key_service(tenant_id: int, key_id: int, session: AsyncSession):
    
    result=await session.execute(select(APIKey).where(APIKey.id==key_id, APIKey.tenant_id==tenant_id).options(defer(APIKey.key_hash)))
    api_key=result.scalar_one_or_none()
    if not api_key:
        return None #route will handle 404
    
    if api_key.revoked_at is not None:
        return api_key #idempotent when the API key is already revoked

    api_key.revoked_at=datetime.now().replace(tzinfo=None)

    try:
        await session.commit()
        #we dont need a refresh here because the only change is setting revoked_at
        return api_key
    except SQLAlchemyError:
        await session.rollback()
        raise