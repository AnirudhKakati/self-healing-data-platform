from shared.db import Base
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from sqlalchemy import ForeignKey, String, Text, func, Integer

class PipelineCircuitBreaker(Base):
    __tablename__="pipeline_circuit_breakers"

    id: Mapped[int]=mapped_column(primary_key=True)
    tenant_id: Mapped[int]=mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    pipeline_id: Mapped[int]=mapped_column(ForeignKey("pipelines.id", ondelete="CASCADE"), index=True, unique=True)
    state: Mapped[str]=mapped_column(String(50), default="closed", nullable=False)
    failure_reason: Mapped[str|None]=mapped_column(Text,nullable=True)
    retry_after: Mapped[datetime|None]=mapped_column(nullable=True)
    created_at: Mapped[datetime]=mapped_column(server_default=func.now())
    updated_at: Mapped[datetime|None]=mapped_column(nullable=True)
    failure_count_threshold: Mapped[int]=mapped_column(Integer,default=3, nullable=False)
    failure_window_minutes: Mapped[int]=mapped_column(Integer,default=60, nullable=False)

    pipeline=relationship("Pipeline", back_populates="pipeline_circuit_breaker")
    tenant=relationship("Tenant", back_populates="pipeline_circuit_breakers")