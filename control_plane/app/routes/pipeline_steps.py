from fastapi import APIRouter, Depends, status, HTTPException, Query 
from sqlalchemy.ext.asyncio import AsyncSession
from shared.db import get_db
from control_plane.app.services.pipeline_steps import create_pipeline_step_service, get_pipeline_step_service, get_all_pipeline_steps_service, delete_pipeline_step_service, update_pipeline_step_service
from control_plane.app.schemas.pipeline_steps import PipelineStepCreate, PipelineStepUpdate, PipelineStepResponse
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from typing import List

router=APIRouter()

#CREATE PIPELINE STEP
@router.post("/", response_model=PipelineStepResponse, status_code=status.HTTP_201_CREATED)
async def create_pipeline_step(tenant_id: int, pipeline_id: int, step_data: PipelineStepCreate, session: AsyncSession=Depends(get_db)):

    try:
        pipeline_step=await create_pipeline_step_service(tenant_id, pipeline_id, step_data, session)
    except IntegrityError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,detail="Pipeline step could not be created because of a database constraint violation.")
    except SQLAlchemyError:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,detail="Database error while creating pipeline step")
    
    if not pipeline_step:
        raise HTTPException(status_code=404,detail="Pipeline not found. Please check the pipeline_id")

    return pipeline_step

#GET PIPELINE STEP BY ID
@router.get("/{step_id}", response_model=PipelineStepResponse)
async def get_pipeline_step(tenant_id: int, pipeline_id: int, step_id: int, session: AsyncSession=Depends(get_db)):

    step_data=await get_pipeline_step_service(tenant_id,pipeline_id,step_id,session)
    if not step_data:
        raise HTTPException(status_code=404,detail="Pipline step not found. Please check the step_id")

    return step_data

#GET ALL STEPS FOR A PIPELINE. OPTIONAL LIMIT AND OFFSET
@router.get("/",response_model=List[PipelineStepResponse])
async def get_all_pipeline_steps(tenant_id: int, pipeline_id: int, session: AsyncSession=Depends(get_db), limit: int | None=Query(default=None,ge=1), offset: int=Query(default=0, ge=0)): #We user Query() to set constraints and for swagger docs. 
    #Limit must be greater than equal to 1 and offset greater than equal to 0 
    try:
        pipeline_steps=await get_all_pipeline_steps_service(tenant_id, pipeline_id, session, limit, offset)
    except SQLAlchemyError:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Database error while fetching pipeline steps")
    
    if pipeline_steps is None: #needs 'is None' instead of 'not pipeline_steps' because None indicates pipeline was not found (atleast not for this tenant, or the tenant doesn't exist), 
        # and an empty pipeline_steps list indicates 0 returned pipeline steps
        raise HTTPException(status_code=404,detail="Pipeline not found. Please check the pipeline_id")
    
    return pipeline_steps

#DELETE PIPELINE STEP BY ID (ONLY BELONGING TO A SPECIFIC PIPELINE ID)
@router.delete("/{step_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_pipeline_step(tenant_id: int, pipeline_id: int, step_id: int, session: AsyncSession=Depends(get_db)):
    try:
        deleted_rows= await delete_pipeline_step_service(tenant_id,pipeline_id,step_id,session)

    except SQLAlchemyError:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Database error while deleting pipeline step")
    
    if deleted_rows==0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pipeline step not found. Please check the step_id")
    return

#UPDATE PIPELINE STEP BY ID
@router.put("/{step_id}", response_model=PipelineStepResponse, status_code=status.HTTP_200_OK)
async def update_pipeline_step(tenant_id: int, pipeline_id: int, step_id: int, step_data: PipelineStepUpdate, session: AsyncSession=Depends(get_db)):
    try:
        pipeline_step=await update_pipeline_step_service(tenant_id,pipeline_id,step_id,step_data,session)

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,detail=str(e))
    except IntegrityError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,detail="Pipeline step could not be updated because of a database constraint violation.")
    except SQLAlchemyError:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,detail="Database error while updating pipeline step.")
    
    
    if not pipeline_step:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pipeline step not found. Please check the step_id")
    
    return pipeline_step