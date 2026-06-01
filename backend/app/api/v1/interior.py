"""
VidGo Interior Design API Endpoints.

AI-powered interior design using Gemini 2.5 Flash Image:
- Room Redesign (Image + Text → Image)
- Design Generation (Text → Image)
- Style Fusion (Multi-image → Image)
- Iterative Editing (Multi-turn refinement)
- Style Transfer (Apply design style)

Access: All users (demo) or Subscribers (full features)
"""
import logging
import uuid
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_current_active_user, get_current_user_optional, is_subscribed_user
from app.core.upload_validation import ROOM_REDESIGN_IMAGE_DIMENSION_RULES, validate_uploaded_content
from app.models.user import User
from app.models.user_generation import UserGeneration
from app.models.material import ToolType
from app.providers.provider_router import TaskType, get_provider_router
from app.services.interior_design_service import (
    get_interior_design_service,
    DESIGN_STYLES,
    ROOM_TYPES
)
from app.services.interior_growth_service import get_interior_growth_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/interior", tags=["interior"])

# ── Floor-plan → 3D-growth-video pipeline pricing ──────────────────────────
# Fallback credit costs; a ServicePricing row keyed by the same service_type
# overrides these per the deduction-firewall pattern in
# tools._check_and_deduct_credits, so ops can retune without a redeploy.
#   Tier "video"     = Gemini analysis + 3D render + Kling 3.0/Omni growth video
#   Tier "video_3d"  = + Trellis2 interactive GLB model
GROWTH_VIDEO_CREDITS = 800
GROWTH_VIDEO_3D_CREDITS = 950
GROWTH_3D_DELTA = GROWTH_VIDEO_3D_CREDITS - GROWTH_VIDEO_CREDITS  # refunded if 3D add-on yields no model


# ============ Schemas ============

class StyleInfo(BaseModel):
    id: str
    name: str
    name_zh: str
    description: str


class RoomTypeInfo(BaseModel):
    id: str
    name: str
    name_zh: str


class RedesignRequest(BaseModel):
    room_image_url: Optional[str] = Field(None, description="URL of room image")
    room_image_base64: Optional[str] = Field(None, description="Base64-encoded room image")
    prompt: str = Field(..., description="Description of desired changes")
    style_id: Optional[str] = Field(None, description="Design style to apply")
    room_type: Optional[str] = Field(None, description="Type of room for context")
    keep_layout: bool = Field(True, description="Preserve window/door layout")
    space_kind: str = Field(
        "interior",
        description="'interior' (default) or 'exterior'. Drives which catalog (INTERIOR_STYLES vs EXTERIOR_STYLES) backs `style_id`.",
    )


class GenerateRequest(BaseModel):
    prompt: str = Field(..., description="Text description of desired room design")
    style_id: Optional[str] = Field(None, description="Design style to apply")
    room_type: Optional[str] = Field(None, description="Type of room to generate")


class FusionRequest(BaseModel):
    room_image_url: Optional[str] = Field(None, description="URL of room image")
    room_image_base64: Optional[str] = Field(None, description="Base64-encoded room image")
    style_image_url: Optional[str] = Field(None, description="URL of style reference")
    style_image_base64: Optional[str] = Field(None, description="Base64-encoded style reference")
    prompt: str = Field("", description="Additional instructions")


class IterativeEditRequest(BaseModel):
    conversation_id: Optional[str] = Field(None, description="Conversation ID for continuing edits")
    prompt: str = Field(..., description="Edit instruction")
    image_url: Optional[str] = Field(None, description="URL of image to edit")
    image_base64: Optional[str] = Field(None, description="Base64-encoded image to edit")


class StyleTransferRequest(BaseModel):
    room_image_url: Optional[str] = Field(None, description="URL of room image")
    room_image_base64: Optional[str] = Field(None, description="Base64-encoded room image")
    style_id: str = Field(..., description="Design style ID to apply")


class DesignResponse(BaseModel):
    success: bool
    image_url: Optional[str] = None
    description: Optional[str] = None
    conversation_id: Optional[str] = None
    turn_count: Optional[int] = None
    error: Optional[str] = None
    space_kind: Optional[str] = None  # 'interior' | 'exterior', echoed back
    # 2026-05-18 — image-understanding fusion result. Lets the frontend
    # show "we see: ..." alongside the result and warn the user when
    # their text prompt was suppressed because it contradicted the image.
    vision_summary: Optional[str] = None
    user_prompt_used: Optional[bool] = None
    prompt_gap_reason: Optional[str] = None


