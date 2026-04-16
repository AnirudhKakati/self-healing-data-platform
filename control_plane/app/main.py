from fastapi import FastAPI
from control_plane.app.routes.tenants import router as tenant_router
from control_plane.app.routes.pipelines import router as pipeline_router
from control_plane.app.routes.pipeline_steps import router as pipeline_step_router
from control_plane.app.routes.schedules import router as schedule_router
from control_plane.app.routes.pipeline_runs import pipeline_runs_router, tenant_runs_router

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