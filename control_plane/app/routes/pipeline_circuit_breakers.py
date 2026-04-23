from fastapi import APIRouter, Depends, status, HTTPException, Query 
from sqlalchemy.ext.asyncio import AsyncSession
from shared.db import get_db
from control_plane.app.services.pipeline_circuit_breakers import get_pipeline_circuit_breaker_service, get_all_pipeline_circuit_breakers_for_tenant_service, update_pipeline_circuit_breaker_service
from control_plane.app.schemas.pipeline_circuit_breakers import PipelineCircuitBreakerResponse, PipelineCircuitBreakerUpdate
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from typing import List

pipeline_circuit_breakers_router=APIRouter()
tenant_circuit_breakers_router=APIRouter()

#GET PIPELINE CIRCUIT BREAKER
@pipeline_circuit_breakers_router.get("/", response_model=PipelineCircuitBreakerResponse)
async def get_pipeline_circuit_breaker(tenant_id: int, pipeline_id: int, session: AsyncSession=Depends(get_db)):

    breaker_data=await get_pipeline_circuit_breaker_service(tenant_id,pipeline_id,session)
    if not breaker_data:
        raise HTTPException(status_code=404,detail="Pipeline circuit breaker not found. Please check the pipeline_id")

    return breaker_data

#GET ALL PIPELINE CIRCUIT BREAKER FOR A TENANT
@tenant_circuit_breakers_router.get("/",response_model=List[PipelineCircuitBreakerResponse])
async def get_all_pipeline_circuit_breakers_for_tenant(tenant_id: int, session: AsyncSession=Depends(get_db), limit: int | None=Query(default=None,ge=1), offset: int=Query(default=0, ge=0)): #We user Query() to set constraints and for swagger docs. 
    #Limit must be greater than equal to 1 and offset greater than equal to 0 
    try:
        pipeline_circuit_breakers=await get_all_pipeline_circuit_breakers_for_tenant_service(tenant_id, session, limit, offset)
    except SQLAlchemyError:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Database error while fetching pipeline circuit breakers")
    
    if pipeline_circuit_breakers is None: #needs 'is None' instead of 'not pipeline_circuit_breakers' None indicates tenant was not found, 
        # and an empty pipeline_circuit_breakers list indicates 0 returned pipeline circuit breakers
        raise HTTPException(status_code=404,detail="Tenant not found. Please check the tenant_id")
    
    return pipeline_circuit_breakers

# UPDATE PIPELINE CIRCUIT BREAKER STATE
@pipeline_circuit_breakers_router.put("/", response_model=PipelineCircuitBreakerResponse, status_code=status.HTTP_200_OK)
async def update_pipeline_circuit_breaker(tenant_id: int, pipeline_id: int, breaker_data: PipelineCircuitBreakerUpdate, session: AsyncSession=Depends(get_db)):
    try:
        pipeline_circuit_breaker=await update_pipeline_circuit_breaker_service(tenant_id,pipeline_id,breaker_data,session)

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,detail=str(e))
    except IntegrityError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,detail="Pipeline circuit breaker could not be updated because of a database constraint violation.")
    except SQLAlchemyError:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,detail="Database error while updating pipeline circuit breaker.")
    
    if not pipeline_circuit_breaker:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pipeline circuit breaker not found. Please check the pipeline_id")
    
    return pipeline_circuit_breaker