class Generate3DRequest(BaseModel):
    image_url: str = Field(..., description="Public URL of the room/floor-plan image to convert")
    texture_size: int = Field(1024, ge=512, le=2048, description="Texture size for the GLB model")
    mesh_simplify: float = Field(0.95, ge=0.5, le=1.0, description="Mesh simplification ratio")
    model_version: str = Field("v1", description="Trellis model version: 'v1' (fast/cheap) or 'v2' (high quality)")


class Generate3DFromFloorplanRequest(BaseModel):
    image_url: str = Field(..., description="Public URL of the architectural floor plan image")
    style_id: Optional[str] = Field(None, description="Optional design style to apply when rendering the interior")
    room_type: Optional[str] = Field("living_room", description="Room type hint for the photorealistic render")
    prompt: Optional[str] = Field(None, description="Optional extra description (materials, mood, dimensions)")
    model_version: str = Field("v2", description="Trellis model version for the final mesh, default high quality")


class Generate3DResponse(BaseModel):
    success: bool
    model_url: Optional[str] = None
    preview_image_url: Optional[str] = None
    preview_video_url: Optional[str] = None
    task_id: Optional[str] = None
    error: Optional[str] = None


class FloorplanToVideoRequest(BaseModel):
    """Floor-plan → 3D-growth-video pipeline request."""
    image_url: str = Field(..., description="Public URL of the 2D architectural floor plan image.")
    style_id: Optional[str] = Field("modern_minimalist", description="Interior design style (see GET /interior/styles).")
    room_type: Optional[str] = Field("living_room", description="Primary room type hint (see GET /interior/room-types).")
    prompt: Optional[str] = Field(None, description="Optional extra request (materials, mood, dimensions).")
    result_tier: str = Field(
        "video",
        pattern="^(video|video_3d)$",
        description="What the user wants: 'video' = render + Kling 3.0 growth animation; "
                    "'video_3d' = also reconstruct an interactive 3D model (.glb).",
    )
    duration: int = Field(5, ge=5, le=10, description="Growth-video length in seconds (5 or 10).")
    model_version: str = Field("v2", description="Trellis version for the 3D model when result_tier='video_3d'.")
    language: Optional[str] = Field("en", description="Language for the Gemini analysis ('en' | 'zh').")


class FloorplanToVideoResponse(BaseModel):
    success: bool
    result_tier: str
    render_image_url: Optional[str] = None       # photorealistic 3D render (video end frame)
    video_url: Optional[str] = None              # Kling 3.0 growth animation MP4
    model_url: Optional[str] = None              # interactive .glb (video_3d tier)
    model_preview_video_url: Optional[str] = None
    render_prompt: Optional[str] = None
    video_motion_prompt: Optional[str] = None
    structure_notes: Optional[str] = None
    credits_used: int = 0
    steps: Optional[Dict[str, Any]] = None       # per-stage status map
    stage: Optional[str] = None                  # failing stage on error
    model_3d_error: Optional[str] = None         # set when 3D add-on failed but video succeeded
    error: Optional[str] = None


# ============ Endpoints ============

@router.get("/styles", response_model=List[StyleInfo])
async def get_design_styles():
    """
    Get available interior design styles.

    Styles include:
    - Modern Minimalist
    - Scandinavian
    - Japanese Zen
    - Industrial
    - Bohemian
    - Mediterranean
    - Art Deco
    - Mid-Century Modern
    - Coastal
    - Farmhouse
    """
    return [
        StyleInfo(
            id=style["id"],
            name=style["name"],
            name_zh=style["name_zh"],
            description=style["description"]
        )
        for style in DESIGN_STYLES.values()
    ]


@router.get("/room-types", response_model=List[RoomTypeInfo])
async def get_room_types():
    """
    Get available room types for context.

    Types include:
    - Living Room
    - Bedroom
    - Kitchen
    - Bathroom
    - Dining Room
    - Home Office
    - Balcony
    """
    return [
        RoomTypeInfo(
            id=room["id"],
            name=room["name"],
            name_zh=room["name_zh"]
        )
        for room in ROOM_TYPES.values()
    ]


