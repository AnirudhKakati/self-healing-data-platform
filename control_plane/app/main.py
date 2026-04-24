from fastapi import FastAPI
from control_plane.app.routes.tenants import router as tenant_router
from control_plane.app.routes.pipelines import router as pipeline_router
from control_plane.app.routes.pipeline_steps import router as pipeline_step_router
from control_plane.app.routes.schedules import router as schedule_router
from control_plane.app.routes.pipeline_runs import pipeline_runs_router, tenant_runs_router
from control_plane.app.routes.agent_recommendations import run_recommendations_router, pipeline_recommendations_router, tenant_recommendations_router
from control_plane.app.routes.pipeline_circuit_breakers import pipeline_circuit_breakers_router, tenant_circuit_breakers_router
from control_plane.app.routes.webhook_callbacks import run_callbacks_router, pipeline_callbacks_router, tenant_callbacks_router

app=FastAPI()

@app.get("/")
def get_root():
    return {"message":"control plane app is running!","docs":"/docs"}

@app.get("/health")
def get_health():
    return {"status": "healthy"}

app.include_router(tenant_router,prefix="/tenants",tags=["Tenants"]) #add the tenants routes
app.include_router(pipeline_router,prefix="/tenants/{tenant_id}/pipelines",tags=["Pipelines"]) #add the pipelines routes
app.include_router(pipeline_step_router,prefix="/tenants/{tenant_id}/pipelines/{pipeline_id}/steps",tags=["Pipeline_steps"]) #add the pipeline steps routes
app.include_router(schedule_router,prefix="/tenants/{tenant_id}/pipelines/{pipeline_id}/schedules",tags=["Schedules"]) #add the schedules routes

#add the pipeline runs routes
app.include_router(pipeline_runs_router,prefix="/tenants/{tenant_id}/pipelines/{pipeline_id}/runs",tags=["Pipeline_runs"]) 
app.include_router(tenant_runs_router,prefix="/tenants/{tenant_id}/runs",tags=["Tenant_pipeline_runs"]) 

# add the agent recommendations routes
app.include_router(run_recommendations_router,prefix="/tenants/{tenant_id}/pipelines/{pipeline_id}/runs/{run_id}/recommendations",tags=["Run_agent_recommendations"])
app.include_router(pipeline_recommendations_router,prefix="/tenants/{tenant_id}/pipelines/{pipeline_id}/recommendations",tags=["Pipeline_agent_recommendations"])
app.include_router(tenant_recommendations_router,prefix="/tenants/{tenant_id}/recommendations",tags=["Tenant_agent_recommendations"])

# add the pipeline circuit breaker routes
app.include_router(pipeline_circuit_breakers_router,prefix="/tenants/{tenant_id}/pipelines/{pipeline_id}/circuit_breakers",tags=["Pipeline_circuit_breakers"]) 
app.include_router(tenant_circuit_breakers_router,prefix="/tenants/{tenant_id}/circuit_breakers",tags=["Tenant_circuit_breakers"]) 

# add the webhook callbacks routes
app.include_router(run_callbacks_router,prefix="/tenants/{tenant_id}/pipelines/{pipeline_id}/runs/{run_id}/callbacks",tags=["Run_webhook_callbacks"])
app.include_router(pipeline_callbacks_router,prefix="/tenants/{tenant_id}/pipelines/{pipeline_id}/callbacks",tags=["Pipeline_webhook_callbacks"])
app.include_router(tenant_callbacks_router,prefix="/tenants/{tenant_id}/callbacks",tags=["Tenant_webhook_callbacks"])