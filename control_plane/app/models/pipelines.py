from shared.db import Base
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from sqlalchemy import ForeignKey, String, Text, func

class Pipeline(Base):
    __tablename__="pipelines"

    id: Mapped[int]=mapped_column(primary_key=True) 
    tenant_id: Mapped[int]=mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    name: Mapped[str]=mapped_column(String(255),nullable=False)
    description: Mapped[str | None]=mapped_column(Text,nullable=True)
    created_at: Mapped[datetime]=mapped_column(server_default=func.now())
    is_active: Mapped[bool]=mapped_column(default=True, nullable=False)

    tenant=relationship("Tenant", back_populates="pipelines")
    steps=relationship("PipelineStep", back_populates="pipeline", cascade="all, delete-orphan")
    schedule=relationship("Schedule", back_populates="pipeline", uselist=False, cascade="all, delete-orphan") #one schedule belongs to one pipeline (so singular name)
    pipeline_runs=relationship("PipelineRun", back_populates="pipeline", cascade="all, delete-orphan")
    agent_recommendations=relationship("AgentRecommendation",back_populates="pipeline", cascade="all, delete-orphan")
    pipeline_circuit_breaker=relationship("PipelineCircuitBreaker", back_populates="pipeline", uselist=False, cascade="all, delete-orphan")