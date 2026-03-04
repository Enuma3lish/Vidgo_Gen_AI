from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Enum, Boolean
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime, timezone, timedelta
import uuid

from app.core.database import Base
from app.models.material import ToolType

# Media retention period: 14 days (2 weeks)
MEDIA_RETENTION_DAYS = 14


class UserGeneration(Base):
    __tablename__ = "user_generations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)

    # Classification
    tool_type = Column(
        Enum(ToolType, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        index=True
    )

    # Input Data (kept permanently for generation history)
    input_image_url = Column(String(500), nullable=True)   # Main input (product, model, room, photo)
    input_video_url = Column(String(500), nullable=True)   # Video input
    input_text = Column(String, nullable=True)             # Text input (script, prompt)
    input_params = Column(JSONB, default={})               # Config: prompt, style, model, settings

    # Output Data (cleared after 14 days, no watermark for subscribers)
    result_image_url = Column(String(500), nullable=True)
    result_video_url = Column(String(500), nullable=True)
    result_metadata = Column(JSONB, default={})            # Extra generation info (kept permanently)

    # Metadata
    credits_used = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    # ── Media Expiry (14-day retention) ──────────────────────────────────────
    # After expires_at, result_image_url and result_video_url are cleared.
    # The generation record itself (tool_type, input_params, credits_used, etc.)
    # is kept permanently so users can see their creation history.
    expires_at = Column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        comment="Media files expire 14 days after creation; record kept permanently"
    )
    media_expired = Column(
        Boolean,
        default=False,
        nullable=False,
        comment="True when media URLs have been cleared after expiry"
    )

    # Relationships
    user = relationship("User", back_populates="generations")

    # ── Helper Methods ────────────────────────────────────────────────────────

    def set_expiry(self):
        """Set expires_at to 14 days from now (call when generation is created)."""
        self.expires_at = datetime.now(timezone.utc) + timedelta(days=MEDIA_RETENTION_DAYS)

    @property
    def is_media_expired(self) -> bool:
        """Check if media has expired (either flagged or past expiry date)."""
        if self.media_expired:
            return True
        if self.expires_at and datetime.now(timezone.utc) > self.expires_at:
            return True
        return False

    @property
    def days_until_expiry(self) -> int | None:
        """
        Days remaining until media expires.
        Returns None if no expiry set, 0 if already expired.
        """
        if not self.expires_at:
            return None
        if self.is_media_expired:
            return 0
        delta = self.expires_at - datetime.now(timezone.utc)
        return max(0, delta.days)

    @property
    def hours_until_expiry(self) -> int | None:
        """
        Hours remaining until media expires (useful for last 24h warning).
        Returns None if no expiry set, 0 if already expired.
        """
        if not self.expires_at:
            return None
        if self.is_media_expired:
            return 0
        delta = self.expires_at - datetime.now(timezone.utc)
        total_hours = int(delta.total_seconds() / 3600)
        return max(0, total_hours)
