from pydantic import BaseModel, Field
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
    failure_count_threshold: int=Field(ge=1)
    failure_window_minutes: int=Field(ge=1)

    model_config = {
        "from_attributes": True
    }

class PipelineCircuitBreakerUpdate(BaseModel): 
    state: Optional[StateType]=None
    failure_count_threshold: Optional[int]=Field(None,ge=1)
    failure_window_minutes: Optional[int]=Field(None,ge=1)