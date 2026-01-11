"""
Workflow API - Prompt Chaining Generation Endpoints

This module exposes the workflow generator as REST API endpoints.
"""
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from enum import Enum

from app.config.demo_topics import (
    TopicDefinition,
    TopicCategory,
    OutputType,
    get_all_topics,
    get_topics_by_category,
    get_topic_by_id,
    CATEGORY_OUTPUT_MAP,
)
from app.services.workflow_generator import (
    get_workflow_generator,
    run_workflow,
    GenerationResult,
)

router = APIRouter(prefix="/workflow", tags=["Workflow"])


# =============================================================================
# Request/Response Models
# =============================================================================

class TopicSummary(BaseModel):
    """Summary of a topic for listing."""
    id: str
    category: str
    output_type: str
    subject: str
    mood: str
    tags: List[str]


class TopicDetail(BaseModel):
    """Detailed topic information."""
    id: str
    category: str
    output_type: str
    subject: str
    mood: str
    tags: List[str]
    image_prompt: str
    effect_prompt: Optional[str]
    language: str
    metadata: Dict[str, Any]


class GenerationRequest(BaseModel):
    """Request to generate content."""
    topic_id: Optional[str] = Field(None, description="Specific topic ID to generate")
    category: Optional[str] = Field(None, description="Category to generate all topics from")
    save_locally: bool = Field(True, description="Save generated files locally")


class GenerationResponse(BaseModel):
    """Response from generation."""
    success: bool
    topic_id: Optional[str] = None
    category: Optional[str] = None
    output_type: Optional[str] = None
    image_url: Optional[str] = None
    video_url: Optional[str] = None
    error: Optional[str] = None
    steps_completed: List[str] = []
    duration_seconds: float = 0.0
    metadata: Dict[str, Any] = {}


class BatchGenerationResponse(BaseModel):
    """Response from batch generation."""
    success: bool
    category: Optional[str] = None
    total: int
    succeeded: int
    failed: int
    results: List[GenerationResponse] = []


class CategoryInfo(BaseModel):
    """Information about a category."""
    id: str
    name: str
    output_type: str
    topic_count: int
    description: str


# =============================================================================
# API Endpoints
# =============================================================================

@router.get("/topics", response_model=List[TopicSummary])
async def list_topics(
    category: Optional[str] = None,
    output_type: Optional[str] = None
):
    """
    List all available topics.

    - **category**: Filter by category (product_video, interior_design, etc.)
    - **output_type**: Filter by output type (video, image)
    """
    topics = get_all_topics()

    # Filter by category
    if category:
        try:
            cat = TopicCategory(category)
            topics = [t for t in topics if t.category == cat]
        except ValueError:
            raise HTTPException(400, f"Invalid category: {category}")

    # Filter by output type
    if output_type:
        try:
            ot = OutputType(output_type)
            topics = [t for t in topics if t.output_type == ot]
        except ValueError:
            raise HTTPException(400, f"Invalid output_type: {output_type}")

    return [
        TopicSummary(
            id=t.id,
            category=t.category.value,
            output_type=t.output_type.value,
            subject=t.subject,
            mood=t.mood,
            tags=t.tags
        )
        for t in topics
    ]


@router.get("/topics/{topic_id}", response_model=TopicDetail)
async def get_topic(topic_id: str):
    """Get detailed information about a specific topic."""
    topic = get_topic_by_id(topic_id)
    if not topic:
        raise HTTPException(404, f"Topic not found: {topic_id}")

    return TopicDetail(
        id=topic.id,
        category=topic.category.value,
        output_type=topic.output_type.value,
        subject=topic.subject,
        mood=topic.mood,
        tags=topic.tags,
        image_prompt=topic.build_image_prompt(),
        effect_prompt=topic.build_effect_prompt() if topic.effect_prompt_template else None,
        language=topic.language,
        metadata=topic.metadata
    )


