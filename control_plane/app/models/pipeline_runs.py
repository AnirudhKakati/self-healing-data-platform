from shared.db import Base
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from sqlalchemy import ForeignKey, String, Text, Integer, func

class PipelineRun(Base):
    __tablename__="pipeline_runs"

    id: Mapped[int]=mapped_column(primary_key=True)
    tenant_id: Mapped[int]=mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    pipeline_id: Mapped[int]=mapped_column(ForeignKey("pipelines.id", ondelete="CASCADE"), index=True)
    status: Mapped[str]=mapped_column(String(50), default="queued", nullable=False)
    created_at: Mapped[datetime]=mapped_column(server_default=func.now())
    started_at: Mapped[datetime|None]=mapped_column(nullable=True)
    updated_at: Mapped[datetime|None]=mapped_column(nullable=True)
    ended_at: Mapped[datetime|None]=mapped_column(nullable=True)
    error_type: Mapped[str|None]=mapped_column(String(50), nullable=True)
    error_message: Mapped[str|None]=mapped_column(Text,nullable=True)
    retry_count: Mapped[int]=mapped_column(Integer,default=0, nullable=False)


    pipeline=relationship("Pipeline", back_populates="pipeline_runs")
    tenant=relationship("Tenant", back_populates="pipeline_runs")
    agent_recommendations=relationship("AgentRecommendation",back_populates="pipeline_run", cascade="all, delete-orphan")