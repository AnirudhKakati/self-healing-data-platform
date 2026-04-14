from fastapi import APIRouter, Depends, status, HTTPException, Query 
from sqlalchemy.ext.asyncio import AsyncSession
from shared.db import get_db
from control_plane.app.services.tenants import create_tenant_service, get_tenant_service, get_all_tenants_service, delete_tenant_service, update_tenant_service
from control_plane.app.schemas.tenants import TenantCreate, TenantUpdate, TenantResponse
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from typing import List

router=APIRouter()

#CREATE TENANT
@router.post("/", response_model=TenantResponse, status_code=status.HTTP_201_CREATED)
async def create_tenant(tenant_data: TenantCreate, session: AsyncSession = Depends(get_db)):

    try:
        tenant=await create_tenant_service(tenant_data, session)
        return tenant
    
    except IntegrityError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,detail="Tenant could not be created because of a database constraint violation.")
    except SQLAlchemyError:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,detail="Database error while creating tenant.")

#GET TENANT BY ID
@router.get("/{tenant_id}", response_model=TenantResponse)
async def get_tenant(tenant_id: int, session: AsyncSession=Depends(get_db)):

    tenant_data=await get_tenant_service(tenant_id,session)
    if not tenant_data:
        raise HTTPException(status_code=404,detail="Tenant not found. Please check the tenant_id")

    return tenant_data

#GET ALL TENANTS. OPTIONAL LIMIT AND OFFSET
@router.get("/",response_model=List[TenantResponse])
async def get_all_tenants(session: AsyncSession=Depends(get_db), limit: int | None=Query(default=None,ge=1), offset: int=Query(default=0, ge=0)): #We user Query() to set constraints and for swagger docs. 
    #Limit must be greater than equal to 1 and offset greater than equal to 0 
    try:
        tenants=await get_all_tenants_service(session, limit, offset)
        return tenants
    except SQLAlchemyError:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Database error while fetching tenants.")

#DELETE TENANT BY ID
@router.delete("/{tenant_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tenant(tenant_id: int, session: AsyncSession=Depends(get_db)):
    try:
        deleted_rows= await delete_tenant_service(tenant_id,session)

    except SQLAlchemyError:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Database error while deleting tenant")

    if deleted_rows==0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found. Please check the tenant_id")
    return

#UPDATE TENANT BY ID
@router.put("/{tenant_id}", response_model=TenantResponse, status_code=status.HTTP_200_OK)
async def update_tenant(tenant_id: int, tenant_data: TenantUpdate, session: AsyncSession=Depends(get_db)):
    try:
        tenant=await update_tenant_service(tenant_id,tenant_data,session)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,detail=str(e))
    except IntegrityError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,detail="Tenant could not be updated because of a database constraint violation.")
    except SQLAlchemyError:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,detail="Database error while updating tenant.")
    
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found. Please check the tenant_id")
    
    return tenant