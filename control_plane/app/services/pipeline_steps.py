from control_plane.app.models.pipelines import Pipeline
from control_plane.app.models.pipeline_steps import PipelineStep
from control_plane.app.schemas.pipeline_steps import PipelineStepCreate, PipelineStepUpdate
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import delete, select

async def create_pipeline_step_service(tenant_id: int, pipeline_id: int, step_data: PipelineStepCreate, session: AsyncSession):
    #we need to verify the pipeline exists and belongs to this tenant
    #without this, someone could create steps on a pipeline belonging to another tenant
    result=await session.execute(select(Pipeline).where(Pipeline.id == pipeline_id, Pipeline.tenant_id == tenant_id))
    pipeline = result.scalar_one_or_none()
    if not pipeline:
        return None  # route will handle 404 not found

    step_dict=step_data.model_dump()
    step_dict["pipeline_id"]=pipeline_id  #inject pipeline_id from the URL, not the body
    step=PipelineStep(**step_dict)

    try:
        session.add(step)
        await session.commit()
        await session.refresh(step)
        return step
    except SQLAlchemyError:
        await session.rollback()
        raise

async def get_pipeline_step_service(tenant_id: int, pipeline_id: int, step_id: int, session: AsyncSession):
    #the step must exist, belong to the given pipeline, and that pipeline must belong to the tenant
    #we join through Pipeline to verify tenant ownership without a separate query
    result=await session.execute(
        select(PipelineStep).join(Pipeline,PipelineStep.pipeline_id==Pipeline.id).where(PipelineStep.id==step_id,PipelineStep.pipeline_id==pipeline_id,Pipeline.tenant_id==tenant_id)
        )
    pipeline_steps=result.scalar_one_or_none()
    return pipeline_steps


async def get_all_pipeline_steps_service(tenant_id: int, pipeline_id: int, session: AsyncSession, limit: int | None = None, offset: int = 0):
    
    #we verify the pipeline exists and belongs to this tenant
    result=await session.execute(select(Pipeline).where(Pipeline.id==pipeline_id,Pipeline.tenant_id==tenant_id))
    pipeline=result.scalar_one_or_none()
    if not pipeline:
        return None #route will handle 404

    #order by step_order instead of id as this is the natural ordering for steps
    statement=select(PipelineStep).where(PipelineStep.pipeline_id==pipeline_id).order_by(PipelineStep.step_order).offset(offset)
    if limit is not None:
        statement=statement.limit(limit)

    result=await session.execute(statement)
    pipeline_steps=result.scalars().all()
    return pipeline_steps


async def delete_pipeline_step_service(tenant_id: int, pipeline_id: int, step_id: int, session: AsyncSession):
    #we join through Pipeline to confirm the tenant owns this pipeline
    try:
        #first confirm the pipeline belongs to this tenant
        pipeline_result=await session.execute(select(Pipeline).where(Pipeline.id == pipeline_id, Pipeline.tenant_id == tenant_id))
        if not pipeline_result.scalar_one_or_none():
            return 0 #route treats 0 deleted rows as 404

        result=await session.execute(delete(PipelineStep).where(PipelineStep.id == step_id, PipelineStep.pipeline_id == pipeline_id))
        await session.commit()
        return result.rowcount
    except SQLAlchemyError:
        await session.rollback()
        raise


async def update_pipeline_step_service(tenant_id: int, pipeline_id: int, step_id: int, step_data: PipelineStepUpdate, session: AsyncSession):
    #again verify step exists under this pipeline under this tenant
    result=await session.execute(select(PipelineStep).join(Pipeline, PipelineStep.pipeline_id == Pipeline.id)
                                 .where(PipelineStep.id==step_id,PipelineStep.pipeline_id==pipeline_id,Pipeline.tenant_id==tenant_id))
    step=result.scalar_one_or_none()
    if not step:
        return None

    update_dict=step_data.model_dump(exclude_unset=True)
    if not update_dict:
        raise ValueError("No fields were provided for update.")

    try:
        for key, value in update_dict.items():
            setattr(step, key, value)
        await session.commit()
        await session.refresh(step)
        return step
    except SQLAlchemyError:
        await session.rollback()
        raise