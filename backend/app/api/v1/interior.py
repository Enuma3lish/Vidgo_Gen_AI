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
from app.services.tier_config import get_user_tier
from app.services.interior_design_service import (
    get_interior_design_service,
    DESIGN_STYLES,
    ROOM_TYPES
)
from app.services.interior_growth_service import get_interior_growth_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/interior", tags=["interior"])

# ── Interior tool pricing (fallbacks) ──────────────────────────────────────
# A ServicePricing row keyed by the same service_type overrides these per the
# deduction-firewall pattern in tools._check_and_deduct_credits, so ops can
# retune without a redeploy. These constants must stay correct, since they are
# the live charge until the ServicePricing seed runs.
#   interior_floorplan = 2D floor-plan blueprint (平面配置圖)
#   interior_isometric = 3D isometric "dollhouse" view (立體圖)
#   interior_render    = photorealistic render only, 3D 效果圖 "render" tier
#   "video"    tier    = render + Kling 3.0/Omni growth video
#   "video_3d" tier    = + Trellis2 interactive GLB model
FLOORPLAN_CREDITS = 15
ISOMETRIC_CREDITS = 25
RENDER_CREDITS = 40
GROWTH_VIDEO_CREDITS = 600
GROWTH_VIDEO_3D_CREDITS = 750
GROWTH_3D_DELTA = GROWTH_VIDEO_3D_CREDITS - GROWTH_VIDEO_CREDITS  # refunded if 3D add-on yields no model
# Simulation tier = 4 variants of the locked space rendered concurrently for
# side-by-side comparison. Priced at ~3.5× single render (small bundle discount
# vs. 4× to encourage the comparison workflow).
SIMULATION_CREDITS = RENDER_CREDITS * 4 - 20  # 140

# ── Detail-mode surface presets (細化模式) — additive clauses appended to the
# preserve render's prompt so the user can swap floor/ceiling/wall textures
# without re-rolling style or geometry.
SURFACE_FLOOR_PRESETS = {
    "oak":      "Floor: warm light-oak hardwood in a herringbone pattern.",
    "walnut":   "Floor: rich dark walnut hardwood with subtle grain.",
    "marble":   "Floor: polished white marble with light grey veining.",
    "concrete": "Floor: polished pale concrete with a soft sheen.",
    "terrazzo": "Floor: cream terrazzo with confetti aggregate.",
    "tile":     "Floor: matte warm-taupe porcelain tile, fine grout lines.",
}
SURFACE_CEILING_PRESETS = {
    "white":        "Ceiling: flat smooth matte white painted ceiling.",
    "warm_white":   "Ceiling: warm-white painted ceiling with subtle cove detail.",
    "exposed_beam": "Ceiling: exposed warm-oak beams against a white plaster ceiling.",
    "industrial":   "Ceiling: exposed concrete ceiling with visible black steel beams.",
}
SURFACE_WALL_PRESETS = {
    "white":         "Walls: smooth matte white painted walls.",
    "warm_grey":     "Walls: warm-grey limewash walls with a soft hand-applied texture.",
    "feature_brick": "Walls: one feature wall in exposed red brick, the rest in matte white.",
    "wood_panel":    "Walls: one warm-oak vertical wood-panel feature wall, the rest in matte white.",
}

# Simulation variants — 4 distinct moods of the same locked space.
SIMULATION_VARIANT_PRESETS = [
    {"label": "Morning Daylight",  "lighting_tone": "daylight",          "material_accent": "wood"},
    {"label": "Warm Evening",      "lighting_tone": "warm_evening",      "material_accent": "leather"},
    {"label": "Overcast Soft",     "lighting_tone": "overcast_soft",     "material_accent": "concrete"},
    {"label": "Dramatic Golden",   "lighting_tone": "golden_hour",       "material_accent": "marble"},
]


