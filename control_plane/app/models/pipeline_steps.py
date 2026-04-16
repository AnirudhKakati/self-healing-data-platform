from shared.db import Base
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from sqlalchemy import ForeignKey, String, JSON, Integer, UniqueConstraint, func

class PipelineStep(Base):
    __tablename__="pipeline_steps"
    __table_args__=(UniqueConstraint("pipeline_id", "step_order", name="uq_pipeline_step_order"),) #every pipeline should have unique step orders (but different pipelines can have the same step order numbers)
    #table args expects a tuple so we add a , before the end
    
    id: Mapped[int]=mapped_column(primary_key=True)
    pipeline_id: Mapped[int]=mapped_column(ForeignKey("pipelines.id", ondelete="CASCADE"), index=True)
    step_type: Mapped[str]=mapped_column(String(50), nullable=False)
    step_order: Mapped[int]=mapped_column(Integer, nullable=False)
    config: Mapped[dict | None]=mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime]=mapped_column(server_default=func.now())
    is_active: Mapped[bool]=mapped_column(default=True, nullable=False)
    pipeline=relationship("Pipeline", back_populates="steps")