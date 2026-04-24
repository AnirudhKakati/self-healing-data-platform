from fastapi import APIRouter, Depends, status, HTTPException, Query 
from sqlalchemy.ext.asyncio import AsyncSession
from shared.db import get_db
from control_plane.app.services.webhook_callbacks import get_webhook_callback_service, get_all_webhook_callbacks_service, get_all_webhook_callbacks_for_pipeline_service, get_all_webhook_callbacks_for_tenant_service
from control_plane.app.schemas.webhook_callbacks import WebhookCallbackResponse
from sqlalchemy.exc import SQLAlchemyError
from typing import List

run_callbacks_router=APIRouter()
pipeline_callbacks_router=APIRouter()
tenant_callbacks_router=APIRouter()

#GET WEBHOOK CALLBACK BY ID
@run_callbacks_router.get("/{callback_id}", response_model=WebhookCallbackResponse)
async def get_webhook_callback(tenant_id: int, pipeline_id: int, run_id: int, callback_id: int, session: AsyncSession=Depends(get_db)):

    callback_data=await get_webhook_callback_service(tenant_id,pipeline_id,run_id,callback_id,session)
    if not callback_data:
        raise HTTPException(status_code=404,detail="Callback not found. Please check the callback_id")

    return callback_data

# GET ALL WEBHOOK CALLBACKS FOR A PIPELINE RUN
@run_callbacks_router.get("/", response_model=List[WebhookCallbackResponse])
async def get_all_webhook_callbacks(tenant_id: int, pipeline_id: int, run_id: int, session: AsyncSession=Depends(get_db), limit: int | None=Query(default=None,ge=1), offset: int=Query(default=0, ge=0)): #We user Query() to set constraints and for swagger docs. 
    #Limit must be greater than equal to 1 and offset greater than equal to 0 
    try:
        webhook_callbacks=await get_all_webhook_callbacks_service(tenant_id, pipeline_id, run_id, session, limit, offset)
    except SQLAlchemyError:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Database error while fetching webhook callbacks")
    
    if webhook_callbacks is None: #needs 'is None' instead of 'not webhook_callbacks' because None indicates pipeline_run was not found (atleast not for this pipeline, tenant or the tenant or pipeline doesn't exist), 
        # and an empty webhook_callbacks list indicates 0 returned webhook callbacks
        raise HTTPException(status_code=404,detail="Pipeline run not found. Please check the run_id")
    
    return webhook_callbacks

# GET ALL WEBHOOK CALLBACKS FOR A PIPELINE
@pipeline_callbacks_router.get("/", response_model=List[WebhookCallbackResponse])
async def get_all_webhook_callbacks_for_pipeline(tenant_id: int, pipeline_id: int, session: AsyncSession=Depends(get_db), limit: int | None=Query(default=None,ge=1), offset: int=Query(default=0, ge=0)): #We user Query() to set constraints and for swagger docs. 
    #Limit must be greater than equal to 1 and offset greater than equal to 0 
    try:
        webhook_callbacks=await get_all_webhook_callbacks_for_pipeline_service(tenant_id, pipeline_id, session, limit, offset)
    except SQLAlchemyError:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Database error while fetching webhook callbacks")
    
    if webhook_callbacks is None: #needs 'is None' instead of 'not webhook_callbacks' because None indicates pipeline was not found (atleast not for this tenant, or the tenant doesn't exist),  
        # and an empty webhook_callbacks list indicates 0 returned webhook callbacks
        raise HTTPException(status_code=404,detail="Pipeline not found. Please check the pipeline_id")
    
    return webhook_callbacks

# GET ALL WEBHOOK CALLBACKS FOR A TENANT
@tenant_callbacks_router.get("/", response_model=List[WebhookCallbackResponse])
async def get_all_webhook_callbacks_for_tenant(tenant_id: int, session: AsyncSession=Depends(get_db), limit: int | None=Query(default=None,ge=1), offset: int=Query(default=0, ge=0)): #We user Query() to set constraints and for swagger docs. 
    #Limit must be greater than equal to 1 and offset greater than equal to 0 
    try:
        webhook_callbacks=await get_all_webhook_callbacks_for_tenant_service(tenant_id, session, limit, offset)
    except SQLAlchemyError:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Database error while fetching webhook callbacks")
    
    if webhook_callbacks is None: #needs 'is None' instead of 'not webhook_callbacks' because None indicates tenant was not found, 
        # and an empty webhook_callbacks list indicates 0 returned webhook callbacks
        raise HTTPException(status_code=404,detail="Tenant not found. Please check the tenant_id")
    
    return webhook_callbacks