def _build_surface_clause(floor: Optional[str], ceiling: Optional[str], wall: Optional[str]) -> str:
    parts = []
    if floor and floor in SURFACE_FLOOR_PRESETS:
        parts.append(SURFACE_FLOOR_PRESETS[floor])
    if ceiling and ceiling in SURFACE_CEILING_PRESETS:
        parts.append(SURFACE_CEILING_PRESETS[ceiling])
    if wall and wall in SURFACE_WALL_PRESETS:
        parts.append(SURFACE_WALL_PRESETS[wall])
    return " ".join(parts)


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


class FloorPlanRequest(BaseModel):
    """平面配置圖 — generate a clean 2D floor plan from requirements OR a sketch."""
    room_type: Optional[str] = Field(None, description="Primary room/space type hint.")
    dimensions: Optional[str] = Field(None, max_length=200, description="Free-text overall dimensions, e.g. '4m x 5m, 2 bedrooms'.")
    requirements: Optional[str] = Field(None, max_length=1000, description="Free-text needs (rooms, adjacencies, must-haves).")
    sketch_image_url: Optional[str] = Field(None, description="URL of an uploaded hand sketch / rough plan to clean up.")
    sketch_image_base64: Optional[str] = Field(None, description="Base64 of an uploaded sketch (alternative to URL).")
    # 2026-06-14 (owner): the 2D plan now ships with color. style_id picks the
    # interior-design family (scandinavian / industrial / japanese / …) so the
    # furniture icons + room fills read in that style; palette overrides the
    # base color family (warm / cool / neutral / vibrant / mono). Both are
    # optional — when both unset the plan falls back to the legacy white-bg
    # blueprint look so existing callers keep working.
    style_id: Optional[str] = Field(None, description="Interior design style (see GET /interior/styles).")
    palette: Optional[str] = Field(
        None,
        pattern="^(warm|cool|neutral|vibrant|mono)$",
        description="Color palette preset: warm | cool | neutral | vibrant | mono.",
    )
    language: Optional[str] = Field("en", description="UI locale hint.")


class IsometricRequest(BaseModel):
    """立體圖 — isometric 3D 'dollhouse' view from an uploaded image (e.g. a floor plan)."""
    image_url: Optional[str] = Field(None, description="URL of the source image (floor plan or layout).")
    image_base64: Optional[str] = Field(None, description="Base64 of the source image (alternative to URL).")
    style_id: Optional[str] = Field(None, description="Optional interior design style.")
    room_type: Optional[str] = Field(None, description="Optional room type hint.")
    prompt: Optional[str] = Field(None, max_length=1000, description="Optional extra request (materials, mood).")
    language: Optional[str] = Field("en", description="UI locale hint.")
    # 2026-06-12 — fine-tune knobs so the user can adjust the same render
    # instead of regenerating blind. Additive atmosphere clauses only.
    lighting_tone: Optional[str] = Field(None, description="daylight | warm_evening | golden_hour | overcast_soft | dramatic_spotlight | night")
    color_temperature: Optional[int] = Field(None, ge=2000, le=8000, description="Light color temperature in Kelvin (2700-6500 typical).")
    material_accent: Optional[str] = Field(None, description="wood | marble | concrete | linen | brass | leather | terrazzo")


