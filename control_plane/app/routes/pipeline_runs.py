from fastapi import APIRouter, Depends, status, HTTPException, Query 
from sqlalchemy.ext.asyncio import AsyncSession
from shared.db import get_db
from control_plane.app.services.pipeline_runs import get_pipeline_run_service, get_all_pipeline_runs_service, get_all_pipeline_runs_for_tenant_service, create_pipeline_run_service
from control_plane.app.schemas.pipeline_runs import PipelineRunResponse, PipelineRunStatusResponse
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from typing import List
from shared.redis_client import redis_client

pipeline_runs_router=APIRouter()
tenant_runs_router=APIRouter()

#GET PIPELINE RUN BY ID
@pipeline_runs_router.get("/{run_id}", response_model=PipelineRunResponse)
async def get_pipeline_run(tenant_id: int, pipeline_id: int, run_id: int, session: AsyncSession=Depends(get_db)):

    run_data=await get_pipeline_run_service(tenant_id,pipeline_id,run_id,session)
    if not run_data:
        raise HTTPException(status_code=404,detail="Run not found. Please check the run_id")

    return run_data

#GET PIPELINE RUN STATUS
@pipeline_runs_router.get("/{run_id}/status", response_model=PipelineRunStatusResponse)
async def get_pipeline_run_status(tenant_id: int, pipeline_id: int, run_id: int, session: AsyncSession=Depends(get_db)):
    run_data=await get_pipeline_run_service(tenant_id,pipeline_id,run_id,session)
    if not run_data:
        raise HTTPException(status_code=404,detail="Run not found. Please check the run_id")
    
    return run_data

#GET ALL RUNS FOR A PIPELINE
@pipeline_runs_router.get("/",response_model=List[PipelineRunResponse])
async def get_all_pipeline_runs(tenant_id: int, pipeline_id: int, session: AsyncSession=Depends(get_db), limit: int | None=Query(default=None,ge=1), offset: int=Query(default=0, ge=0)): #We user Query() to set constraints and for swagger docs. 
    #Limit must be greater than equal to 1 and offset greater than equal to 0 
    try:
        pipeline_runs=await get_all_pipeline_runs_service(tenant_id, pipeline_id, session, limit, offset)
    except SQLAlchemyError:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Database error while fetching pipeline runs")
    
    if pipeline_runs is None: #needs 'is None' instead of 'not pipeline_runs' because None indicates pipeline was not found (atleast not for this tenant, or the tenant doesn't exist), 
        # and an empty pipeline_runs list indicates 0 returned pipeline steps
        raise HTTPException(status_code=404,detail="Pipeline not found. Please check the pipeline_id")
    
    return pipeline_runs

#GET ALL PIPELINE RUNS FOR A TENANT
@tenant_runs_router.get("/",response_model=List[PipelineRunResponse])
async def get_all_pipeline_runs_for_tenant(tenant_id: int, session: AsyncSession=Depends(get_db), limit: int | None=Query(default=None,ge=1), offset: int=Query(default=0, ge=0)): #We user Query() to set constraints and for swagger docs. 
    #Limit must be greater than equal to 1 and offset greater than equal to 0 
    try:
        pipeline_runs=await get_all_pipeline_runs_for_tenant_service(tenant_id, session, limit, offset)
    except SQLAlchemyError:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Database error while fetching pipeline runs")
    
    if pipeline_runs is None: #needs 'is None' instead of 'not pipeline_runs' because None indicates pipeline was not found (atleast not for this tenant, or the tenant doesn't exist), 
        # and an empty pipeline_runs list indicates 0 returned pipeline runs
        raise HTTPException(status_code=404,detail="Tenant not found. Please check the tenant_id")
    
    return pipeline_runs

#CREATE A PIPELINE RUN
@pipeline_runs_router.post("/",response_model=PipelineRunResponse, status_code=status.HTTP_201_CREATED)
async def create_pipeline_run(tenant_id: int, pipeline_id: int, session: AsyncSession=Depends(get_db)):
    try:
        pipeline_run=await create_pipeline_run_service(tenant_id, pipeline_id, session)
    except IntegrityError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,detail="Pipeline run could not be created because of a database constraint violation.")
    except SQLAlchemyError:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,detail="Database error while creating pipeline run")
    
    if not pipeline_run:
        raise HTTPException(status_code=404,detail="Pipeline not found. Please check the pipeline_id")

    #push to redis
    try:
        await redis_client.rpush("pipeline_runs", str(pipeline_run.id))
    except Exception: #generic exception for now
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,detail="Pipeline run was created, but failed to enqueue for execution.")
    
    return pipeline_run