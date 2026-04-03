from control_plane.app.models.tenants import Tenant
from control_plane.app.schemas.tenants import TenantCreate, TenantUpdate
from sqlalchemy.ext.asyncio import AsyncSession


async def create_tenant(session: AsyncSession, tenant_data: TenantCreate):
    tenant_dict=tenant_data.model_dump() #converts the pydantic object to a plain dictionary
    tenant=Tenant(**tenant_dict) #SQLAlchemy constructors expect keyword arguments, so we need to unpack the dictionary with **

    try:
        session.add(tenant) #this makes SQL track and prepare the object to insert it into the database
        await session.commit() #this ensures the current transaction is finalized and changes are persited to the database. SQLAlchemy will issue the actual SQL insert.
        await session.refresh(tenant) #because the DB generates certain fields, we wait for it to send the latest state to be reflected in the tenant object.

        return tenant #we return this full object so we can send it in the Response later
    except Exception:
        await session.rollback() #incase of any error, we roll back the session and raise the error
        raise

async def update_tenant(session: AsyncSession, tenant_data: TenantUpdate):
    pass