class DesignResponse(BaseModel):
    success: bool
    image_url: Optional[str] = None
    description: Optional[str] = None
    conversation_id: Optional[str] = None
    turn_count: Optional[int] = None
    error: Optional[str] = None
    # Access-gate signal: when set to 'subscription_card_required' the frontend
    # (utils/toolGate.ts isCardRequired) pops the subscribe + add-card CTA.
    error_code: Optional[str] = None
    message: Optional[str] = None
    credits_used: int = 0
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
        "render",
        pattern="^(render|video|video_3d|simulation)$",
        description="What the user wants: 'render' = photorealistic 3D 效果圖 only; "
                    "'video' = render + Kling 3.0 growth animation; "
                    "'video_3d' = also reconstruct an interactive 3D model (.glb); "
                    "'simulation' = 4 light×material variants of the SAME locked space "
                    "for side-by-side comparison.",
    )
    duration: int = Field(5, ge=5, le=10, description="Growth-video length in seconds (5 or 10).")
    model_version: str = Field("v2", description="Trellis version for the 3D model when result_tier='video_3d'.")
    language: Optional[str] = Field("en", description="Language for the Gemini analysis ('en' | 'zh').")
    preserve_original: bool = Field(
        False,
        description="3D 效果圖 render mode. True = '保留結構' (preserve the uploaded "
                    "design's structure/layout and photorealize it); "
                    "False = '自由改造' (render a new design from the floor plan).",
    )
    structural_fidelity: int = Field(
        70, ge=0, le=100,
        description="保留結構 mode: how strictly to keep the original walls/layout/"
                    "furniture (higher = stricter). Ignored in 自由改造 mode.",
    )
    style_strength: int = Field(
        60, ge=0, le=100,
        description="保留結構 mode: how strongly the chosen style applies to "
                    "materials/colors/lighting (0 = keep original materials).",
    )
    # 2026-06-12 — detailed adjustment knobs (designer request): lighting mood
    # and color temperature, applied in every tier/mode as additive clauses.
    lighting_tone: Optional[str] = Field(
        None,
        description="daylight | warm_evening | golden_hour | overcast_soft | dramatic_spotlight | night",
    )
    color_temperature: Optional[int] = Field(
        None, ge=2000, le=8000,
        description="Light color temperature in Kelvin (2700-6500 typical).",
    )
    material_accent: Optional[str] = Field(
        None,
        description="wood | marble | concrete | linen | brass | leather | terrazzo",
    )
    # 2026-06-14 (owner): 細化 (detail) vs 魔法 (magic) modes.
    # - magic_mode=False (default): structure AND style of the uploaded image
    #   are locked; the user only tunes light + per-surface texture below.
    # - magic_mode=True: free-prompt path (uses `prompt`), structure still
    #   locked but style/materials may shift; backend injects extra
    #   anti-hallucination guards.
    magic_mode: bool = Field(
        False,
        description="True = 魔法模式 (free prompt, looser styling); False = 細化模式 "
                    "(layout + style locked, only surfaces + light tunable).",
    )
    surface_floor: Optional[str] = Field(
        None,
        description="Floor texture preset (細化 mode): oak | walnut | marble | concrete | terrazzo | tile.",
    )
    surface_ceiling: Optional[str] = Field(
        None,
        description="Ceiling preset (細化 mode): white | warm_white | exposed_beam | industrial.",
    )
    surface_wall: Optional[str] = Field(
        None,
        description="Wall preset (細化 mode): white | warm_grey | feature_brick | wood_panel.",
    )


class SimulationVariant(BaseModel):
    """One variant in a result_tier='simulation' response — same locked layout,
    different light × material combination so the user can compare moods."""
    label: str
    image_url: str
    lighting_tone: Optional[str] = None
    material_accent: Optional[str] = None


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
    # 2026-06-14: populated only when result_tier='simulation' — 4 variants of
    # the same locked space rendered with distinct light × material combos.
    simulation_variants: Optional[List[SimulationVariant]] = None
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
    # Real plan tier so premium subscribers keep their queue priority.
    # Unsubscribed visitors keep the legacy "basic" params (1024px renders —
    # dropping them to FREE_TIER's 512px would degrade the public demo);
    # they pick no model on this endpoint, so model gating is moot here.
    user_tier = get_user_tier(current_user) if is_subscribed_user(current_user) else "basic"

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
                # space_kind drives provider-side framing (exterior facades
                # need different anti-drift constraints than interiors).
                # Forgotten here pre-2026-06-06 — exterior requests silently
                # rendered with interior framing.
                "space_kind": request.space_kind,
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
            user_tier=get_user_tier(current_user),
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
            user_tier=get_user_tier(current_user),
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
            user_tier=get_user_tier(current_user),
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


