from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class PipelineRunResponse(BaseModel):

    id: int
    tenant_id: int
    pipeline_id: int
    status: str
    created_at: datetime
    started_at: Optional[datetime]
    updated_at: Optional[datetime]
    ended_at: Optional[datetime]
    error_type: Optional[str]
    error_message: Optional[str]
    retry_count: int

    model_config = {
        "from_attributes": True
    }

class PipelineRunStatusResponse(BaseModel):
    id: int
    pipeline_id: int
    status: str
    started_at: Optional[datetime]
    updated_at: Optional[datetime]
    ended_at: Optional[datetime]

    model_config = {
        "from_attributes": True
    }