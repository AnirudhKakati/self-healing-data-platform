from shared.db import async_session
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import select, update, func
from control_plane.app.models.pipelines import Pipeline
from control_plane.app.models.pipeline_runs import PipelineRun
from control_plane.app.models.pipeline_steps import PipelineStep
from control_plane.app.models.pipeline_circuit_breakers import PipelineCircuitBreaker
from datetime import timedelta
from worker.app.exceptions import InvalidPipelineRunStatus, UnknownStepTypeError, ObservabilityRecordingError
from worker.app.step_handlers import step_registry
from shared.utils import now_naive
from shared.webhook_dispatcher import dispatch_webhook_callback
import asyncio
import random
from pathlib import Path
import json

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
            #this shared dictionary is passed between steps.
            #earlier steps can write values here, and later steps can read them.
            run_context={"run_id":run_id, "pipeline_id": pipeline_run.pipeline_id, 
                         "tenant_id":pipeline_run.tenant_id, "retry_count": 0} #will be built dynamically during execution
            
            #fetch pipeline steps of this pipeline
            #use pipeline_run.pipeline_id from the fresh re-fetch after claiming the run
            result=await session.execute(select(PipelineStep).where(PipelineStep.pipeline_id==pipeline_run.pipeline_id).order_by(PipelineStep.step_order))
            pipeline_steps=result.scalars().all()

            for step in pipeline_steps:
                current_step_type=step.step_type
                config=step.config or {}
                print(f"step_order={step.step_order}, step_type={current_step_type}, config={config}")
                perform_step=step_registry.get(current_step_type)#get the corresponding function for that step
                if not perform_step: #case when no corresponding function exists for the step type
                    raise UnknownStepTypeError(f"Unknown step type: {current_step_type}")
                
                retry_config=config.get("retry",{}) #if no retry_config, it means this step won't have retries
                #so the following fields would be 0/None in that case
                max_retries=retry_config.get("max_retries",0) 
                strategy=retry_config.get("strategy", None)
                base_delay=retry_config.get("base_delay", 0)
                
                max_attempts=max_retries+1 #total attempts = first attempt + number of retries

                for attempt in range(1,max_attempts+1): 
                    try:
                        await perform_step(step.config, run_context) #call the step's function with the config and the run_context passed as parameter
                        
                        #record this step attempt in the run_context
                        run_context.setdefault("step_attempts", []).append({"step_order":step.step_order,"step_type":current_step_type,
                                                                      "attempt":attempt,"status": "success","error": None,"delay": 0})
                        break #if perform_step executes, then we break out of the loop

                    except Exception as e:

                        print(f"Retrying {current_step_type}, attempt : {attempt}, Max attempts : {max_attempts}")
                        is_final_attempt= attempt==max_attempts #it is the final atttempt if attempt count is equal to max attempt count

                        #if its the final attempt then the delay for next step is 0, else we calculate the delay
                        delay=0 if is_final_attempt else calculate_delay(strategy,base_delay,attempt)

                        #record this step attempt in the run_context
                        run_context.setdefault("step_attempts",[]).append({"step_order":step.step_order,"step_type":current_step_type,
                                                                     "attempt":attempt,"status":"failed","error":str(e),"delay": delay})
                        
                        #the final attempt check is after recording the step attempt to ensure even the final step attempt is recorded properly
                        if is_final_attempt: #if we reach the final attempt for this step, the outer error is raised and the run fails
                            raise 
                        
                        #when we retry, we also increase retry_count by 1 in run_context
                        run_context["retry_count"]=run_context.get("retry_count", 0) + 1

                        try:
                            pipeline_run.retry_count+=1
                            pipeline_run.updated_at=now_naive()
                            pipeline_run.status="retrying"
                            await session.commit()
                            await session.refresh(pipeline_run)
                        except Exception as inner_e:
                            #worst case: log it, but don’t mask original error
                            await session.rollback()
                            print(f"Failed to update retry count: {inner_e}")
                        
                        await asyncio.sleep(delay)
            
            #if every step completed update status to success and add the ended_at
            now=now_naive()
            pipeline_run.status="success"
            pipeline_run.ended_at=now
            pipeline_run.updated_at=now
            await session.commit()
            await session.refresh(pipeline_run)

            run_context["run_status"]="success"

            #on a successful run, if the circuit breaker state was half-open, we mark it as closed.
            try:
                result=await session.execute(select(PipelineCircuitBreaker).where(PipelineCircuitBreaker.pipeline_id==pipeline_id))
                pipeline_circuit_breaker=result.scalar_one_or_none()
                if pipeline_circuit_breaker and pipeline_circuit_breaker.state=="half-open":
                    pipeline_circuit_breaker.state='closed'
                    #closed circuit indicates no failures, so we clear these fields
                    pipeline_circuit_breaker.failure_reason=None
                    pipeline_circuit_breaker.retry_after=None
                    pipeline_circuit_breaker.updated_at=now_naive()
                    await session.commit()
                    await session.refresh(pipeline_circuit_breaker)

            except Exception as inner_e:
                await session.rollback()
                print(f"Failed to update pipeline circuit breaker state : {inner_e}")
                
            return pipeline_run

        except Exception as e:  #capture step failures and persist run failure details
            await session.rollback()
            run_context["run_status"]="failed"
            run_context["error_type"]=type(e).__name__
            run_context["error_message"]=str(e)


            try:
                #re-fetch fresh object after rollback
                result=await session.execute(select(PipelineRun).where(PipelineRun.id==run_id))
                pipeline_run=result.scalar_one_or_none()

                if pipeline_run:
                    now=now_naive()
                    pipeline_run.status="failed"
                    pipeline_run.ended_at=now
                    pipeline_run.updated_at=now
                    pipeline_run.error_type=type(e).__name__
                    pipeline_run.error_message=str(e)
                    await session.commit()
                    await session.refresh(pipeline_run)

            except Exception as inner_e:
                #worst case: log it, but don’t mask original error
                await session.rollback()
                print(f"Failed to update run as failed: {inner_e}")

            #now check if the pipeline circuit breaker state needs to be updated
            try:
                result=await session.execute(select(PipelineCircuitBreaker).where(PipelineCircuitBreaker.pipeline_id==pipeline_id))
                pipeline_circuit_breaker=result.scalar_one_or_none()
                if pipeline_circuit_breaker:
                    #we get the failure_count_threshold and the failure_window_minutes for this pipeline
                    failure_count_threshold=pipeline_circuit_breaker.failure_count_threshold
                    failure_window_minutes=pipeline_circuit_breaker.failure_window_minutes

                    current_time=now_naive()
                    failure_reason=f"Error Type:{type(e).__name__} Error message: {str(e)}"
                    
                    #first check if the circuit state was half-open. If it was half-open we immediately mark the circuit state as open
                    if pipeline_circuit_breaker.state=="half-open":
                        mark_circuit_breaker_open(pipeline_circuit_breaker,failure_reason,current_time+timedelta(minutes=failure_window_minutes))
                        await session.commit()
                        await session.refresh(pipeline_circuit_breaker)
                        
                    elif pipeline_circuit_breaker.state=="closed": #the circuit state was closed so we check the failure threshold

                        #we get the count of failed runs within the failure window and see if it exceeds the threshold
                        window_start=current_time-timedelta(minutes=failure_window_minutes)
                        result=await session.execute(select(func.count()).select_from(PipelineRun).where(PipelineRun.pipeline_id==pipeline_id, PipelineRun.status=='failed', PipelineRun.ended_at>=window_start))
                        failed_runs_count=result.scalar_one()
                        
                        if failed_runs_count>=failure_count_threshold: #if count exceeds the threshold we mark the circuit breaker state as open
                            mark_circuit_breaker_open(pipeline_circuit_breaker,failure_reason,current_time+timedelta(minutes=failure_window_minutes))
                            await session.commit()
                            await session.refresh(pipeline_circuit_breaker)
                    #we do elif and explicitly check if state==close rather than doing an 'else' block because another run could have already marked 
                    # this pipeline circuit breaker as open while this run was executing so we would be opening a circuit which was already open and do
                    # wasteful work. So we avoid that 

            except Exception as inner_e:
                await session.rollback()
                print(f"Failed to update pipeline circuit breaker state : {inner_e}")

            raise #re-raise original error
        finally:
            #for each pipeline run, always run observability recording
            try:
                await run_observability_recording(run_context)
            except ObservabilityRecordingError as e: #if observability recording fails, we just log it. We dont want it to overwrite the errors in the actual pipeline run
                print(f"Failed to write observability recording: {e}")

            #next, send webhook callback
            #so first try to fetch the callback_url for the pipeline
            try:
                result=await session.execute(select(Pipeline).where(Pipeline.id==pipeline_run.pipeline_id))
                pipeline=result.scalar_one_or_none()
                if pipeline and pipeline.callback_url: #check if we have a callback url for this pipeline
                    asyncio.create_task(dispatch_webhook_callback(pipeline.callback_url, run_id, pipeline_run.pipeline_id, pipeline_run.tenant_id, run_context["run_status"]))
                    
            except SQLAlchemyError:
                await session.rollback()
                print(f"Failed to fetch pipeline callback_url")
            