async def _record_interior_generation(
    db: AsyncSession,
    user: User,
    service_type: str,
    input_image_url: Optional[str],
    result_image_url: Optional[str],
    credits_used: int,
    input_text: Optional[str] = None,
) -> None:
    """Best-effort UserGeneration history row — never break the response on it."""
    try:
        user_gen = UserGeneration(
            user_id=user.id,
            tool_type=ToolType.ROOM_REDESIGN,
            input_image_url=input_image_url,
            input_params={"pipeline": service_type},
            input_text=input_text,
            result_image_url=result_image_url,
            credits_used=credits_used,
        )
        if hasattr(user_gen, "set_expiry"):
            user_gen.set_expiry()
        db.add(user_gen)
        await db.commit()
    except Exception as exc:  # noqa: BLE001
        logger.warning("%s: generation record skipped: %s", service_type, exc)
        try:
            await db.rollback()
        except Exception:  # noqa: BLE001
            pass


@router.post("/floorplan", response_model=DesignResponse)
async def generate_floorplan_layout(
    request: FloorPlanRequest,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    """平面配置圖 — generate a clean 2D floor-plan layout from typed requirements
    OR an uploaded hand sketch (Gemini 2.5 Flash Image)."""
    has_text = bool((request.requirements or "").strip() or (request.dimensions or "").strip())
    has_sketch = bool(request.sketch_image_url or request.sketch_image_base64)
    if not has_text and not has_sketch:
        raise HTTPException(status_code=400, detail="Provide requirements/dimensions or upload a sketch.")

    # Floor-plan input is always custom → active subscription + bound card
    # required (admins / internal test accounts bypass via the gate).
    from app.services.access_gate import custom_prompt_gate
    if await custom_prompt_gate(db, current_user, is_custom=True) != "allow":
        return DesignResponse(
            success=False,
            error_code="subscription_card_required",
            message="平面配置圖需要有效訂閱並綁定信用卡。 / Floor-plan generation requires an active subscription with a bound card.",
        )

    from app.api.v1.tools import _check_and_deduct_credits, _refund_credits, _credits_charged
    ok, err = await _check_and_deduct_credits(db, current_user, FLOORPLAN_CREDITS, "interior_floorplan")
    if not ok:
        return DesignResponse(success=False, error=err)

    try:
        result = await get_interior_design_service().generate_floorplan(
            requirements=request.requirements or "",
            dimensions=request.dimensions,
            room_type=request.room_type,
            sketch_image_url=request.sketch_image_url,
            sketch_image_base64=request.sketch_image_base64,
            style_id=request.style_id,
            palette=request.palette,
        )
    except Exception as exc:  # noqa: BLE001
        await _refund_credits(db, current_user, FLOORPLAN_CREDITS, "interior_floorplan")
        logger.error("floorplan layout generation raised: %s", exc, exc_info=True)
        return DesignResponse(success=False, error="Floor-plan generation failed. Please try again.")

    if not result.get("success") or not result.get("image_url"):
        await _refund_credits(db, current_user, FLOORPLAN_CREDITS, "interior_floorplan")
        return DesignResponse(success=False, error=result.get("error") or "Floor-plan generation failed.")

    credits_used = _credits_charged(current_user, FLOORPLAN_CREDITS)
    await _record_interior_generation(
        db, current_user, "interior_floorplan",
        request.sketch_image_url, result.get("image_url"), credits_used,
        input_text=request.requirements,
    )
    return DesignResponse(
        success=True,
        image_url=result.get("image_url"),
        description="Floor plan generated",
        credits_used=credits_used,
    )


@router.post("/isometric", response_model=DesignResponse)
async def generate_isometric_view(
    request: IsometricRequest,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    """立體圖 — isometric 3D 'dollhouse' view from an uploaded image. Reuses
    interior_design_service.render_from_floorplan (its prompt yields a 45°
    isometric interior visualization)."""
    if not request.image_url and not request.image_base64:
        raise HTTPException(status_code=400, detail="An image (URL or base64) is required.")

    from app.services.access_gate import custom_prompt_gate
    if await custom_prompt_gate(db, current_user, is_custom=True) != "allow":
        return DesignResponse(
            success=False,
            error_code="subscription_card_required",
            message="立體圖需要有效訂閱並綁定信用卡。 / Isometric view requires an active subscription with a bound card.",
        )

    from app.api.v1.tools import _check_and_deduct_credits, _refund_credits, _credits_charged
    ok, err = await _check_and_deduct_credits(db, current_user, ISOMETRIC_CREDITS, "interior_isometric")
    if not ok:
        return DesignResponse(success=False, error=err)

    try:
        result = await get_interior_design_service().render_from_floorplan(
            floorplan_image_url=request.image_url,
            floorplan_image_base64=request.image_base64,
            style_id=request.style_id,
            room_type=request.room_type,
            extra_prompt=request.prompt or "",
            lighting_tone=request.lighting_tone,
            color_temperature=request.color_temperature,
            material_accent=request.material_accent,
        )
    except Exception as exc:  # noqa: BLE001
        await _refund_credits(db, current_user, ISOMETRIC_CREDITS, "interior_isometric")
        logger.error("isometric view generation raised: %s", exc, exc_info=True)
        return DesignResponse(success=False, error="Isometric view generation failed. Please try again.")

    if not result.get("success") or not result.get("image_url"):
        await _refund_credits(db, current_user, ISOMETRIC_CREDITS, "interior_isometric")
        return DesignResponse(success=False, error=result.get("error") or "Isometric view generation failed.")

    credits_used = _credits_charged(current_user, ISOMETRIC_CREDITS)
    await _record_interior_generation(
        db, current_user, "interior_isometric",
        request.image_url, result.get("image_url"), credits_used,
    )
    return DesignResponse(
        success=True,
        image_url=result.get("image_url"),
        description="Isometric view generated",
        credits_used=credits_used,
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
                "id": "render",
                "name": "3D Render",
                "name_zh": "3D 效果圖",
                "description": "Gemini renders a photorealistic 3D interior from your floor plan or room image (image only, no video).",
                "service_type": "interior_render",
                "credits": RENDER_CREDITS,
                "outputs": ["render_image"],
            },
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


async def _preserve_render(request: "FloorplanToVideoRequest", current_user: User) -> Dict[str, Any]:
    """保留結構 render. Primary: Flux ControlNet (depth) — hard-locks the output
    geometry to the uploaded design so structure/layout cannot drift or be
    invented (strongest anti-hallucination lever). Fallback: the Gemini
    structure-preserve render. Returns {success, image_url, error, engine}.

    structural_fidelity → ControlNet control_strength (higher = stricter lock);
    style_strength drives how much the chosen style restyles materials/lighting.
    """
    fidelity = max(0, min(100, request.structural_fidelity))
    strength = max(0, min(100, request.style_strength))

    style_name = ""
    if request.style_id and request.style_id in DESIGN_STYLES:
        style_name = DESIGN_STYLES[request.style_id].get("prompt_suffix") or DESIGN_STYLES[request.style_id].get("name", "")
    if strength <= 20 or not style_name:
        style_clause = "keeping the original materials, colors and textures"
    elif strength <= 70:
        style_clause = f"moderately styled toward {style_name}"
    else:
        style_clause = f"styled as {style_name}"
    # Atmosphere knobs (lighting / color temperature / material) apply to the
    # ControlNet path too — depth conditioning locks geometry, so these only
    # restyle light and surfaces.
    from app.services.interior_design_service import build_atmosphere_clause
    atmosphere = build_atmosphere_clause(
        request.lighting_tone, request.color_temperature, request.material_accent
    )
    lighting_default = "" if request.lighting_tone or request.color_temperature else "natural lighting, "
    # 2026-06-14 (owner): detail mode (magic_mode=False) → also lock the
    # FURNITURE and inject the user's surface presets so the render only
    # restyles flooring/walls/ceiling lighting and never invents new pieces.
    # Magic mode keeps the free prompt but adds explicit anti-hallucination
    # guards so the model doesn't add doors / windows / furniture not in the
    # uploaded design.
    surface_clause = _build_surface_clause(
        getattr(request, "surface_floor", None),
        getattr(request, "surface_ceiling", None),
        getattr(request, "surface_wall", None),
    )
    if not getattr(request, "magic_mode", False):
        guard_clause = (
            "STRICT preserve mode: keep every wall, window, door, and piece of "
            "furniture from the uploaded image in the same position and proportion; "
            "do NOT add, remove, or relocate any wall, opening, or furniture. Only "
            "restyle the surface materials and lighting as described."
        )
    else:
        guard_clause = (
            "Even in this free-design pass, do NOT add or remove walls, doors, "
            "windows, or major furniture pieces beyond what the uploaded image "
            "shows; restyle surfaces, decor, and lighting freely but keep the "
            "spatial layout intact."
        )
    cn_prompt = (
        "photorealistic real-world interior photograph, "
        f"{style_clause}, professional architectural visualization, {lighting_default}"
        "soft realistic shadows, sharp focus, high detail, no people, no text, no watermark. "
        f"{guard_clause} {surface_clause} {atmosphere} "
        + (request.prompt or "")
    ).strip()
    # fidelity 0..100 → control_strength 0.4..0.85 (higher = stricter geometry lock).
    control_strength = round(0.4 + (fidelity / 100) * 0.45, 2)

    try:
        piapi = get_provider_router().piapi
        cn = await piapi.controlnet_render({
            "image_url": request.image_url,
            "prompt": cn_prompt,
            "control_type": "depth",
            "control_strength": control_strength,
            "timeout": 300,
        })
        img = (cn.get("output") or {}).get("image_url") if cn and cn.get("success") else None
        if img:
            # ControlNet returns a temporary PiAPI URL — persist to GCS so it survives.
            from app.api.v1.tools import _persist_provider_url
            persisted = await _persist_provider_url(img, "image", current_user)
            return {"success": True, "image_url": persisted or img, "engine": "controlnet_depth"}
        logger.warning("[preserve-render] ControlNet returned no image; falling back to Gemini")
    except Exception as exc:  # noqa: BLE001
        logger.warning("[preserve-render] ControlNet failed (%s); falling back to Gemini", exc)

    g = await get_interior_design_service().render_realistic_preserve(
        image_url=request.image_url,
        style_id=request.style_id,
        structural_fidelity=fidelity,
        style_strength=strength,
        extra_prompt=request.prompt or "",
        lighting_tone=request.lighting_tone,
        color_temperature=request.color_temperature,
        material_accent=request.material_accent,
    )
    return {
        "success": bool(g.get("success") and g.get("image_url")),
        "image_url": g.get("image_url"),
        "error": g.get("error"),
        "engine": "gemini_preserve",
    }


async def _floorplan_to_video_inner(
    request: "FloorplanToVideoRequest",
    current_user: User,
    db: AsyncSession,
) -> FloorplanToVideoResponse:
    """Run the floor-plan growth pipeline (credits + orchestration + record).
    Returns a FloorplanToVideoResponse; the caller streams it with heartbeats.
    """
    is_admin = bool(getattr(current_user, "is_superuser", False))

    # Credit deduction reuses the platform's deduction firewall (admins bypass,
    # ServicePricing overrides the fallback `cost`). Imported lazily to avoid a
    # tools.py ↔ interior.py circular import at module load.
    from app.api.v1.tools import _check_and_deduct_credits, _refund_credits, _credits_charged

    # ── "simulation" tier: 4 light × material variants of the SAME locked
    # space, rendered concurrently for side-by-side mood comparison. Forces
    # preserve mode so all 4 variants share identical geometry/furniture
    # and only the atmosphere shifts.
    if request.result_tier == "simulation":
        ok, err = await _check_and_deduct_credits(
            db, current_user, SIMULATION_CREDITS, "interior_simulation",
        )
        if not ok:
            return FloorplanToVideoResponse(success=False, result_tier="simulation", error=err)
        try:
            from copy import deepcopy
            from asyncio import gather

            async def _one_variant(preset: dict) -> Optional[dict]:
                v_req = deepcopy(request)
                v_req.result_tier = "render"
                v_req.preserve_original = True       # always locked in simulation
                v_req.magic_mode = False
                v_req.lighting_tone = preset["lighting_tone"]
                v_req.material_accent = preset["material_accent"]
                rendered = await _preserve_render(v_req, current_user)
                if not rendered.get("success") or not rendered.get("image_url"):
                    return None
                return {
                    "label": preset["label"],
                    "image_url": rendered["image_url"],
                    "lighting_tone": preset["lighting_tone"],
                    "material_accent": preset["material_accent"],
                }

            results = await gather(*(_one_variant(p) for p in SIMULATION_VARIANT_PRESETS))
            variants = [SimulationVariant(**r) for r in results if r]
        except Exception as exc:  # noqa: BLE001
            await _refund_credits(db, current_user, SIMULATION_CREDITS, "interior_simulation")
            logger.error("simulation tier raised: %s", exc, exc_info=True)
            return FloorplanToVideoResponse(
                success=False, result_tier="simulation",
                error="Simulation render failed. Please try again.",
            )
        if not variants:
            await _refund_credits(db, current_user, SIMULATION_CREDITS, "interior_simulation")
            return FloorplanToVideoResponse(
                success=False, result_tier="simulation",
                error="Simulation render produced no variants.",
            )
        # Partial refund proportional to missing variants (kept proportional so
        # the user is never charged for failed renders that came back empty).
        if len(variants) < len(SIMULATION_VARIANT_PRESETS):
            missing = len(SIMULATION_VARIANT_PRESETS) - len(variants)
            refund = int(SIMULATION_CREDITS * missing / len(SIMULATION_VARIANT_PRESETS))
            if refund > 0:
                await _refund_credits(db, current_user, refund, "interior_simulation")
        credits_used = _credits_charged(current_user, SIMULATION_CREDITS)
        if len(variants) < len(SIMULATION_VARIANT_PRESETS):
            missing = len(SIMULATION_VARIANT_PRESETS) - len(variants)
            credits_used = max(0, credits_used - int(SIMULATION_CREDITS * missing / len(SIMULATION_VARIANT_PRESETS)))
        await _record_interior_generation(
            db, current_user, "interior_simulation",
            request.image_url, variants[0].image_url, credits_used,
        )
        return FloorplanToVideoResponse(
            success=True,
            result_tier="simulation",
            render_image_url=variants[0].image_url,   # convenience: first variant as the "hero"
            simulation_variants=variants,
            credits_used=credits_used,
        )

    # ── "render" tier: photorealistic 3D 效果圖 only (no Kling/Trellis) ──
    # Reuses the same Gemini render the growth pipeline uses for its end frame,
    # so output is visually consistent with the video tiers.
    if request.result_tier == "render":
        ok, err = await _check_and_deduct_credits(db, current_user, RENDER_CREDITS, "interior_render")
        if not ok:
            return FloorplanToVideoResponse(success=False, result_tier="render", error=err)
        try:
            if request.preserve_original:
                # 保留結構: ControlNet (depth) hard structure lock → Gemini fallback.
                rendered = await _preserve_render(request, current_user)
                result = {
                    "success": rendered["success"],
                    "image_url": rendered.get("image_url"),
                    "error": rendered.get("error"),
                }
            else:
                result = await get_interior_design_service().render_from_floorplan(
                    floorplan_image_url=request.image_url,
                    style_id=request.style_id,
                    room_type=request.room_type,
                    extra_prompt=request.prompt or "",
                    lighting_tone=request.lighting_tone,
                    color_temperature=request.color_temperature,
                    material_accent=request.material_accent,
                )
        except Exception as exc:  # noqa: BLE001
            await _refund_credits(db, current_user, RENDER_CREDITS, "interior_render")
            logger.error("3D render (render tier) raised: %s", exc, exc_info=True)
            # Return a graceful response (NOT raise): this runs inside the
            # heartbeat-streamed worker, where a raised HTTPException can't set a
            # real status and yields a body the frontend can't read as an error.
            return FloorplanToVideoResponse(
                success=False, result_tier="render",
                error="3D render failed. Please try again.",
            )
        if not result.get("success") or not result.get("image_url"):
            await _refund_credits(db, current_user, RENDER_CREDITS, "interior_render")
            return FloorplanToVideoResponse(
                success=False, result_tier="render", error=result.get("error") or "3D render failed",
            )
        credits_used = _credits_charged(current_user, RENDER_CREDITS)
        await _record_interior_generation(
            db, current_user, "interior_render",
            request.image_url, result.get("image_url"), credits_used,
        )
        return FloorplanToVideoResponse(
            success=True,
            result_tier="render",
            render_image_url=result.get("image_url"),
            credits_used=credits_used,
        )

    include_3d = request.result_tier == "video_3d"
    service_type = "interior_growth_video_3d" if include_3d else "interior_growth_video"
    cost = GROWTH_VIDEO_3D_CREDITS if include_3d else GROWTH_VIDEO_CREDITS

    ok, err = await _check_and_deduct_credits(db, current_user, cost, service_type)
    if not ok:
        return FloorplanToVideoResponse(success=False, result_tier=request.result_tier, error=err)

    # "Auto" effect on the video tiers: bias the render stage toward faithfully
    # preserving the uploaded design rather than restyling it.
    from app.services.interior_design_service import build_atmosphere_clause
    growth_extra_prompt = (
        build_atmosphere_clause(
            request.lighting_tone, request.color_temperature, request.material_accent
        ).strip()
        + " "
        + (request.prompt or "")
    ).strip()
    if request.preserve_original:
        growth_extra_prompt = (
            "Preserve the original design exactly — keep the same layout, structure, "
            "geometry, furniture placement, materials, colors and textures from the "
            "input; only make it photorealistic. Do not redesign or change the style. "
            + growth_extra_prompt
        ).strip()

    try:
        result = await get_interior_growth_service().run(
            floorplan_url=request.image_url,
            style_id=request.style_id,
            room_type=request.room_type,
            extra_prompt=growth_extra_prompt,
            include_3d=include_3d,
            duration=request.duration,
            model_version=request.model_version,
            language=request.language or "en",
        )
    except Exception as exc:
        await _refund_credits(db, current_user, cost, service_type)
        logger.error("floorplan-to-video pipeline raised: %s", exc, exc_info=True)
        # Graceful return (NOT raise) — see render-tier note above; this runs
        # inside the heartbeat-streamed worker.
        return FloorplanToVideoResponse(
            success=False, result_tier=request.result_tier,
            error="Floor-plan growth pipeline failed. Please try again.",
        )

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

    # Report the amount actually charged (ServicePricing-override aware; 0 for admins).
    credits_used = _credits_charged(current_user, cost)
    # Partial refund: the user paid for a 3D model that couldn't be produced.
    if include_3d and not result.get("model_url") and not is_admin:
        await _refund_credits(db, current_user, GROWTH_3D_DELTA, service_type)
        credits_used = max(0, credits_used - GROWTH_3D_DELTA)

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
