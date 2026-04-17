"""
Interior Design Service
Uses Gemini 2.5 Flash Image for AI-powered room redesign and interior design generation.

Features:
- Image + Text → Image: Upload room photo + text prompt = redesigned room
- Text → Image: Generate design from text description only
- Multi-image Fusion: Combine room photo with style reference
- Iterative Editing: Multi-turn dialogue for continuous refinement
- Style Transfer: Apply specific design styles to rooms
"""
import asyncio
import logging
import base64
import uuid
import json
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


# Available interior design styles
DESIGN_STYLES = {
    "modern_minimalist": {
        "id": "modern_minimalist",
        "name": "Modern Minimalist",
        "name_zh": "現代極簡",
        "description": "Clean lines, neutral colors, minimal furniture, open spaces",
        "prompt_suffix": "modern minimalist interior, clean geometric lines, neutral white and warm grey palette, low-profile furniture with hidden storage, polished concrete or light oak flooring, floor-to-ceiling windows with sheer linen curtains, recessed LED strip lighting, single statement art piece, architectural visualization quality"
    },
    "scandinavian": {
        "id": "scandinavian",
        "name": "Scandinavian",
        "name_zh": "北歐風格",
        "description": "Light wood, white walls, cozy textiles, functional design",
        "prompt_suffix": "Scandinavian hygge interior, pale birch wood furniture with rounded edges, matte white walls, chunky knit wool throw on light grey sofa, sheepskin rug on pale oak herringbone floor, brass pendant lamp, potted monstera in ceramic planter, soft north-facing window light, warm cozy functional living"
    },
    "japanese": {
        "id": "japanese",
        "name": "Japanese Zen",
        "name_zh": "日式禪風",
        "description": "Tatami, shoji screens, natural materials, zen simplicity",
        "prompt_suffix": "Japanese wabi-sabi zen interior, tatami mat flooring with shoji paper sliding screens, low natural cypress wood platform furniture, ikebana arrangement, tokonoma alcove, diffused paper lantern lighting, muted earth tones with charcoal and cream, bamboo accent wall, serene meditative atmosphere"
    },
    "industrial": {
        "id": "industrial",
        "name": "Industrial",
        "name_zh": "工業風",
        "description": "Exposed brick, metal accents, raw textures, urban loft",
        "prompt_suffix": "industrial loft interior, exposed red brick walls with original mortar, black steel I-beam ceiling with exposed ductwork, polished concrete floor, oversized factory windows with black metal mullions, Edison bulb pendant cluster, worn leather tufted sofa, reclaimed wood and steel pipe shelving, warehouse conversion aesthetic"
    },
    "bohemian": {
        "id": "bohemian",
        "name": "Bohemian",
        "name_zh": "波西米亞",
        "description": "Eclectic patterns, rich colors, layered textiles, artistic",
        "prompt_suffix": "bohemian eclectic interior, layered Moroccan kilim rugs on terracotta tile, macrame wall hanging, rattan peacock chair with colorful cushions, trailing pothos and fiddle leaf fig plants, woven basket pendant lamps, amber string lights, rich emerald and burnt orange jewel tones, artistic maximalist lived-in atmosphere"
    },
    "mediterranean": {
        "id": "mediterranean",
        "name": "Mediterranean",
        "name_zh": "地中海風格",
        "description": "Terracotta, blue accents, arched doorways, rustic charm",
        "prompt_suffix": "Mediterranean coastal interior, hand-laid terracotta hexagonal floor tiles, whitewashed lime plaster walls with arched doorways, cerulean blue window shutters, wrought iron fixtures with candle-style bulbs, solid wood dining table with linen runner, ceramic hand-painted accent tiles, warm golden afternoon sunlight, relaxed coastal elegance"
    },
    "art_deco": {
        "id": "art_deco",
        "name": "Art Deco",
        "name_zh": "裝飾藝術",
        "description": "Geometric patterns, metallic accents, refined materials, sophistication",
        "prompt_suffix": "Art Deco style interior, geometric chevron patterned stone floor in black and white, deep green tufted sofa with metallic nailhead trim, sunburst decorative mirror, fluted column details, lacquered black console with brass inlay, glass display cabinet, dramatic uplighting on fluted wall panels, 1920s inspired geometric sophistication"
    },
    "mid_century_modern": {
        "id": "mid_century_modern",
        "name": "Mid-Century Modern",
        "name_zh": "中世紀現代",
        "description": "Organic curves, retro furniture, bold colors, iconic design",
        "prompt_suffix": "mid-century modern interior circa 1960, classic molded plywood lounge chair with leather cushion, teak credenza with tapered legs, starburst metal chandelier, sunburst wall clock, bold mustard yellow accent wall, geometric patterned area rug, large picture window with greenery view, retro atomic age style"
    },
    "coastal": {
        "id": "coastal",
        "name": "Coastal",
        "name_zh": "海岸風格",
        "description": "Blue tones, white furniture, nautical elements, beachy",
        "prompt_suffix": "coastal Hampton interior, whitewashed shiplap walls, bleached driftwood-finish wide plank flooring, soft navy and crisp white linen upholstery, natural seagrass baskets and rattan pendant lights, large sliding glass doors open to ocean view, weathered rope detail accents, bright airy natural daylight, relaxed seaside living"
    },
    "farmhouse": {
        "id": "farmhouse",
        "name": "Farmhouse",
        "name_zh": "農舍風格",
        "description": "Rustic wood, vintage accents, cozy warmth, country charm",
        "prompt_suffix": "modern farmhouse interior, reclaimed barn wood accent wall with original nail holes, white subway tile backsplash with dark grout, apron-front farmhouse sink, open shelving with mason jars and stoneware, black matte hardware on cream Shaker cabinets, wrought iron chandelier with Edison bulbs, wide plank pine floor, warm morning light"
    }
}


