from shared.db import Base
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from sqlalchemy import func, String

class Tenant(Base):
    __tablename__="tenants"

    id: Mapped[int]=mapped_column(primary_key=True)
    name: Mapped[str]=mapped_column(String(255),nullable=False)
    created_at: Mapped[datetime]=mapped_column(server_default=func.now())
    is_active: Mapped[bool]=mapped_column(default=True, nullable=False)

    pipelines=relationship("Pipeline", back_populates="tenant", cascade="all, delete-orphan")