from shared.db import Base
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from sqlalchemy import ForeignKey, String, func

class Schedule(Base):
    __tablename__="schedules"

    id: Mapped[int]=mapped_column(primary_key=True) 
    pipeline_id: Mapped[int]=mapped_column(ForeignKey("pipelines.id", ondelete="CASCADE"), index=True, unique=True)
    cron_expression: Mapped[str]=mapped_column(String(100), nullable=False)
    timezone: Mapped[str]=mapped_column(String(100), nullable=False, default="UTC")
    created_at: Mapped[datetime]=mapped_column(server_default=func.now())
    is_active: Mapped[bool]=mapped_column(default=True, nullable=False)

    pipeline=relationship("Pipeline", back_populates="schedule") #one schedule belongs to one pipeline