# Room types for better context
ROOM_TYPES = {
    "living_room": {
        "id": "living_room",
        "name": "Living Room",
        "name_zh": "客廳",
        "context": "residential living room approximately 20-30 square meters, featuring a main seating area with sofa, coffee table, TV console or entertainment wall, area rug, and ambient plus accent lighting"
    },
    "bedroom": {
        "id": "bedroom",
        "name": "Bedroom",
        "name_zh": "臥室",
        "context": "residential bedroom approximately 12-20 square meters, featuring a queen or king bed with headboard, matching nightstands with table lamps, wardrobe or closet area, and soft warm ambient lighting"
    },
    "kitchen": {
        "id": "kitchen",
        "name": "Kitchen",
        "name_zh": "廚房",
        "context": "residential kitchen approximately 8-15 square meters, featuring upper and lower cabinetry, countertop workspace, built-in appliances including oven and cooktop, task lighting under cabinets, and a backsplash area"
    },
    "bathroom": {
        "id": "bathroom",
        "name": "Bathroom",
        "name_zh": "浴室",
        "context": "residential bathroom approximately 4-8 square meters, featuring a vanity with mirror and basin, walk-in shower or freestanding bathtub, wall and floor tiling, and recessed waterproof lighting"
    },
    "dining_room": {
        "id": "dining_room",
        "name": "Dining Room",
        "name_zh": "餐廳",
        "context": "residential dining area approximately 10-18 square meters, featuring a dining table seating 4-6 with chairs, overhead pendant or chandelier lighting, and a sideboard or buffet cabinet"
    },
    "home_office": {
        "id": "home_office",
        "name": "Home Office",
        "name_zh": "書房",
        "context": "residential home office approximately 8-12 square meters, featuring a work desk with ergonomic chair, bookshelves or wall-mounted shelving, task desk lamp, and organized cable management"
    },
    "balcony": {
        "id": "balcony",
        "name": "Balcony",
        "name_zh": "陽台",
        "context": "residential enclosed or open balcony approximately 4-10 square meters, featuring outdoor-rated seating with weather-resistant cushions, potted plants, and string lights or lantern lighting"
    }
}


