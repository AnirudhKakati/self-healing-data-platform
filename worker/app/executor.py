from shared.db import async_session
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import select,update
from control_plane.app.models.pipeline_runs import PipelineRun
from control_plane.app.models.pipeline_steps import PipelineStep
from control_plane.app.models.pipeline_circuit_breakers import PipelineCircuitBreaker
from datetime import datetime
from worker.app.exceptions import InvalidPipelineRunStatus, UnknownStepTypeError
from worker.app.step_handlers import step_registry

async def run_executor_service(run_id: int):
    async with async_session() as session:
        try:
            #first get the pipeline run so we can get pipeline_id for the circuit breaker check
            result=await session.execute(select(PipelineRun).where(PipelineRun.id==run_id))
            pipeline_run=result.scalar_one_or_none()
            if not pipeline_run:
                raise ValueError(f"Pipeline run {run_id} not found")
            pipeline_id=pipeline_run.pipeline_id

            #check if this pipeline has an open circuit breaker
            result=await session.execute(select(PipelineCircuitBreaker).where(PipelineCircuitBreaker.pipeline_id==pipeline_id))
            pipeline_circuit_breaker=result.scalar_one_or_none()    

            #if circuit breaker is open, block the run before execution starts
            if pipeline_circuit_breaker and pipeline_circuit_breaker.state=="open":
                # we only block the run if it is still queued.
                # This avoids accidentally overwriting running/success/failed runs.
                now=now_naive()
                result=await session.execute(update(PipelineRun).where(PipelineRun.id==run_id,PipelineRun.status=="queued")
                    .values(status="blocked",ended_at=now,updated_at=now,error_type="CircuitBreakerOpen",error_message="Pipeline circuit breaker is open",))
            
                await session.commit()
                
                if result.rowcount==0: #if no rows were updated, then we check whether the pipeline_run is missing, or if the status is not 'queued'
                    result=await session.execute(select(PipelineRun).where(PipelineRun.id==run_id))
                    pipeline_run=result.scalar_one_or_none()
                    if not pipeline_run: #pipeline run doesn't exist
                        raise ValueError(f"Pipeline run {run_id} not found")
                    #otherwise, the status was not "queued"
                    raise InvalidPipelineRunStatus(f"Pipeline run {run_id} is in '{pipeline_run.status}' state, expected 'queued'")

                result=await session.execute(select(PipelineRun).where(PipelineRun.id == run_id))
                pipeline_run=result.scalar_one_or_none()
                
                print("Pipeline blocked due to an open circuit breaker")
                return pipeline_run #return without executing anything else
            #else case when the pipeline circuit breaker doesn't exist for this pipeline, or the state isn't open. This means we can proceed with the execution.

            #atomically claim this run by changing queued -> running.
            #we immediately fetch the run and mark status as running, instead of first doing a select and then updating it, because between the 
            #time the select and update runs, we might get another select request which finds status='queued' and executes this run
            now=now_naive()
            result=await session.execute(update(PipelineRun).where(PipelineRun.id==run_id,PipelineRun.status=="queued").values(
                    status="running",started_at=now,updated_at=now))

            await session.commit()

        except SQLAlchemyError:
            await session.rollback()
            raise
        
        #if rowcount is 0, the run was not queued anymore
        if result.rowcount==0: 
            result=await session.execute(select(PipelineRun).where(PipelineRun.id==run_id))
            pipeline_run=result.scalar_one_or_none()

            if not pipeline_run: #pipeline run doesn't exist
                raise ValueError(f"Pipeline run {run_id} not found")
            raise InvalidPipelineRunStatus(f"Pipeline run {run_id} is in '{pipeline_run.status}' state, expected 'queued'")

        #else case when the pipeline was marked as running 
        #re-fetch the run after marking it as running
        result=await session.execute(select(PipelineRun).where(PipelineRun.id==run_id))
        pipeline_run=result.scalar_one_or_none()
        if not pipeline_run:
            raise ValueError(f"Pipeline run {run_id} not found")
        
        current_step_type=None
        try:
            #fetch pipeline steps of this pipeline
            #use pipeline_run.pipeline_id from the fresh re-fetch after claiming the run
            result=await session.execute(select(PipelineStep).where(PipelineStep.pipeline_id==pipeline_run.pipeline_id).order_by(PipelineStep.step_order))
            pipeline_steps=result.scalars().all()

            #this shared dictionary is passed between steps.
            #earlier steps can write values here, and later steps can read them.
            run_context={"run_id":run_id, "pipeline_id": pipeline_run.pipeline_id, 
                         "tenant_id":pipeline_run.tenant_id} #will be built dynamically during execution
            
            for step in pipeline_steps:
                current_step_type=step.step_type
                print(f"step_order={step.step_order}, step_type={current_step_type}, config={step.config}")
                perform_step=step_registry.get(current_step_type)#get the corresponding function for that step
                if not perform_step: #case when no corresponding function exists for the step type
                    raise UnknownStepTypeError(f"Unknown step type: {current_step_type}")
                await perform_step(step.config, run_context) #call the step's function with the config and the run_context passed as parameter
                
                # in the future, we might want to update the updated_at field after every step of the pipeline execution
                # pipeline_run.updated_at=datetime.now().replace(tzinfo=None) #updated_at is updated each time a step runs
                # await session.commit()
            
            #if every step completed update status to success and add the ended_at
            now=now_naive()
            pipeline_run.status="success"
            pipeline_run.ended_at=now
            pipeline_run.updated_at=now
            await session.commit()
            await session.refresh(pipeline_run)

            return pipeline_run

        except Exception as e:  #capture step failures and persist run failure details
            await session.rollback()

            try:
                #re-fetch fresh object after rollback
                result=await session.execute(select(PipelineRun).where(PipelineRun.id==run_id))
                pipeline_run=result.scalar_one_or_none()

                if pipeline_run:
                    now=datetime.now().replace(tzinfo=None)
                    pipeline_run.status="failed"
                    pipeline_run.ended_at=now
                    pipeline_run.updated_at=now
                    pipeline_run.error_type=current_step_type or type(e).__name__
                    pipeline_run.error_message=str(e)
                    await session.commit()
                    await session.refresh(pipeline_run)

            except Exception as inner_e:
                #worst case: log it, but don’t mask original error
                print(f"Failed to update run as failed: {inner_e}")

            raise #re-raise original error

def now_naive():
    # helper function to get current timezone-naive time
    return datetime.now().replace(tzinfo=None)