@router.get("/categories", response_model=List[CategoryInfo])
async def list_categories():
    """List all available categories with their info."""
    category_descriptions = {
        TopicCategory.PRODUCT_VIDEO: "Product showcase videos using T2I → I2V pipeline",
        TopicCategory.INTERIOR_DESIGN: "Interior design images using Gemini 2.5 Flash",
        TopicCategory.STYLE_TRANSFER: "Styled videos using T2I → I2V → V2V pipeline",
        TopicCategory.AVATAR: "Talking head videos using Pollo Avatar",
        TopicCategory.T2I_SHOWCASE: "Pattern and texture images using Leonardo",
    }

    result = []
    for cat in TopicCategory:
        topics = get_topics_by_category(cat)
        result.append(CategoryInfo(
            id=cat.value,
            name=cat.value.replace("_", " ").title(),
            output_type=CATEGORY_OUTPUT_MAP[cat].value,
            topic_count=len(topics),
            description=category_descriptions.get(cat, "")
        ))

    return result


@router.post("/generate", response_model=GenerationResponse)
async def generate_single(topic_id: str, save_locally: bool = True):
    """
    Generate content for a single topic.

    This runs the complete prompt chaining workflow:
    1. Build prompts from topic definition
    2. Route to appropriate generator based on category
    3. Chain to video generation if output_type is video
    4. Return result with URLs

    - **topic_id**: The topic ID to generate
    - **save_locally**: Whether to save files to static directory
    """
    topic = get_topic_by_id(topic_id)
    if not topic:
        raise HTTPException(404, f"Topic not found: {topic_id}")

    generator = get_workflow_generator()
    result = await generator.generate_from_topic(topic, save_locally)

    return GenerationResponse(
        success=result.success,
        topic_id=result.topic_id,
        category=result.category.value,
        output_type=result.output_type.value,
        image_url=result.image_url,
        video_url=result.video_url,
        error=result.error,
        steps_completed=result.steps_completed,
        duration_seconds=result.duration_seconds,
        metadata=result.metadata
    )


@router.post("/generate/category/{category}", response_model=BatchGenerationResponse)
async def generate_category(
    category: str,
    save_locally: bool = True,
    background_tasks: BackgroundTasks = None
):
    """
    Generate content for all topics in a category.

    - **category**: Category to generate (product_video, interior_design, etc.)
    - **save_locally**: Whether to save files to static directory

    Note: This can take a long time. For production, consider using background tasks.
    """
    try:
        cat = TopicCategory(category)
    except ValueError:
        raise HTTPException(400, f"Invalid category: {category}")

    generator = get_workflow_generator()
    results = await generator.generate_by_category(cat, save_locally)

    return BatchGenerationResponse(
        success=True,
        category=category,
        total=len(results),
        succeeded=sum(1 for r in results if r.success),
        failed=sum(1 for r in results if not r.success),
        results=[
            GenerationResponse(
                success=r.success,
                topic_id=r.topic_id,
                category=r.category.value,
                output_type=r.output_type.value,
                image_url=r.image_url,
                video_url=r.video_url,
                error=r.error,
                steps_completed=r.steps_completed,
                duration_seconds=r.duration_seconds,
                metadata=r.metadata
            )
            for r in results
        ]
    )


@router.get("/preview/{topic_id}")
async def preview_topic(topic_id: str):
    """
    Preview the prompts that would be generated for a topic.

    Useful for debugging and understanding the prompt chaining flow.
    """
    topic = get_topic_by_id(topic_id)
    if not topic:
        raise HTTPException(404, f"Topic not found: {topic_id}")

    return {
        "topic_id": topic.id,
        "category": topic.category.value,
        "output_type": topic.output_type.value,
        "flow": _get_flow_description(topic.category),
        "prompts": {
            "image_prompt": topic.build_image_prompt(),
            "effect_prompt": topic.build_effect_prompt() if topic.effect_prompt_template else None
        },
        "parameters": {
            "subject": topic.subject,
            "mood": topic.mood,
            "style_id": topic.style_id,
            "language": topic.language
        }
    }


def _get_flow_description(category: TopicCategory) -> str:
    """Get human-readable flow description for a category."""
    flows = {
        TopicCategory.PRODUCT_VIDEO: "Leonardo T2I → Pollo I2V",
        TopicCategory.INTERIOR_DESIGN: "Gemini 2.5 Flash Image T2I",
        TopicCategory.STYLE_TRANSFER: "Leonardo T2I → Pollo I2V → GoEnhance V2V",
        TopicCategory.AVATAR: "Pollo Avatar API",
        TopicCategory.T2I_SHOWCASE: "Leonardo Pattern T2I",
    }
    return flows.get(category, "Unknown")
