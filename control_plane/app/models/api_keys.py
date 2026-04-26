from shared.db import Base
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from sqlalchemy import ForeignKey, String, UniqueConstraint, func

class APIKey(Base):
    __tablename__="api_keys"
    __table_args__=(UniqueConstraint("tenant_id", "name", name="uq_tenant_key_name"),) #a tenant cannot have two api keys with the same name

    id: Mapped[int]=mapped_column(primary_key=True)
    tenant_id: Mapped[int]=mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)

    name: Mapped[str]=mapped_column(String(50), nullable=False)
    key_prefix: Mapped[str]=mapped_column(String(16), nullable=False) #small visible part of the key, useful for lookup/display
    key_hash: Mapped[str]=mapped_column(String(64), nullable=False, unique=True, index=True) # HMAC-SHA256 hex digest is 64 chars
    created_at: Mapped[datetime]=mapped_column(server_default=func.now())
    revoked_at: Mapped[datetime|None]=mapped_column(nullable=True)

    tenant=relationship("Tenant", back_populates="api_keys")