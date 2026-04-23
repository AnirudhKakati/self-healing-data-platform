from shared.db import Base
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from sqlalchemy import ForeignKey, String, Text, func

class AgentRecommendation(Base):
    __tablename__="agent_recommendations"
    
    id: Mapped[int]=mapped_column(primary_key=True)
    tenant_id: Mapped[int]=mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    pipeline_id: Mapped[int]=mapped_column(ForeignKey("pipelines.id", ondelete="CASCADE"), index=True)
    run_id: Mapped[int]=mapped_column(ForeignKey("pipeline_runs.id", ondelete="CASCADE"), index=True)
    failure_classification: Mapped[str]=mapped_column(String(50), nullable=False) 
    recommended_action: Mapped[str]=mapped_column(String(50), nullable=False) #will convert to an ENUM later
    explanation: Mapped[str]=mapped_column(Text,nullable=False)
    status: Mapped[str]=mapped_column(String(50), default="pending", nullable=False) #will convert to an ENUM later
    created_at: Mapped[datetime]=mapped_column(server_default=func.now())
    updated_at: Mapped[datetime|None]=mapped_column(nullable=True)

    pipeline=relationship("Pipeline", back_populates="agent_recommendations")
    tenant=relationship("Tenant", back_populates="agent_recommendations")
    pipeline_run=relationship("PipelineRun", back_populates="agent_recommendations")
