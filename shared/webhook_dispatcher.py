import httpx
from shared.utils import now_naive
from shared.db import async_session
from control_plane.app.models.webhook_callbacks import WebhookCallback
from sqlalchemy.exc import SQLAlchemyError

async def dispatch_webhook_callback(callback_url: str, run_id: int, pipeline_id: int, tenant_id: int, status: str, recommendation_id: int|None=None):
    #recommendation_id is the new optional parameter. when None, recommendations_url stays None in the payload.
    #when populated, we construct a URL pointing to the recommendation resource on the control plane.
    #note: we build the URL with the path only, not a fully qualified scheme://host.
    #the tenant's webhook receiver should resolve it against the control plane base URL they configured.
    #we could hardcode http://localhost:8000 here for local dev, but that would leak into production —
    #better to keep the dispatcher portable and let deployment-time config decide the base URL later.
    #for now we emit the resource path; when we move to GCP we'll inject CONTROL_PLANE_BASE_URL from config.
    recommendations_url=None
    if recommendation_id is not None:
        recommendations_url=f"/tenants/{tenant_id}/pipelines/{pipeline_id}/runs/{run_id}/recommendations/{recommendation_id}"
    
    payload={"run_id":run_id, "pipeline_id": pipeline_id, "tenant_id":tenant_id, "status":status, "timestamp":now_naive().isoformat(), "recommendations_url":recommendations_url}
    payload["event"]="run.completed" if status=="success" else "run.failed"

    webhook_callback_dict={"tenant_id": tenant_id, "pipeline_id": pipeline_id, "run_id": run_id, "callback_url": callback_url, "payload": payload}
    
    try: #try sending the payload
        async with httpx.AsyncClient(timeout=15) as client: #timeout prevents webhook requests from hanging indefinitely if the callback endpoint is slow or unresponsive
            #so if no response within the timeout, we go to our except block
            response=await client.post(url=callback_url,json=payload)
        
        webhook_callback_dict["http_status_code"]=response.status_code

        if 200<=response.status_code<300: 
            webhook_callback_dict["status"]="success"
        else: #if non 2xx messages then we mark it as failed
            webhook_callback_dict["status"]="failed"
            webhook_callback_dict["error_message"]=f"Webhook returned non-2xx status code: {response.status_code}"
        
    except Exception as e: #if an error occurs then we mark it as failed
        webhook_callback_dict["status"]="failed"
        webhook_callback_dict["error_message"]=str(e)

    #always try to write the webhook delivery result to the webhook_callbacks audit table
    async with async_session() as session:
        try:
            webhook_callback=WebhookCallback(**webhook_callback_dict)
            session.add(webhook_callback)
            await session.commit()
            await session.refresh(webhook_callback)

            return webhook_callback
        
        except SQLAlchemyError:
            await session.rollback()
            print("Failed to write to webhook_callbacks table")