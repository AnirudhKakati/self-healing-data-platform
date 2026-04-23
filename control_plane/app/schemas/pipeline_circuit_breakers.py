from pydantic import BaseModel
from datetime import datetime
from typing import Optional, Literal

StateType=Literal["closed", "open", "half-open"]

class PipelineCircuitBreakerResponse(BaseModel):

    id: int
    tenant_id: int
    pipeline_id: int
    state: StateType
    failure_reason: Optional[str]
    retry_after: Optional[datetime]
    created_at: datetime
    updated_at: Optional[datetime]

    model_config = {
        "from_attributes": True
    }

class PipelineCircuitBreakerUpdate(BaseModel): 
    state: StateType
    