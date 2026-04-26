from fastapi import APIRouter, Depends, status, HTTPException, Query 
from sqlalchemy.ext.asyncio import AsyncSession
from shared.db import get_db
from control_plane.app.services.api_keys import create_api_key_service,get_api_key_service, get_all_api_keys_service, revoke_api_key_service
from control_plane.app.schemas.api_keys import APIKeyCreate, APIKeyCreatedResponse, APIKeyResponse
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from typing import List

router=APIRouter()

#CREATE API KEY
@router.post("/", response_model=APIKeyCreatedResponse, status_code=status.HTTP_201_CREATED)
async def create_api_key(tenant_id: int, key_data: APIKeyCreate, session: AsyncSession = Depends(get_db)):
    try:
        api_key, raw_api_key=await create_api_key_service(tenant_id, key_data, session)
    except IntegrityError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,detail="API key could not be created because of a database constraint violation.")
    except SQLAlchemyError:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,detail="Database error while creating API Key.")
    
    if api_key is None:
        raise HTTPException(status_code=404,detail="Tenant not found. Please check the tenant_id")

    base_response=APIKeyResponse.model_validate(api_key)
    created_api_key=APIKeyCreatedResponse(**base_response.model_dump(),api_key=raw_api_key)
    return created_api_key

#GET API KEY BY ID
@router.get("/{key_id}", response_model=APIKeyResponse)
async def get_api_key(tenant_id: int, key_id: int, session: AsyncSession=Depends(get_db)):

    key_data=await get_api_key_service(tenant_id,key_id,session)
    if not key_data:
        raise HTTPException(status_code=404,detail="API key not found. Please check the key_id")

    return key_data

#GET ALL API KEYS FOR A TENANT
@router.get("/",response_model=List[APIKeyResponse])
async def get_all_api_keys(tenant_id: int, session: AsyncSession=Depends(get_db), limit: int | None=Query(default=None,ge=1), offset: int=Query(default=0, ge=0)): #We user Query() to set constraints and for swagger docs. 
    #Limit must be greater than equal to 1 and offset greater than equal to 0 
    try:
        api_keys=await get_all_api_keys_service(tenant_id, session, limit, offset)
    except SQLAlchemyError:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Database error while fetching api keys.")
    
    if api_keys is None: #needs 'is None' instead of 'not api_keys' because None indicates tenant not found, and an empty api_keys list indicates 0 returned api keys
        raise HTTPException(status_code=404,detail="Tenant not found. Please check the tenant_id")
    
    return api_keys

#REVOKE API KEY
@router.post("/{key_id}/revoke", response_model=APIKeyResponse, status_code=status.HTTP_200_OK)
async def revoke_api_key(tenant_id: int, key_id: int, session: AsyncSession=Depends(get_db)):
    try:
        revoked_api_key=await revoke_api_key_service(tenant_id,key_id,session)

    except SQLAlchemyError:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Database error while revoking API Key")
    
    if not revoked_api_key:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found. Please check the key_id")
    return revoked_api_key
