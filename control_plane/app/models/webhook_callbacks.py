from shared.db import Base
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from sqlalchemy import ForeignKey, JSON, String, Integer, Text, func

class WebhookCallback(Base):
    __tablename__="webhook_callbacks"
    
    id: Mapped[int]=mapped_column(primary_key=True)
    tenant_id: Mapped[int]=mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    pipeline_id: Mapped[int]=mapped_column(ForeignKey("pipelines.id", ondelete="CASCADE"), index=True)
    run_id: Mapped[int]=mapped_column(ForeignKey("pipeline_runs.id", ondelete="CASCADE"), index=True)
    callback_url: Mapped[str]=mapped_column(Text, nullable=False)
    payload: Mapped[dict|None]=mapped_column(JSON, nullable=True)
    status: Mapped[str]=mapped_column(String(50), nullable=False)
    http_status_code: Mapped[int|None]=mapped_column(Integer, nullable=True)
    error_message: Mapped[str|None]=mapped_column(Text,nullable=True)
    created_at: Mapped[datetime]=mapped_column(server_default=func.now())

    tenant=relationship("Tenant", back_populates="webhook_callbacks")
    pipeline=relationship("Pipeline", back_populates="webhook_callbacks")   
    pipeline_run=relationship("PipelineRun", back_populates="webhook_callbacks")