from fastapi import APIRouter, Depends, status, HTTPException, Query 
from sqlalchemy.ext.asyncio import AsyncSession
from shared.db import get_db
from control_plane.app.services.pipelines import create_pipeline_service, get_pipeline_service, get_all_pipelines_service, delete_pipeline_service, update_pipeline_service
from control_plane.app.schemas.pipelines import PipelineCreate, PipelineUpdate, PipelineResponse
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from typing import List

router=APIRouter()

#CREATE PIPELINE
@router.post("/", response_model=PipelineResponse, status_code=status.HTTP_201_CREATED)
async def create_pipeline(tenant_id: int, pipeline_data: PipelineCreate, session: AsyncSession = Depends(get_db)):

    try:
        pipeline=await create_pipeline_service(tenant_id, pipeline_data, session)
    except IntegrityError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,detail="Pipeline could not be created because of a database constraint violation.")
    except SQLAlchemyError:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,detail="Database error while creating pipeline.")
    
    if not pipeline:
        raise HTTPException(status_code=404,detail="Tenant not found. Please check the tenant_id")

    return pipeline

#GET PIPELINE BY ID
@router.get("/{pipeline_id}", response_model=PipelineResponse)
async def get_pipeline(tenant_id: int, pipeline_id: int, session: AsyncSession=Depends(get_db)):

    pipeline_data=await get_pipeline_service(tenant_id,pipeline_id,session)
    if not pipeline_data:
        raise HTTPException(status_code=404,detail="Pipeline not found. Please check the pipeline_id")

    return pipeline_data

#GET ALL PIPELINES FOR A TENANT. OPTIONAL LIMIT AND OFFSET
@router.get("/",response_model=List[PipelineResponse])
async def get_all_pipelines(tenant_id: int, session: AsyncSession=Depends(get_db), limit: int | None=Query(default=None,ge=1), offset: int=Query(default=0, ge=0)): #We user Query() to set constraints and for swagger docs. 
    #Limit must be greater than equal to 1 and offset greater than equal to 0 
    try:
        pipelines=await get_all_pipelines_service(tenant_id, session, limit, offset)
    except SQLAlchemyError:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Database error while fetching pipelines.")
    
    if pipelines is None: #needs 'is None' instead of 'not pipelines' because None indicates tenant not found, and an empty pipelines list indicates 0 returned pipelines
        raise HTTPException(status_code=404,detail="Tenant not found. Please check the tenant_id")
    
    return pipelines
    

#DELETE PIPELINE BY ID (ONLY BELONGING TO A SPECIFIC TENANT ID)
@router.delete("/{pipeline_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_pipeline(tenant_id: int, pipeline_id: int, session: AsyncSession=Depends(get_db)):
    try:
        deleted_rows= await delete_pipeline_service(tenant_id,pipeline_id,session)

    except SQLAlchemyError:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Database error while deleting pipeline")
    
    if deleted_rows==0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pipeline not found. Please check the pipeline_id")
    return

#UPDATE PIPELINE BY ID
@router.put("/{pipeline_id}", response_model=PipelineResponse, status_code=status.HTTP_200_OK)
async def update_pipeline(tenant_id: int, pipeline_id: int, pipeline_data: PipelineUpdate, session: AsyncSession=Depends(get_db)):
    try:
        pipeline=await update_pipeline_service(tenant_id,pipeline_id, pipeline_data,session)

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,detail=str(e))
    except IntegrityError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,detail="Pipeline could not be updated because of a database constraint violation.")
    except SQLAlchemyError:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,detail="Database error while updating pipeline.")
    
    
    if not pipeline:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pipeline not found. Please check the pipeline_id")
    
    return pipeline