from control_plane.app.models.tenants import Tenant
from control_plane.app.models.pipelines import Pipeline
from control_plane.app.models.pipeline_runs import PipelineRun
from control_plane.app.models.webhook_callbacks import WebhookCallback
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

async def get_webhook_callback_service(tenant_id: int, pipeline_id: int, run_id: int, callback_id: int, session: AsyncSession):
    #the callback must exist, belong to the given pipeline, and that pipeline must belong to the tenant
    #we join through PipelineRun to verify pipeline and tenant ownership without a separate query
    result=await session.execute(
        select(WebhookCallback).join(PipelineRun,WebhookCallback.run_id==PipelineRun.id)
        .where(WebhookCallback.id==callback_id,WebhookCallback.run_id==run_id,PipelineRun.tenant_id==tenant_id, PipelineRun.pipeline_id==pipeline_id))
    webhook_callback=result.scalar_one_or_none()
    return webhook_callback

async def get_all_webhook_callbacks_service(tenant_id: int, pipeline_id: int, run_id: int, session: AsyncSession, limit: int|None = None, offset: int = 0):
    #we verify the run exists and belongs to this tenant and pipeline
    result=await session.execute(select(PipelineRun).where(PipelineRun.id==run_id,PipelineRun.tenant_id==tenant_id,PipelineRun.pipeline_id==pipeline_id))
    pipeline_run=result.scalar_one_or_none()
    if not pipeline_run:
        return None #route will handle 404

    statement=select(WebhookCallback).where(WebhookCallback.run_id==run_id).order_by(WebhookCallback.created_at.desc()).offset(offset)
    if limit is not None:
        statement=statement.limit(limit)

    result=await session.execute(statement)
    webhook_callbacks=result.scalars().all()
    return webhook_callbacks

async def get_all_webhook_callbacks_for_pipeline_service(tenant_id: int, pipeline_id: int, session: AsyncSession, limit: int|None = None, offset: int = 0):
    #we verify the pipeline exists and belongs to this tenant
    result=await session.execute(select(Pipeline).where(Pipeline.id==pipeline_id,Pipeline.tenant_id==tenant_id))
    pipeline=result.scalar_one_or_none()
    if not pipeline:
        return None #route will handle 404

    statement=select(WebhookCallback).where(WebhookCallback.pipeline_id==pipeline_id).order_by(WebhookCallback.created_at.desc()).offset(offset)
    if limit is not None:
        statement=statement.limit(limit)

    result=await session.execute(statement)
    webhook_callbacks=result.scalars().all()
    return webhook_callbacks

async def get_all_webhook_callbacks_for_tenant_service(tenant_id: int, session: AsyncSession, limit: int|None = None, offset: int = 0):
    #we verify the tenant exists
    result=await session.execute(select(Tenant).where(Tenant.id==tenant_id))
    tenant=result.scalar_one_or_none()
    if not tenant:
        return None #route will handle 404

    statement=select(WebhookCallback).where(WebhookCallback.tenant_id==tenant_id).order_by(WebhookCallback.created_at.desc()).offset(offset)
    if limit is not None:
        statement=statement.limit(limit)

    result=await session.execute(statement)
    webhook_callbacks=result.scalars().all()
    return webhook_callbacks