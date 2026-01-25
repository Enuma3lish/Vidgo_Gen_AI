from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Enum, JSON
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

from app.core.database import Base
from app.models.material import ToolType

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
    
    # Input Data
    input_image_url = Column(String(500), nullable=True)  # Main input (product, model, room, photo)
    input_video_url = Column(String(500), nullable=True)  # Video input
    input_text = Column(String, nullable=True)            # Text input (script, prompt)
    input_params = Column(JSONB, default={})              # Config: prompt, style, settings
    
    # Output Data (No Watermark for Subscribers)
    result_image_url = Column(String(500), nullable=True)
    result_video_url = Column(String(500), nullable=True)
    result_metadata = Column(JSONB, default={})           # Extra generation info
    
    # Metadata
    credits_used = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    
    # Relationships
    user = relationship("User", back_populates="generations")