async def run_observability_recording(run_context):
    print(f"Running Observability Recording")

    run_id=run_context["run_id"]

    #save in a local directory for now
    run_dir=Path("data")/"runs"/str(run_id)
    run_dir.mkdir(parents=True, exist_ok=True)

    filename="run_context.json"
    file_path=run_dir/filename

    #save file
    try:
        with open(file_path,"w") as f:
            json.dump(run_context, f, indent=4)
    except Exception as e:
        raise ObservabilityRecordingError(f"Failed to write {str(file_path)}: {e}")
    print("Successfully completed observability recording step")


#helper functions
def calculate_delay(strategy, base_delay, attempt):
    #helper function to calculate the delay based on retry strategy
    if strategy=="exponential_backoff":
        print("retrying with exponential backoff")
        return base_delay*(2**(attempt-1))
    elif strategy=="exponential_backoff_jitter":
        print("retrying with exponential backoff jitter")
        calculated_delay=base_delay*(2**(attempt-1))
        return calculated_delay+random.uniform(0.5*calculated_delay,calculated_delay)
    else:
        print("No known retry strategy provided")
        return base_delay
    
def mark_circuit_breaker_open(pipeline_circuit_breaker, failure_reason, retry_after):
    #helper function to mark pipeline circuit breaker state as open
    pipeline_circuit_breaker.state='open'
    pipeline_circuit_breaker.failure_reason=failure_reason
    pipeline_circuit_breaker.retry_after=retry_after
    pipeline_circuit_breaker.updated_at=now_naive()