"""
UserUpload model — stores files uploaded by subscribers for real-API generation.
"""
import enum
import uuid
from sqlalchemy import Boolean, Column, String, DateTime, Integer, ForeignKey, Enum, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base


class UploadStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class UserUpload(Base):
    """
    File uploaded by a subscriber for use with a real AI generation call.

    Lifecycle:
      1. User POSTs file → record created (status=PENDING, file_url set)
      2. Generation is triggered → status=PROCESSING, task_id set
      3. Result available → status=COMPLETED, result_url / result_video_url set
      4. User downloads result (no watermark for subscribers)
    """
    __tablename__ = "user_uploads"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)

    # Upload metadata
    tool_type = Column(String(50), nullable=False, index=True)      # e.g. "background_removal"
    original_filename = Column(String(255), nullable=True)
    file_url = Column(String(500), nullable=False)                   # Stored path / URL of upload
    file_size = Column(Integer, nullable=True)                       # bytes
    content_type = Column(String(100), nullable=True)                # MIME type

    # Generation params
    prompt = Column(Text, nullable=True)
    selected_model = Column(String(100), nullable=True)              # Model chosen by user
    extra_params = Column(Text, nullable=True)                       # JSON string for extra params

    # Generation output
    status = Column(Enum(UploadStatus), default=UploadStatus.PENDING, nullable=False, index=True)
    task_id = Column(String(200), nullable=True)                     # External API task id
    result_url = Column(String(500), nullable=True)                  # Result image URL (no watermark)
    result_video_url = Column(String(500), nullable=True)            # Result video URL (no watermark)
    error_message = Column(Text, nullable=True)

    # Credits deducted for this generation
    credits_used = Column(Integer, default=0)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    user = relationship("User", foreign_keys=[user_id])
