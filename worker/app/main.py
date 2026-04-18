from fastapi import FastAPI, BackgroundTasks, status
from worker.app.executor import run_executor_service 
app=FastAPI()

@app.get("/")
def get_root():
    return {"message":"worker app is running!","docs":"/docs"}

@app.get("/health")
def get_health():
    return {"status": "healthy"}

@app.post("/run/{run_id}",status_code=status.HTTP_202_ACCEPTED)
async def run_executor(run_id: int, background_tasks: BackgroundTasks):
    background_tasks.add_task(run_executor_service,run_id)
    return {"run_id":run_id,"status":"accepted"}
