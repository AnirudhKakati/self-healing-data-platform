from control_plane.app.models.tenants import Tenant
from control_plane.app.models.api_keys import APIKey
from control_plane.app.schemas.tenants import TenantCreate, TenantUpdate
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import delete, select
from shared.config import API_KEY_SECRET
from shared.utils import generate_secure_key, hash_api_key

async def create_tenant_service(tenant_data: TenantCreate, session: AsyncSession):
    tenant_dict=tenant_data.model_dump() #converts the pydantic object to a plain dictionary
    tenant=Tenant(**tenant_dict) #SQLAlchemy constructors expect keyword arguments, so we need to unpack the dictionary with **

    try:
        #first we try to create the tenant
        session.add(tenant) #this makes SQL track and prepare the object to insert it into the database
        await session.flush() #flush sends the Tenant to the DB to get an ID WITHOUT committing the transaction yet

         #whenever a tenant is created, we also create an API key for it. The name is defaulted to 'primary'
        api_key_dict={"name":"primary", "tenant_id": tenant.id}

        raw_api_key=generate_secure_key() #create the actual API key
        key_hash=hash_api_key(raw_api_key, API_KEY_SECRET) #create the key hash

        api_key_dict["key_prefix"]=raw_api_key[:16]
        api_key_dict["key_hash"]=key_hash
        api_key=APIKey(**api_key_dict)

        session.add(api_key)
        await session.commit() #commit the whole session only after both operations run successfully
        await session.refresh(tenant)
        return tenant, raw_api_key #we return the tenant object, as well as the raw api key
        
    except SQLAlchemyError:
        await session.rollback() #incase of any DB related errors, we roll back the session and raise the error
        raise

async def get_tenant_service(tenant_id: int, session: AsyncSession):
    tenant_data=await session.get(Tenant,tenant_id) #get is used for primary key look up. So the passed tenant_id is mapped to the primary key of the table which is id
    return tenant_data

async def get_all_tenants_service(session:AsyncSession, limit: int | None=None, offset: int=0): 
    statement=select(Tenant).order_by(Tenant.id).offset(offset) #we select all tenants with optional offset (0 by default). we also ensure they are sorted by id
    if limit is not None: #and an optional limit. None by default
        statement=statement.limit(limit)

    result=await session.execute(statement)
    tenants=result.scalars().all() #scalars() is used to get clean ORM objects. all() is used to give the results as a list
    return tenants

async def delete_tenant_service(tenant_id: int, session: AsyncSession):
    try:
        result=await session.execute(delete(Tenant).where(Tenant.id==tenant_id)) #try deleting this tenant id and then return the number of rows deleted (should be 1 if deleted, 0 if not deleted)
        await session.commit()
        return result.rowcount
    except SQLAlchemyError: #if any DB related errors, then rollback
        await session.rollback() 
        raise

async def update_tenant_service(tenant_id: int, tenant_data: TenantUpdate, session: AsyncSession):
    
    tenant=await session.get(Tenant,tenant_id) #first we get the Tenant object
    if not tenant:
        return None
    
    update_dict=tenant_data.model_dump(exclude_unset=True) #we get the dictionary of the updates. Exclude unset is set to True to avoid updating other fields
    if not update_dict:
        raise ValueError("No fields were provided for update.")
    
    try:
        for key,value in update_dict.items():
            setattr(tenant,key,value) #then set the individual attributes

        await session.commit()
        await session.refresh(tenant)

        return tenant
    
    except SQLAlchemyError: #if any DB error, we rollback
        await session.rollback()
        raise