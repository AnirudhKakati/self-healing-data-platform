from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from shared.db import get_db
from control_plane.app.services.tenants import create_tenant as create_tenant_service
from control_plane.app.schemas.tenants import TenantCreate, TenantUpdate, TenantResponse

router=APIRouter()

@router.post("/", response_model=TenantResponse, status_code=status.HTTP_201_CREATED)
async def create_tenant(tenant_data: TenantCreate, session: AsyncSession = Depends(get_db)):
    
    tenant=await create_tenant_service(session,tenant_data)
    return tenant