@router.post("/redesign", response_model=DesignResponse)
async def redesign_room(
    request: RedesignRequest,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db)
):
    """
    Redesign a room based on image and text prompt.

    **Image + Text -> Image**

    Upload a room photo and describe the changes you want.
    The AI will generate a redesigned version of the room.

    Examples:
    - "Change the sofa to grey"
    - "Add indoor plants and modern lighting"
    - "Make it more minimalist with neutral colors"
    """
    if not request.room_image_url and not request.room_image_base64:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Room image is required (URL or base64)"
        )

    provider_router = get_provider_router()
    user_tier = "paid" if is_subscribed_user(current_user) else "starter"

    # Build image URL — upload base64 to GCS if needed
    image_url = request.room_image_url
    if not image_url and request.room_image_base64:
        try:
            from app.services.gcs_storage_service import get_gcs_storage
            import base64, uuid
            gcs = get_gcs_storage()
            if gcs.enabled:
                raw = base64.b64decode(request.room_image_base64)
                blob = f"uploads/interior/{uuid.uuid4().hex}.jpg"
                image_url = gcs.upload_public(raw, blob, "image/jpeg")
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Failed to process image: {exc}")

    if not image_url:
        raise HTTPException(status_code=400, detail="No image URL could be resolved")

    # 2026-05-18 — image-understanding pass to fuse user prompt with
    # what's actually in the photo. Drops the user's text when it
    # contradicts the image (e.g. "redesign as a kitchen" on a bedroom
    # photo). Fail-open: any Gemini error returns user's original prompt.
    from app.services.image_understanding_service import (
        get_image_understanding_service,
    )

    fusion = await get_image_understanding_service().describe_and_fuse(
        image_url=image_url,
        user_prompt=request.prompt,
        tool_context=f"room_redesign:{request.space_kind}",
        language="zh-TW",
    )

    # 2026-05-18 — hard "no people" constraint for every interior render.
    # Architectural / staging renders must show the space, not occupants.
    no_people_clause = (
        " Empty room: NO people, NO humans, NO faces, NO hands, NO pets, "
        "NO photographer in frame, NO occupants — render the space only, "
        "as a clean unpopulated architectural proposal."
    )
    routed_prompt = f"{fusion.fused_prompt}{no_people_clause}".strip()

    try:
        result = await provider_router.route(
            TaskType.INTERIOR,
            {
                "image_url": image_url,
                "prompt": routed_prompt,
                "style": request.style_id or "modern",
                "room_type": request.room_type or "living_room",
            },
            user_tier=user_tier,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Room redesign failed: {exc}"
        )

    if not result.get("success"):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=result.get("error", "Failed to redesign room")
        )

    output = result.get("output") or {}
    return DesignResponse(
        success=True,
        image_url=output.get("image_url") or result.get("image_url"),
        description=result.get("description") or "Room redesign complete",
        vision_summary=fusion.image_summary or None,
        user_prompt_used=fusion.used_user_prompt,
        prompt_gap_reason=fusion.gap_reason,
    )


@router.post("/generate", response_model=DesignResponse)
async def generate_design(
    request: GenerateRequest,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db)
):
    """
    Generate interior design from text description only.

    **Text -> Image**

    Describe the room you want and the AI will generate it.

    Examples:
    - "Nordic style living room with wood floor and white sofa"
    - "Modern minimalist bedroom with floor-to-ceiling windows"
    - "Cozy Japanese zen study with tatami and low table"
    """
    service = get_interior_design_service()

    result = await service.generate_design(
        prompt=request.prompt,
        style_id=request.style_id,
        room_type=request.room_type
    )

    if not result.get("success"):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=result.get("error", "Failed to generate design")
        )

    return DesignResponse(
        success=True,
        image_url=result.get("image_url"),
        description=result.get("description")
    )


@router.post("/fusion", response_model=DesignResponse)
async def fusion_design(
    request: FusionRequest,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db)
):
    """
    Combine room photo with style reference image.

    **Multi-image Fusion: Room + Style Reference -> Fused Result**

    Upload your room photo and a style reference image.
    The AI will apply the style to your room while keeping the layout.
    """
    if not (request.room_image_url or request.room_image_base64):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Room image is required"
        )

    if not (request.style_image_url or request.style_image_base64):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Style reference image is required"
        )

    service = get_interior_design_service()

    result = await service.fusion_design(
        room_image_base64=request.room_image_base64,
        room_image_url=request.room_image_url,
        style_image_base64=request.style_image_base64,
        style_image_url=request.style_image_url,
        prompt=request.prompt
    )

    if not result.get("success"):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=result.get("error", "Failed to create fusion design")
        )

    return DesignResponse(
        success=True,
        image_url=result.get("image_url"),
        description=result.get("description")
    )


