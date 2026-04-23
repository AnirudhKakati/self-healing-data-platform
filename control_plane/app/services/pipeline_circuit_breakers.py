from control_plane.app.models.pipelines import Pipeline
from control_plane.app.models.tenants import Tenant
from control_plane.app.models.pipeline_circuit_breakers import PipelineCircuitBreaker
from control_plane.app.schemas.pipeline_circuit_breakers import PipelineCircuitBreakerUpdate
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import select
from datetime import datetime


async def get_pipeline_circuit_breaker_service(tenant_id: int, pipeline_id: int, session: AsyncSession):
    #the circuit breaker must exist, belong to the given pipeline, and that pipeline must belong to the tenant
    #we join through Pipeline to verify tenant ownership without a separate query
    result=await session.execute(
        select(PipelineCircuitBreaker).join(Pipeline,PipelineCircuitBreaker.pipeline_id==Pipeline.id).where(PipelineCircuitBreaker.pipeline_id==pipeline_id,Pipeline.tenant_id==tenant_id)
        )
    pipeline_circuit_breaker=result.scalar_one_or_none()
    return pipeline_circuit_breaker


async def get_all_pipeline_circuit_breakers_for_tenant_service(tenant_id: int, session: AsyncSession, limit: int | None = None, offset: int = 0):
    #we verify the tenant exists
    result=await session.execute(select(Tenant).where(Tenant.id==tenant_id))
    tenant=result.scalar_one_or_none()
    if not tenant:
        return None #route will handle 404

    statement=select(PipelineCircuitBreaker).where(PipelineCircuitBreaker.tenant_id==tenant_id).order_by(PipelineCircuitBreaker.created_at.desc()).offset(offset)
    if limit is not None:
        statement=statement.limit(limit)

    result=await session.execute(statement)
    pipeline_circuit_breakers=result.scalars().all()
    return pipeline_circuit_breakers


async def update_pipeline_circuit_breaker_service(tenant_id: int, pipeline_id: int, breaker_data: PipelineCircuitBreakerUpdate, session: AsyncSession):
    #again verify circuit breaker exists under this pipeline under this tenant
    result=await session.execute(select(PipelineCircuitBreaker).join(Pipeline, PipelineCircuitBreaker.pipeline_id == Pipeline.id).where(PipelineCircuitBreaker.pipeline_id==pipeline_id,Pipeline.tenant_id==tenant_id))
    pipeline_circuit_breaker=result.scalar_one_or_none()
    if not pipeline_circuit_breaker:
        return None
    
    try:
        pipeline_circuit_breaker.state=breaker_data.state
        pipeline_circuit_breaker.updated_at=datetime.now().replace(tzinfo=None)
        
        if breaker_data.state=="closed": #closed circuit indicates no failures, so we clear these fields
            pipeline_circuit_breaker.failure_reason=None
            pipeline_circuit_breaker.retry_after=None

        await session.commit()
        await session.refresh(pipeline_circuit_breaker)
        return pipeline_circuit_breaker
    except SQLAlchemyError:
        await session.rollback()
        raise