from control_plane.app.models.tenants import Tenant
from control_plane.app.schemas.tenants import TenantCreate, TenantUpdate
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import delete, select

async def create_tenant_service(tenant_data: TenantCreate, session: AsyncSession):
    tenant_dict=tenant_data.model_dump() #converts the pydantic object to a plain dictionary
    tenant=Tenant(**tenant_dict) #SQLAlchemy constructors expect keyword arguments, so we need to unpack the dictionary with **

    try:
        session.add(tenant) #this makes SQL track and prepare the object to insert it into the database
        await session.commit() #this ensures the current transaction is finalized and changes are persited to the database. SQLAlchemy will issue the actual SQL insert.
        await session.refresh(tenant) #because the DB generates certain fields, we wait for it to send the latest state to be reflected in the tenant object.

        return tenant #we return this full object so we can send it in the Response later
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

