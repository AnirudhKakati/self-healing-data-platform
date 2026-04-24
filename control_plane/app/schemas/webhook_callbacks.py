from pydantic import BaseModel
from datetime import datetime
from typing import Optional, Literal

StatusType=Literal["success", "pending", "failed"]

class WebhookCallbackResponse(BaseModel):

    id: int
    tenant_id: int
    pipeline_id: int
    run_id: int
    callback_url: str
    payload: Optional[dict]
    status: StatusType
    http_status_code: Optional[int]
    error_message: Optional[str]
    created_at: datetime

    model_config = {
        "from_attributes": True
    }