class InteriorDesignService:
    """
    Interior Design Service using Gemini 2.5 Flash Image.

    Supports:
    - Image + Text → Image (room redesign)
    - Text → Image (generate from description)
    - Multi-image Fusion (room + style reference)
    - Iterative Editing (multi-turn refinement)
    - Style Transfer (apply design styles)
    """

    BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
    MODEL = "gemini-2.5-flash-image"  # Gemini 2.5 Flash Image for image generation

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or getattr(settings, 'GEMINI_API_KEY', '')
        self.static_dir = Path("/app/static/generated/interior")
        self.static_dir.mkdir(parents=True, exist_ok=True)

        # Conversation history for iterative editing
        self._conversations: Dict[str, List[Dict]] = {}

    def _get_headers(self) -> Dict[str, str]:
        return {"Content-Type": "application/json"}

    async def _fetch_image_as_base64(self, image_url: str) -> Tuple[str, str]:
        """Fetch image from URL and return as base64 with mime type."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(image_url)
            if response.status_code == 200:
                content_type = response.headers.get("content-type", "image/jpeg")
                mime_type = content_type.split(";")[0]
                image_data = base64.b64encode(response.content).decode()
                return image_data, mime_type
            raise Exception(f"Failed to fetch image: {response.status_code}")

    def _save_generated_image(self, image_data: bytes, prefix: str = "design") -> str:
        """Save generated image to static directory and return URL."""
        filename = f"{prefix}_{uuid.uuid4().hex[:8]}.png"
        filepath = self.static_dir / filename
        filepath.write_bytes(image_data)
        return f"/static/generated/interior/{filename}"

    async def get_styles(self) -> List[Dict[str, Any]]:
        """Get all available interior design styles."""
        return list(DESIGN_STYLES.values())

    async def get_room_types(self) -> List[Dict[str, Any]]:
        """Get all available room types."""
        return list(ROOM_TYPES.values())

    # =========================================================================
    # Core Design Functions
    # =========================================================================

    async def redesign_room(
        self,
        room_image_base64: Optional[str] = None,
        room_image_url: Optional[str] = None,
        prompt: str = "",
        style_id: Optional[str] = None,
        room_type: Optional[str] = None,
        keep_layout: bool = True
    ) -> Dict[str, Any]:
        """
        Redesign a room based on image and text prompt.

        Image + Text → Image

        Args:
            room_image_base64: Base64-encoded room image
            room_image_url: URL of room image (alternative)
            prompt: Text description of desired changes
            style_id: Optional design style to apply
            room_type: Type of room for context
            keep_layout: Whether to preserve room layout

        Returns:
            Dict with redesigned image URL and description
        """
        if not self.api_key:
            return {
                "success": False,
                "error": "Gemini API key not configured"
            }

        # Get image as base64
        if room_image_url and not room_image_base64:
            try:
                room_image_base64, mime_type = await self._fetch_image_as_base64(room_image_url)
            except Exception as e:
                return {"success": False, "error": f"Failed to fetch image: {e}"}

        if not room_image_base64:
            return {"success": False, "error": "No room image provided"}

        # Determine mime type from base64
        mime_type = "image/jpeg"
        if room_image_base64.startswith("iVBOR"):
            mime_type = "image/png"

        # Build the prompt — photorealistic architectural visualization quality
        full_prompt = (
            "Redesign this room into a photorealistic interior design rendering. "
            "Output must look like a professional architectural visualization photograph "
            "with correct perspective, realistic material textures, and natural lighting. "
            "The room must be empty with no people, no person, no human figure, no silhouette. "
            "Do not include any luxury branded items. "
        )

        if keep_layout:
            full_prompt += "Preserve the existing window positions, door locations, and room geometry exactly. "

        if room_type and room_type in ROOM_TYPES:
            room_context = ROOM_TYPES[room_type]["context"]
            full_prompt += f"This is a {room_context}. "

        if style_id and style_id in DESIGN_STYLES:
            style_suffix = DESIGN_STYLES[style_id]["prompt_suffix"]
            full_prompt += f"Apply {style_suffix}. "

        full_prompt += prompt

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    f"{self.BASE_URL}/models/{self.MODEL}:generateContent",
                    params={"key": self.api_key},
                    headers=self._get_headers(),
                    json={
                        "contents": [
                            {
                                "role": "user",
                                "parts": [
                                    {
                                        "inline_data": {
                                            "mime_type": mime_type,
                                            "data": room_image_base64
                                        }
                                    },
                                    {"text": full_prompt}
                                ]
                            }
                        ],
                        "generationConfig": {
                            "responseModalities": ["TEXT", "IMAGE"],
                            "temperature": 0.8
                        }
                    }
                )

                if response.status_code == 200:
                    data = response.json()
                    return await self._process_image_response(data, "redesign")
                else:
                    error_text = response.text[:500]
                    logger.error(f"Gemini API error: {response.status_code} - {error_text}")
                    return {
                        "success": False,
                        "error": f"API error: {response.status_code}",
                        "details": error_text
                    }

        except Exception as e:
            logger.error(f"Interior design error: {e}")
            return {"success": False, "error": str(e)}

    async def generate_design(
        self,
        prompt: str,
        style_id: Optional[str] = None,
        room_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate interior design from text description only.

        Text → Image

        Args:
            prompt: Detailed text description of desired room
            style_id: Optional design style to apply
            room_type: Type of room to generate

        Returns:
            Dict with generated image URL and description
        """
        if not self.api_key:
            return {
                "success": False,
                "error": "Gemini API key not configured"
            }

        # Build the full prompt
        full_prompt = (
            "Generate a photorealistic interior design architectural visualization image. "
            "The room must be empty with no people, no person, no human figure. "
            "Do not include any luxury branded items. "
        )

        if room_type and room_type in ROOM_TYPES:
            room_context = ROOM_TYPES[room_type]["context"]
            full_prompt += f"Create a {room_context}. "

        if style_id and style_id in DESIGN_STYLES:
            style_suffix = DESIGN_STYLES[style_id]["prompt_suffix"]
            full_prompt += f"Use {style_suffix}. "

        full_prompt += prompt
        full_prompt += " Professional interior architectural photography, correct perspective, realistic material textures, natural lighting."

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    f"{self.BASE_URL}/models/{self.MODEL}:generateContent",
                    params={"key": self.api_key},
                    headers=self._get_headers(),
                    json={
                        "contents": [
                            {
                                "role": "user",
                                "parts": [{"text": full_prompt}]
                            }
                        ],
                        "generationConfig": {
                            "responseModalities": ["TEXT", "IMAGE"],
                            "temperature": 0.9
                        }
                    }
                )

                if response.status_code == 200:
                    data = response.json()
                    return await self._process_image_response(data, "generate")
                else:
                    error_text = response.text[:500]
                    logger.error(f"Gemini API error: {response.status_code} - {error_text}")
                    return {
                        "success": False,
                        "error": f"API error: {response.status_code}",
                        "details": error_text
                    }

        except Exception as e:
            logger.error(f"Interior design generation error: {e}")
            return {"success": False, "error": str(e)}

    async def fusion_design(
        self,
        room_image_base64: Optional[str] = None,
        room_image_url: Optional[str] = None,
        style_image_base64: Optional[str] = None,
        style_image_url: Optional[str] = None,
        prompt: str = ""
    ) -> Dict[str, Any]:
        """
        Combine room photo with style reference image.

        Multi-image Fusion: Room + Style Reference → Fused Result

        Args:
            room_image_base64: Base64-encoded room image
            room_image_url: URL of room image
            style_image_base64: Base64-encoded style reference
            style_image_url: URL of style reference image
            prompt: Additional instructions

        Returns:
            Dict with fused design image URL
        """
        if not self.api_key:
            return {
                "success": False,
                "error": "Gemini API key not configured"
            }

        # Get room image
        if room_image_url and not room_image_base64:
            try:
                room_image_base64, room_mime = await self._fetch_image_as_base64(room_image_url)
            except Exception as e:
                return {"success": False, "error": f"Failed to fetch room image: {e}"}

        # Get style image
        if style_image_url and not style_image_base64:
            try:
                style_image_base64, style_mime = await self._fetch_image_as_base64(style_image_url)
            except Exception as e:
                return {"success": False, "error": f"Failed to fetch style image: {e}"}

        if not room_image_base64 or not style_image_base64:
            return {"success": False, "error": "Both room image and style reference are required"}

        # Determine mime types
        room_mime = "image/png" if room_image_base64.startswith("iVBOR") else "image/jpeg"
        style_mime = "image/png" if style_image_base64.startswith("iVBOR") else "image/jpeg"

        full_prompt = f"""I have two images:
1. First image: A room that needs to be redesigned
2. Second image: A style reference showing the desired design aesthetic

Please redesign the room in the first image using the style, colors, and design elements from the second image.
Keep the room layout and window positions from the first image.
Apply the furniture style, color palette, and decorative elements from the second image.

{prompt}

Generate a photorealistic result."""

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    f"{self.BASE_URL}/models/{self.MODEL}:generateContent",
                    params={"key": self.api_key},
                    headers=self._get_headers(),
                    json={
                        "contents": [
                            {
                                "role": "user",
                                "parts": [
                                    {
                                        "inline_data": {
                                            "mime_type": room_mime,
                                            "data": room_image_base64
                                        }
                                    },
                                    {
                                        "inline_data": {
                                            "mime_type": style_mime,
                                            "data": style_image_base64
                                        }
                                    },
                                    {"text": full_prompt}
                                ]
                            }
                        ],
                        "generationConfig": {
                            "responseModalities": ["TEXT", "IMAGE"],
                            "temperature": 0.8
                        }
                    }
                )

                if response.status_code == 200:
                    data = response.json()
                    return await self._process_image_response(data, "fusion")
                else:
                    error_text = response.text[:500]
                    logger.error(f"Gemini API error: {response.status_code} - {error_text}")
                    return {
                        "success": False,
                        "error": f"API error: {response.status_code}",
                        "details": error_text
                    }

        except Exception as e:
            logger.error(f"Fusion design error: {e}")
            return {"success": False, "error": str(e)}

    async def iterative_edit(
        self,
        conversation_id: str,
        prompt: str,
        image_base64: Optional[str] = None,
        image_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Continue editing a design through multi-turn conversation.

        Iterative Editing: Continuous refinement through dialogue

        Args:
            conversation_id: ID for tracking conversation history
            prompt: Edit instruction for this turn
            image_base64: Optional new image to edit
            image_url: Optional URL of new image

        Returns:
            Dict with updated design and conversation state
        """
        if not self.api_key:
            return {
                "success": False,
                "error": "Gemini API key not configured"
            }

        # Initialize or get conversation history
        if conversation_id not in self._conversations:
            self._conversations[conversation_id] = []

        history = self._conversations[conversation_id]

        # Build user message parts
        user_parts = []

        # Add image if provided (for first turn or new image)
        if image_base64 or image_url:
            if image_url and not image_base64:
                try:
                    image_base64, mime_type = await self._fetch_image_as_base64(image_url)
                except Exception as e:
                    return {"success": False, "error": f"Failed to fetch image: {e}"}

            if image_base64:
                mime_type = "image/png" if image_base64.startswith("iVBOR") else "image/jpeg"
                user_parts.append({
                    "inline_data": {
                        "mime_type": mime_type,
                        "data": image_base64
                    }
                })

        user_parts.append({"text": prompt})

        # Add to history
        history.append({
            "role": "user",
            "parts": user_parts
        })

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    f"{self.BASE_URL}/models/{self.MODEL}:generateContent",
                    params={"key": self.api_key},
                    headers=self._get_headers(),
                    json={
                        "contents": history,
                        "generationConfig": {
                            "responseModalities": ["TEXT", "IMAGE"],
                            "temperature": 0.7
                        },
                        "systemInstruction": {
                            "parts": [{
                                "text": "You are an expert interior designer. Help the user refine their room design through iterative edits. Generate updated images based on their requests. Keep previous changes unless specifically asked to revert."
                            }]
                        }
                    }
                )

                if response.status_code == 200:
                    data = response.json()
                    result = await self._process_image_response(data, f"edit_{conversation_id[:8]}")

                    if result.get("success"):
                        # Add model response to history (text only, not the image)
                        history.append({
                            "role": "model",
                            "parts": [{"text": result.get("description", "Design updated.")}]
                        })

                        # Limit history to last 10 turns
                        if len(history) > 20:
                            self._conversations[conversation_id] = history[-20:]

                        result["conversation_id"] = conversation_id
                        result["turn_count"] = len(history) // 2

                    return result
                else:
                    error_text = response.text[:500]
                    logger.error(f"Gemini API error: {response.status_code} - {error_text}")
                    return {
                        "success": False,
                        "error": f"API error: {response.status_code}",
                        "details": error_text
                    }

        except Exception as e:
            logger.error(f"Iterative edit error: {e}")
            return {"success": False, "error": str(e)}

    async def transfer_style(
        self,
        room_image_base64: Optional[str] = None,
        room_image_url: Optional[str] = None,
        style_id: str = "modern_minimalist"
    ) -> Dict[str, Any]:
        """
        Apply a specific design style to a room image.

        Style Transfer: Room + Style → Styled Room

        Args:
            room_image_base64: Base64-encoded room image
            room_image_url: URL of room image
            style_id: ID of design style to apply

        Returns:
            Dict with styled room image URL
        """
        if style_id not in DESIGN_STYLES:
            return {
                "success": False,
                "error": f"Unknown style: {style_id}. Available: {list(DESIGN_STYLES.keys())}"
            }

        style = DESIGN_STYLES[style_id]
        prompt = f"Transform this room to {style['name']} style. {style['description']}. {style['prompt_suffix']}. Keep the room layout and window positions unchanged. The room must be empty with no people, no person, no human figure. Do not include any luxury branded items."

        return await self.redesign_room(
            room_image_base64=room_image_base64,
            room_image_url=room_image_url,
            prompt=prompt,
            keep_layout=True
        )

    # =========================================================================
    # Helper Methods
    # =========================================================================

    async def _process_image_response(self, data: Dict, prefix: str) -> Dict[str, Any]:
        """Process Gemini response and extract/save generated image."""
        candidates = data.get("candidates", [])

        if not candidates:
            return {
                "success": False,
                "error": "No response generated"
            }

        content = candidates[0].get("content", {})
        parts = content.get("parts", [])

        result = {
            "success": True,
            "description": "",
            "image_url": None
        }

        for part in parts:
            # Extract text description
            if "text" in part:
                result["description"] = part["text"]

            # Extract and save generated image
            if "inlineData" in part:
                inline_data = part["inlineData"]
                mime_type = inline_data.get("mimeType", "image/png")
                image_data = base64.b64decode(inline_data["data"])

                # Save to static directory
                result["image_url"] = self._save_generated_image(image_data, prefix)
                result["mime_type"] = mime_type

        if not result["image_url"]:
            # Try alternate format
            for part in parts:
                if "inline_data" in part:
                    inline_data = part["inline_data"]
                    mime_type = inline_data.get("mime_type", "image/png")
                    image_data = base64.b64decode(inline_data["data"])
                    result["image_url"] = self._save_generated_image(image_data, prefix)
                    result["mime_type"] = mime_type
                    break

        if not result["image_url"]:
            result["success"] = False
            result["error"] = "No image in response"
            result["raw_response"] = str(parts)[:500]

        return result

    def clear_conversation(self, conversation_id: str) -> bool:
        """Clear conversation history for iterative editing."""
        if conversation_id in self._conversations:
            del self._conversations[conversation_id]
            return True
        return False


# Singleton instance
_interior_design_service: Optional[InteriorDesignService] = None


def get_interior_design_service() -> InteriorDesignService:
    """Get or create Interior Design service singleton."""
    global _interior_design_service
    if _interior_design_service is None:
        _interior_design_service = InteriorDesignService()
    return _interior_design_service