@router.post("/edit", response_model=DesignResponse)
async def iterative_edit(
    request: IterativeEditRequest,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db)
):
    """
    Continue editing a design through multi-turn conversation.

    **Iterative Editing: Continuous refinement through dialogue**

    Start a new conversation by providing an image.
    Continue the conversation by using the returned conversation_id.

    Examples:
    - Turn 1: "Change the wall color to sage green"
    - Turn 2: "Add a bookshelf on the left wall"
    - Turn 3: "Replace the floor with oak hardwood"
    """
    # Generate conversation ID if not provided
    conversation_id = request.conversation_id or str(uuid.uuid4())

    # First turn requires an image
    if not request.conversation_id and not (request.image_url or request.image_base64):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Image is required for the first edit. Provide image_url or image_base64."
        )

    service = get_interior_design_service()

    result = await service.iterative_edit(
        conversation_id=conversation_id,
        prompt=request.prompt,
        image_base64=request.image_base64,
        image_url=request.image_url
    )

    if not result.get("success"):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=result.get("error", "Failed to apply edit")
        )

    return DesignResponse(
        success=True,
        image_url=result.get("image_url"),
        description=result.get("description"),
        conversation_id=result.get("conversation_id", conversation_id),
        turn_count=result.get("turn_count")
    )


@router.delete("/edit/{conversation_id}")
async def clear_conversation(
    conversation_id: str,
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """
    Clear conversation history for iterative editing.

    Use this to start fresh without accumulated context.
    """
    service = get_interior_design_service()
    cleared = service.clear_conversation(conversation_id)

    return {
        "success": True,
        "cleared": cleared,
        "conversation_id": conversation_id
    }


@router.post("/style-transfer", response_model=DesignResponse)
async def style_transfer(
    request: StyleTransferRequest,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db)
):
    """
    Apply a specific design style to a room image.

    **Style Transfer: Room + Style -> Styled Room**

    Upload a room photo and select a design style to apply.

    Available styles:
    - modern_minimalist: Clean lines, neutral colors
    - scandinavian: Light wood, white walls, cozy
    - japanese: Zen simplicity, natural materials
    - industrial: Exposed brick, metal accents
    - bohemian: Eclectic patterns, rich colors
    - mediterranean: Terracotta, blue accents
    - art_deco: Geometric patterns, glamour
    - mid_century_modern: Retro furniture, bold colors
    - coastal: Blue tones, nautical elements
    - farmhouse: Rustic wood, vintage charm
    """
    if not request.room_image_url and not request.room_image_base64:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Room image is required"
        )

    if request.style_id not in DESIGN_STYLES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown style: {request.style_id}. Available: {list(DESIGN_STYLES.keys())}"
        )

    service = get_interior_design_service()

    result = await service.transfer_style(
        room_image_base64=request.room_image_base64,
        room_image_url=request.room_image_url,
        style_id=request.style_id
    )

    if not result.get("success"):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=result.get("error", "Failed to apply style transfer")
        )

    return DesignResponse(
        success=True,
        image_url=result.get("image_url"),
        description=result.get("description")
    )


@router.post("/3d-model", response_model=Generate3DResponse)
async def generate_3d_model(
    request: Generate3DRequest,
    current_user: User = Depends(get_current_active_user),
):
    """
    Convert a 2D room image or floor plan into an interactive GLB model.

    This is a subscriber-only endpoint backed by PiAPI Trellis. The frontend
    uploads local files first so Trellis receives a public image URL.
    """
    if not is_subscribed_user(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="3D model generation requires an active subscription"
        )

    if not request.image_url.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Image URL is required"
        )

    provider_router = get_provider_router()
    try:
        result = await provider_router.route(
            TaskType.INTERIOR_3D,
            {
                "image_url": request.image_url,
                "texture_size": request.texture_size,
                "mesh_simplify": request.mesh_simplify,
                "model_version": request.model_version,
            },
            user_tier="paid",
        )
    except Exception as exc:
        # provider_router.route already wraps the upstream failure in a
        # user-friendly message via _get_user_friendly_error. Prefixing it
        # again with "Failed to generate 3D model:" doubles the noise and
        # buries the actionable text ("Service credits are currently
        # depleted." / "3D model generation is temporarily unavailable.")
        # under boilerplate, so we surface the inner message as-is.
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc) or "3D model generation failed."
        ) from exc

    output = result.get("output") or {}
    model_url = output.get("model_url") or output.get("model_file") or output.get("url")
    if not model_url:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="3D provider completed without returning a model URL"
        )

    return Generate3DResponse(
        success=True,
        model_url=model_url,
        preview_image_url=output.get("image_url") or output.get("no_background_image"),
        preview_video_url=output.get("video_url") or output.get("combined_video"),
        task_id=result.get("task_id"),
    )


