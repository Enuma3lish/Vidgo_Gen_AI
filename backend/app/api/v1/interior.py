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
import uuid
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_current_active_user, get_current_user_optional, is_subscribed_user
from app.core.upload_validation import ROOM_REDESIGN_IMAGE_DIMENSION_RULES, validate_uploaded_content
from app.models.user import User
from app.providers.provider_router import TaskType, get_provider_router
from app.services.interior_design_service import (
    get_interior_design_service,
    DESIGN_STYLES,
    ROOM_TYPES
)

router = APIRouter(prefix="/interior", tags=["interior"])


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

    try:
        result = await provider_router.route(
            TaskType.INTERIOR,
            {
                "image_url": image_url,
                "prompt": request.prompt,
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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate 3D model: {exc}"
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
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Floor-plan interior render failed: {exc}"
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
            detail=f"Failed to generate 3D model from floor plan: {exc}"
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


# ============ Demo Endpoint (No Auth Required) ============

@router.post("/demo/redesign", response_model=DesignResponse)
async def demo_redesign(
    prompt: str = Form(..., description="Description of desired changes"),
    style_id: Optional[str] = Form(None, description="Design style to apply"),
    room_type: Optional[str] = Form(None, description="Type of room"),
    image: UploadFile = File(..., description="Room image file")
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

    service = get_interior_design_service()

    result = await service.redesign_room(
        room_image_base64=image_base64,
        prompt=prompt,
        style_id=style_id,
        room_type=room_type,
        keep_layout=True
    )

    if not result.get("success"):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=result.get("error", "Failed to redesign room")
        )

    return DesignResponse(
        success=True,
        image_url=result.get("image_url"),
        description=result.get("description")
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
