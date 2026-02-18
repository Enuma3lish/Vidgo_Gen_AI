"""
VidGo Interior Design API Endpoints.

AI-powered interior design using Gemini 2.5 Flash Image:
- Room Redesign (Image + Text → Image)
- Design Generation (Text → Image)
- Style Fusion (Multi-image → Image)
- Iterative Editing (Multi-turn refinement)
- Style Transfer (Apply design style)
- 3D Model Generation (Image → GLB via Trellis)

Room-Type Constraints:
- A room can ONLY change STYLE, not change to a different room type
- e.g., bathroom → modern bathroom OK, bathroom → kitchen BLOCKED

Access: All users (demo) or Subscribers (full features)
"""
import uuid
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_current_user_optional
from app.models.user import User
from app.services.interior_design_service import (
    get_interior_design_service,
    DESIGN_STYLES,
    ROOM_TYPES
)
from app.providers.provider_router import get_provider_router, TaskType
from app.services.tier_config import get_credit_cost, get_user_tier


# ---------------------------------------------------------------------------
# Room-Type Logical Constraints
# ---------------------------------------------------------------------------
# A room can ONLY change its design STYLE, NOT become a different room type.
# Example: bathroom can become "modern bathroom" but NOT "kitchen".
ROOM_TYPE_CONSTRAINTS = {
    "living_room": ["living_room"],
    "bedroom": ["bedroom"],
    "kitchen": ["kitchen"],
    "bathroom": ["bathroom"],
    "dining_room": ["dining_room"],
    "home_office": ["home_office"],
    "balcony": ["balcony"],
}


def validate_room_redesign(source_room_type: Optional[str], target_room_type: Optional[str]):
    """
    Validate that the target room type is compatible with the source room type.
    A bathroom cannot become a kitchen, etc.
    """
    if not source_room_type or not target_room_type:
        return  # If either is not specified, skip validation

    allowed = ROOM_TYPE_CONSTRAINTS.get(source_room_type, [source_room_type])
    if target_room_type not in allowed:
        source_name = ROOM_TYPES.get(source_room_type, {}).get("name_zh", source_room_type)
        target_name = ROOM_TYPES.get(target_room_type, {}).get("name_zh", target_room_type)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"無法將{source_name}轉換為{target_name}。房間只能變更設計風格，不能變更房間類型。"
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
    source_room_type: Optional[str] = Field(None, description="Source room type for validation")
    target_room_type: Optional[str] = Field(None, description="Target room type (must match source)")


class DesignResponse(BaseModel):
    success: bool
    image_url: Optional[str] = None
    description: Optional[str] = None
    conversation_id: Optional[str] = None
    turn_count: Optional[int] = None
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

    # Credit check for authenticated users
    if current_user:
        cost = get_credit_cost("interior", current_user)
        if current_user.total_credits < cost:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail={
                    "error": "insufficient_credits",
                    "message": "點數不足，請儲值",
                    "required": cost,
                    "current": current_user.total_credits,
                }
            )

    service = get_interior_design_service()

    result = await service.redesign_room(
        room_image_base64=request.room_image_base64,
        room_image_url=request.room_image_url,
        prompt=request.prompt,
        style_id=request.style_id,
        room_type=request.room_type,
        keep_layout=request.keep_layout
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

    # Room-type constraint: cannot change room type, only style
    validate_room_redesign(request.source_room_type, request.target_room_type)

    # Credit check
    if current_user:
        cost = get_credit_cost("interior", current_user)
        if current_user.total_credits < cost:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail={
                    "error": "insufficient_credits",
                    "message": "點數不足，請儲值",
                    "required": cost,
                    "current": current_user.total_credits,
                }
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

    # Read and encode the image
    contents = await image.read()
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


# ============ 3D Model Generation (Trellis) ============

class Generate3DRequest(BaseModel):
    """Generate 3D model from a 2D interior design image."""
    image_url: str = Field(..., description="URL of 2D interior design image")
    texture_size: int = Field(1024, description="Texture resolution (512 or 1024)")
    mesh_simplify: float = Field(0.95, ge=0.0, le=1.0, description="Mesh simplification ratio")


class Generate3DResponse(BaseModel):
    """Response with 3D model URL (GLB format)."""
    success: bool
    model_url: Optional[str] = None
    task_id: Optional[str] = None
    error: Optional[str] = None


@router.post("/3d-model", response_model=Generate3DResponse)
async def generate_3d_model(
    request: Generate3DRequest,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db)
):
    """
    Generate a 3D model (GLB) from a 2D interior design image using PiAPI Trellis.

    The output is a GLB file that can be rendered in a Three.js viewer on the frontend.
    Cost: ~$0.04 per generation.

    Requires authentication and sufficient credits.
    """
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required for 3D model generation"
        )

    # Credit check
    cost = get_credit_cost("interior_3d", current_user)
    if current_user.total_credits < cost:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={
                "error": "insufficient_credits",
                "message": "點數不足，請儲值",
                "required": cost,
                "current": current_user.total_credits,
            }
        )

    # Determine tier for texture quality
    tier = get_user_tier(current_user)
    texture_size = 512 if tier == "free" else request.texture_size

    try:
        provider_router = get_provider_router()
        result = await provider_router.route(
            TaskType.INTERIOR_3D,
            {
                "image_url": request.image_url,
                "texture_size": texture_size,
                "mesh_simplify": request.mesh_simplify,
            },
            user_tier=tier,
        )

        output = result.get("output", {})
        model_url = output.get("model_url") or output.get("glb_url") or output.get("url")

        return Generate3DResponse(
            success=True,
            model_url=model_url,
            task_id=result.get("task_id"),
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"3D model generation failed: {str(e)}"
        )


# ============ Room-Type Constraint Info ============

@router.get("/room-constraints")
async def get_room_constraints():
    """
    Get room-type constraint information.

    A room can only change its design STYLE, not its room TYPE.
    For example, a bathroom can be redesigned in Japanese Zen style,
    but cannot be converted to a kitchen.
    """
    return {
        "constraints": ROOM_TYPE_CONSTRAINTS,
        "message": "Each room type can only be redesigned within the same room type. "
                   "Change the STYLE, not the room TYPE.",
        "examples": {
            "allowed": [
                {"from": "bathroom", "to": "bathroom", "style": "japanese", "note": "OK - same room, different style"},
                {"from": "kitchen", "to": "kitchen", "style": "modern_minimalist", "note": "OK - same room, different style"},
            ],
            "blocked": [
                {"from": "bathroom", "to": "kitchen", "note": "BLOCKED - cannot change room type"},
                {"from": "bedroom", "to": "living_room", "note": "BLOCKED - cannot change room type"},
            ]
        }
    }