@router.post("/3d-from-floorplan", response_model=Generate3DResponse)
async def generate_3d_from_floorplan(
    request: Generate3DFromFloorplanRequest,
    current_user: User = Depends(get_current_active_user),
):
    """
    Two-stage Floor-Plan -> 3D pipeline (subscribers + superusers).

    Stage 1: Gemini 2.5 Flash Image renders a photorealistic isometric
    interior from the user's architectural floor plan + dimensions.
    Stage 2: PiAPI Trellis2 reconstructs the rendered image into a GLB mesh.
    """
    if not is_subscribed_user(current_user) and not getattr(current_user, "is_superuser", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Floor-plan to 3D requires an active subscription"
        )

    if not request.image_url.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Floor plan image URL is required"
        )

    # ---- Stage 1: PiAPI renders a photorealistic interior from the floor plan ----
    from app.services.interior_design_service import DESIGN_STYLES, ROOM_TYPES

    style_suffix = ""
    if request.style_id and request.style_id in DESIGN_STYLES:
        style_suffix = DESIGN_STYLES[request.style_id]["prompt_suffix"]

    room_hint = ""
    if request.room_type and request.room_type in ROOM_TYPES:
        room_hint = f"{ROOM_TYPES[request.room_type]['context']}, "

    floorplan_prompt = (
        f"Photorealistic interior architectural visualization rendered from a 2D floor plan. "
        f"{room_hint}"
        f"Isometric bird's-eye perspective, 2.8m walls, realistic materials, soft natural daylight. "
        f"No people, no dimension labels. "
        f"{style_suffix} "
        f"{(request.prompt or '').strip()}"
    ).strip()

    provider_router = get_provider_router()
    try:
        stage1 = await provider_router.route(
            TaskType.INTERIOR,
            {
                "image_url": request.image_url,
                "prompt": floorplan_prompt,
                "style": request.style_id or "modern_minimalist",
                "preserve_structure": True,
            },
            user_tier="paid",
        )
    except Exception as exc:
        # See note on /3d-model — provider_router already produces a user-
        # friendly message. Surface it directly so the caller sees the real
        # reason (e.g. credit depletion) instead of generic prose.
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc) or "Floor-plan interior render failed."
        ) from exc

    rendered_url = (
        stage1.get("image_url")
        or stage1.get("output_url")
        or (stage1.get("output", {}) or {}).get("image_url")
    )
    if not rendered_url:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Floor-plan render returned no image: {stage1.get('error', 'unknown')}"
        )
    # ---- Stage 2: Trellis2 reconstructs the rendered image into a GLB ----
    provider_router = get_provider_router()
    try:
        result = await provider_router.route(
            TaskType.INTERIOR_3D,
            {
                "image_url": rendered_url,
                "model_version": request.model_version or "v2",
            },
            user_tier="paid",
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc) or "3D reconstruction failed after floor-plan render."
        ) from exc

    output = result.get("output") or {}
    model_url = output.get("model_url") or output.get("model_file") or output.get("url")
    if not model_url:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="3D provider completed without returning a model URL"
        )

    return Generate3DResponse(
        success=True,
        model_url=model_url,
        preview_image_url=rendered_url,
        preview_video_url=output.get("video_url") or output.get("combined_video"),
        task_id=result.get("task_id"),
    )


@router.get("/floorplan-options")
async def floorplan_to_video_options():
    """Result tiers + credit costs + styles for the floor-plan growth pipeline.

    Lets the frontend render the "what result do you want?" picker. Credit
    costs shown are the fallback constants; the live charge follows any
    ServicePricing override for the same service_type.
    """
    return {
        "tiers": [
            {
                "id": "video",
                "name": "Growth Video",
                "name_zh": "平面圖長出房間影片",
                "description": "Gemini analyses your floor plan, renders a photorealistic 3D interior, "
                               "then Kling 3.0 animates the 2D plan growing into the finished room (MP4 + render image).",
                "service_type": "interior_growth_video",
                "credits": GROWTH_VIDEO_CREDITS,
                "outputs": ["render_image", "growth_video"],
            },
            {
                "id": "video_3d",
                "name": "Growth Video + 3D Model",
                "name_zh": "成長影片 + 3D 模型",
                "description": "Everything in Growth Video, plus a rotatable interactive 3D model (.glb) "
                               "reconstructed from the rendered room.",
                "service_type": "interior_growth_video_3d",
                "credits": GROWTH_VIDEO_3D_CREDITS,
                "outputs": ["render_image", "growth_video", "model_3d"],
            },
        ],
        "video_engine": "kling_3.0_omni",
        "styles": [
            {"id": s["id"], "name": s["name"], "name_zh": s["name_zh"]}
            for s in DESIGN_STYLES.values()
        ],
        "room_types": [
            {"id": r["id"], "name": r["name"], "name_zh": r["name_zh"]}
            for r in ROOM_TYPES.values()
        ],
    }


