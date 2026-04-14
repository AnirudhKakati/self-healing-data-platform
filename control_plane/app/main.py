from fastapi import FastAPI
from control_plane.app.routes.tenants import router as tenant_router
from control_plane.app.routes.pipelines import router as pipeline_router
app=FastAPI()

@app.get("/")
def get_root():
    return {"message":"control plane app is running!","docs":"/docs"}

@app.get("/health")
def get_health():
    return {"status": "healthy"}

app.include_router(tenant_router,prefix="/tenants",tags=["Tenants"]) #add the tenants routes
app.include_router(pipeline_router,prefix="/tenants/{tenant_id}/pipelines",tags=["Pipelines"]) #add the pipelines routes