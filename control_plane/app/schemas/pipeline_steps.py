from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional

#when creating a step, we specify what type of step it is, its execution order, and optionally a config dict. pipeline_id comes from the URL path, not the body.
#id, created_at are auto-generated; is_active defaults to True.
class PipelineStepCreate(BaseModel):
    step_type: str=Field(min_length=1,max_length=50)
    step_order: int=Field(ge=1)  #must be at least 1 — execution is sequential starting from 1
    config: Optional[dict]=None  #flexible JSON config, validated as a Python dict by Pydantic

#step_type and step_order are updatable in case the user wants to reorder steps or change what a step does
#each step belongs to a specific pipeline and that cannot be changed
class PipelineStepUpdate(BaseModel):
    step_type: Optional[str]=Field(None, min_length=1, max_length=50)
    step_order: Optional[int]=Field(None, ge=1)
    config: Optional[dict]=None
    is_active: Optional[bool]=None

class PipelineStepResponse(BaseModel):
    id: int
    pipeline_id: int
    step_type: str
    step_order: int
    config: Optional[dict]
    created_at: datetime
    is_active: bool

    model_config = {
        "from_attributes": True
    }