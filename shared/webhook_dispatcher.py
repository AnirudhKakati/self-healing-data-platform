import httpx
from shared.utils import now_naive
from shared.db import async_session
from control_plane.app.models.webhook_callbacks import WebhookCallback
from sqlalchemy.exc import SQLAlchemyError

async def dispatch_webhook_callback(callback_url: str, run_id: int, pipeline_id: int, tenant_id: int, status: str):
    payload={"run_id":run_id, "pipeline_id": pipeline_id, "tenant_id":tenant_id, "status":status, "timestamp":now_naive().isoformat(), "recommendation_url":None} #recommendation_url is None for now
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