@router.post("/floorplan-to-video")
async def floorplan_to_video(
    request: FloorplanToVideoRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Floor-plan → "grows into a 3D room" video pipeline (subscribers + superusers).

    Gemini Vision → Imagen/Gemini render → Kling 3.0/Omni first→last-frame growth
    video → (optional) Trellis2 interactive 3D model. The user picks how far the
    pipeline runs via ``result_tier``; credits are charged per tier and refunded
    on failure (and partially refunded if a requested 3D model can't be built).

    The pipeline can run 10-20 min (Kling 3.0 + Trellis), so the long work is
    streamed behind a 25 s keep-alive heartbeat — the same mechanism /short-video
    uses to survive Cloudflare / GCLB / Cloud Run idle-connection timeouts. Auth
    and validation are checked up front so they still return real HTTP statuses;
    the final JSON body matches FloorplanToVideoResponse (it has leading-whitespace
    that JSON.parse / httpx .json() ignore).
    """
    # Fast pre-checks BEFORE streaming so genuine 4xx statuses are preserved.
    if not is_subscribed_user(current_user) and not getattr(current_user, "is_superuser", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Floor-plan growth video requires an active subscription",
        )
    if not request.image_url.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Floor plan image URL is required")

    async def _work() -> Dict[str, Any]:
        resp = await _floorplan_to_video_inner(request, current_user, db)
        return resp.model_dump() if hasattr(resp, "model_dump") else resp

    from app.api.v1.tools import _stream_with_heartbeat
    return _stream_with_heartbeat(_work)


async def _floorplan_to_video_inner(
    request: "FloorplanToVideoRequest",
    current_user: User,
    db: AsyncSession,
) -> FloorplanToVideoResponse:
    """Run the floor-plan growth pipeline (credits + orchestration + record).
    Returns a FloorplanToVideoResponse; the caller streams it with heartbeats.
    """
    include_3d = request.result_tier == "video_3d"
    service_type = "interior_growth_video_3d" if include_3d else "interior_growth_video"
    cost = GROWTH_VIDEO_3D_CREDITS if include_3d else GROWTH_VIDEO_CREDITS
    is_admin = bool(getattr(current_user, "is_superuser", False))

    # Credit deduction reuses the platform's deduction firewall (admins bypass,
    # ServicePricing overrides the fallback `cost`). Imported lazily to avoid a
    # tools.py ↔ interior.py circular import at module load.
    from app.api.v1.tools import _check_and_deduct_credits, _refund_credits

    ok, err = await _check_and_deduct_credits(db, current_user, cost, service_type)
    if not ok:
        return FloorplanToVideoResponse(success=False, result_tier=request.result_tier, error=err)

    try:
        result = await get_interior_growth_service().run(
            floorplan_url=request.image_url,
            style_id=request.style_id,
            room_type=request.room_type,
            extra_prompt=request.prompt or "",
            include_3d=include_3d,
            duration=request.duration,
            model_version=request.model_version,
            language=request.language or "en",
        )
    except Exception as exc:
        await _refund_credits(db, current_user, cost, service_type)
        logger.error("floorplan-to-video pipeline raised: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc) or "Floor-plan growth pipeline failed",
        ) from exc

    if not result.get("success"):
        await _refund_credits(db, current_user, cost, service_type)
        return FloorplanToVideoResponse(
            success=False,
            result_tier=request.result_tier,
            render_image_url=result.get("render_image_url"),
            stage=result.get("stage"),
            steps=result.get("steps"),
            error=result.get("error"),
        )

    credits_used = 0 if is_admin else cost
    # Partial refund: the user paid for a 3D model that couldn't be produced.
    if include_3d and not result.get("model_url") and not is_admin:
        await _refund_credits(db, current_user, GROWTH_3D_DELTA, service_type)
        credits_used = cost - GROWTH_3D_DELTA

    prompts = result.get("prompts") or {}

    # Best-effort history record — never break the response on a persistence error.
    try:
        user_gen = UserGeneration(
            user_id=current_user.id,
            tool_type=ToolType.ROOM_REDESIGN,
            input_image_url=request.image_url,
            input_params={
                "pipeline": "floorplan_to_video",
                "result_tier": request.result_tier,
                "style_id": request.style_id,
                "room_type": request.room_type,
                "video_engine": "kling_3.0_omni",
            },
            input_text=prompts.get("video_motion_prompt"),
            result_image_url=result.get("render_image_url"),
            result_video_url=result.get("video_url"),
            result_metadata={
                "model_url": result.get("model_url"),
                "model_preview_video_url": result.get("model_preview_video_url"),
                "render_prompt": prompts.get("render_prompt"),
                "video_motion_prompt": prompts.get("video_motion_prompt"),
                "structure_notes": prompts.get("structure_notes"),
                "steps": result.get("steps"),
            },
            credits_used=credits_used,
        )
        if hasattr(user_gen, "set_expiry"):
            user_gen.set_expiry()
        db.add(user_gen)
        await db.commit()
    except Exception as exc:  # noqa: BLE001
        logger.warning("floorplan-to-video: generation record skipped: %s", exc)
        try:
            await db.rollback()
        except Exception:  # noqa: BLE001
            pass

    return FloorplanToVideoResponse(
        success=True,
        result_tier=request.result_tier,
        render_image_url=result.get("render_image_url"),
        video_url=result.get("video_url"),
        model_url=result.get("model_url"),
        model_preview_video_url=result.get("model_preview_video_url"),
        render_prompt=prompts.get("render_prompt"),
        video_motion_prompt=prompts.get("video_motion_prompt"),
        structure_notes=prompts.get("structure_notes"),
        credits_used=credits_used,
        steps=result.get("steps"),
        model_3d_error=result.get("model_3d_error"),
    )


# ============ Demo Endpoint (No Auth Required) ============

@router.post("/demo/redesign", response_model=DesignResponse)
async def demo_redesign(
    # 2026-05-26: made `prompt` optional. The endpoint composes the final
    # prompt from style preset + lighting + material chips downstream, so
    # the user's free-text addition is purely additive. Previously this
    # was Form(...) required, which made the redesign / stage flows on
    # /tools/room-redesign 422 with the cryptic
    #   [{type:"missing", loc:["body","prompt"], input:null}]
    # whenever the user picked a style and clicked Generate without
    # typing anything extra. Now: empty string is accepted; the style
    # preset alone produces a usable render.
    prompt: str = Form("", description="Optional extra description of desired changes; empty is fine when a style preset is selected."),
    style_id: Optional[str] = Form(None, description="Design style to apply"),
    room_type: Optional[str] = Form(None, description="Type of room"),
    image: UploadFile = File(..., description="Room image file"),
    # 2026-05-18 — ReRoom-inspired modifiers. Mirror tools.py:RoomRedesignRequest
    # so the demo upload path supports the same enhancements as the
    # URL-based subscriber endpoint.
    space_kind: Optional[str] = Form("interior", description="interior | exterior | commercial"),
    mode: Optional[str] = Form("redesign", description="redesign | stage (AI Virtual Staging on an empty room)"),
    lighting_tone: Optional[str] = Form(None, description="daylight | warm_evening | dramatic_spotlight | golden_hour | moody"),
    material_accent: Optional[str] = Form(None, description="wood | marble | concrete | linen | brass | leather | terrazzo"),
):
    """
    Demo endpoint for room redesign (no authentication required).

    Upload a room image and describe the changes you want.
    Limited to demo usage.
    """
    import base64

    # Read + auto-normalize the image so iPhone HEIC photos, oversize
    # panoramas, and tiny screenshots all succeed instead of 422-ing the
    # user at the validator. Falls back to strict validation only when
    # the bytes aren't a decodable image at all.
    contents = await image.read()
    try:
        from app.services.image_normalize_service import normalize_uploaded_image

        normalized = normalize_uploaded_image(
            contents,
            rules=ROOM_REDESIGN_IMAGE_DIMENSION_RULES,
            max_bytes=20 * 1024 * 1024,
        )
        contents = normalized.bytes
    except HTTPException:
        # Re-raise validation errors verbatim so the user sees the actual
        # reason instead of a generic 422.
        raise
    image_base64 = base64.b64encode(contents).decode()

    # Compose the final prompt: caller text + AI-Staging cue + lighting +
    # material accent. Same clauses as tools.py so the two endpoints
    # produce the same flavor of output for the same chip combination.
    LIGHTING_CLAUSES = {
        "daylight":            " Lit by soft cool natural daylight from large windows; balanced exposure, no harsh shadows.",
        "warm_evening":        " Warm 2700K evening interior lighting from layered lamps; cozy atmospheric ambience.",
        "dramatic_spotlight":  " Dramatic directional spotlighting from above; bold shadows and high contrast.",
        "golden_hour":         " Late-golden-hour sunlight raking across surfaces; warm amber highlights, long soft shadows.",
        "moody":               " Moody low-key lighting with deep shadow play; cinematic and atmospheric.",
    }
    MATERIAL_CLAUSES = {
        "wood":      " Dominant material is warm natural oak / walnut wood across floors, ceilings, and feature walls.",
        "marble":    " Dominant material is veined Calacatta or Carrara marble across counters and feature surfaces.",
        "concrete":  " Dominant material is polished pigmented concrete across floors, walls, and select furnishings.",
        "linen":     " Dominant material is natural unbleached linen across upholstery, drapery, and soft furnishings.",
        "brass":     " Brass and bronze accents throughout: hardware, lighting, frames, and select decor pieces.",
        "leather":   " Dominant material is rich saddle or oxblood leather across major upholstered pieces.",
        "terrazzo":  " Terrazzo with mixed-color aggregate across floors and select surfaces; soft confetti pattern.",
    }
    stage_clause = ""
    if (mode or "").lower() == "stage":
        stage_clause = (
            " The input is an EMPTY room. Furnish it completely in the chosen "
            "style: add appropriate sofas, tables, lighting fixtures, rugs, "
            "art, and accent decor. Preserve the original walls, windows, "
            "doors, and overall room geometry. The final image must look "
            "like a professionally staged real-estate listing photo."
        )
    lighting_clause = LIGHTING_CLAUSES.get((lighting_tone or "").lower(), "")
    material_clause = MATERIAL_CLAUSES.get((material_accent or "").lower(), "")

    # 2026-05-18 — image-understanding fusion BEFORE assembling the final
    # prompt. Drops the user's text when it contradicts the uploaded room
    # photo so we don't render a kitchen on a bedroom.
    #
    # Only run fusion when the user actually provided free-form text.
    # When `prompt` is empty (user picked only a style preset), fusion
    # was synthesising a "rewritten" prompt with no anchor signal, which
    # sometimes drifted away from the chosen style. Matches the gating
    # in tools.py:room_redesign (subscriber path).
    user_text = (prompt or "").strip()
    fusion = None
    fused_text = user_text
    if user_text:
        from app.services.image_understanding_service import (
            get_image_understanding_service,
        )
        fusion = await get_image_understanding_service().describe_and_fuse(
            image_bytes=contents,
            user_prompt=user_text,
            tool_context=f"room_redesign:{(space_kind or 'interior')}:{(mode or 'redesign')}",
            language="zh-TW",
        )
        fused_text = fusion.fused_prompt or user_text

    # 2026-05-18 — hard "no people" constraint. Architectural / staging
    # renders must show the space, not occupants. Redundant phrasing
    # because some upstream models drop a single negative cue.
    no_people_clause = (
        " Empty room: NO people, NO humans, NO faces, NO hands, NO pets, "
        "NO photographer in frame, NO occupants — render the space only, "
        "as a clean unpopulated architectural proposal."
    )
    final_prompt = f"{fused_text}{stage_clause}{lighting_clause}{material_clause}{no_people_clause}".strip()

    # Resolve the style preset against the catalog matching `space_kind`.
    # tools.py owns INTERIOR_STYLES / EXTERIOR_STYLES / COMMERCIAL_STYLES;
    # imported locally to avoid a top-level circular dependency (interior.py
    # → tools.py → … tools registry → interior router).
    style_prompt_suffix: Optional[str] = None
    if style_id:
        from app.api.v1.tools import (
            INTERIOR_STYLES,
            EXTERIOR_STYLES,
            COMMERCIAL_STYLES,
        )
        if (space_kind or "").lower() == "exterior":
            catalog = EXTERIOR_STYLES
        elif (space_kind or "").lower() == "commercial":
            catalog = COMMERCIAL_STYLES
        else:
            catalog = INTERIOR_STYLES
        match = next((s for s in catalog if s.get("id") == style_id), None)
        if match and match.get("prompt"):
            style_prompt_suffix = match["prompt"]

    service = get_interior_design_service()

    result = await service.redesign_room(
        room_image_base64=image_base64,
        prompt=final_prompt,
        style_id=style_id,
        room_type=room_type,
        keep_layout=True,
        style_prompt_suffix=style_prompt_suffix,
    )

    if not result.get("success"):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=result.get("error", "Failed to redesign room")
        )

    return DesignResponse(
        success=True,
        image_url=result.get("image_url"),
        description=result.get("description"),
        space_kind=space_kind if space_kind in ("interior", "exterior", "commercial") else None,
        vision_summary=(fusion.image_summary if fusion else None) or None,
        user_prompt_used=(fusion.used_user_prompt if fusion else None),
        prompt_gap_reason=(fusion.gap_reason if fusion else None),
    )


@router.post("/demo/generate", response_model=DesignResponse)
async def demo_generate(
    request: GenerateRequest
):
    """
    Demo endpoint for generating designs from text (no authentication required).

    Describe the room you want and the AI will generate it.
    Limited to demo usage.
    """
    service = get_interior_design_service()

    result = await service.generate_design(
        prompt=request.prompt,
        style_id=request.style_id,
        room_type=request.room_type
    )

    if not result.get("success"):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=result.get("error", "Failed to generate design")
        )

    return DesignResponse(
        success=True,
        image_url=result.get("image_url"),
        description=result.get("description")
    )
