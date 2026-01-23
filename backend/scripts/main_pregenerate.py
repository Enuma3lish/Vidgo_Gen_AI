#!/usr/bin/env python3
"""
VidGo Main Pre-generation Pipeline
===================================

This is the UNIFIED pre-generation script that merges:
- pregenerate.py (original flow-based approach)
- pregenerate_mapping.py (mapping-based approach)

WORKFLOW:
=========
1. CLI parses arguments (--tool, --limit, --dry-run, --all)
2. Initialize API clients (PiAPI, Pollo, A2E, Rembg)
3. Run selected generator(s) based on tool mappings
4. Store results locally first, then batch to DB
5. Cleanup temp files and print summary

SUPPORTED TOOLS (7 total):
==========================
- ai_avatar: Avatar × Script × Language → A2E → Video
- background_removal: Prompt → T2I → Rembg → PNG
- room_redesign: Room × Style → T2I → Styled Room
- short_video: Prompt → Pollo T2V → Video
- product_scene: Product × Scene → T2I → Product in Scene
- try_on: Model × Clothing (gender restrictions) → T2I → Model wearing Clothing
- pattern_generate: Style × Prompt → T2I → Seamless Pattern

Usage:
    python -m scripts.main_pregenerate --tool ai_avatar --limit 10
    python -m scripts.main_pregenerate --tool try_on --limit 50
    python -m scripts.main_pregenerate --all --limit 20
    python -m scripts.main_pregenerate --dry-run
"""
import asyncio
import argparse
import hashlib
import logging
import os
import sys
import time
import shutil
from pathlib import Path
from typing import Dict, Any, Optional, List

# Add app to path
sys.path.insert(0, "/app")

from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.models.material import Material, ToolType, MaterialSource, MaterialStatus

# Import service clients
from scripts.services import PiAPIClient, PolloClient, A2EClient, RembgClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)


# ============================================================================
# TEMP LOCAL STORAGE
# ============================================================================

TEMP_DIR = Path("/app/static/temp_pregenerate")


def ensure_temp_dir():
    """Ensure temp directory exists."""
    TEMP_DIR.mkdir(parents=True, exist_ok=True)


def cleanup_temp_dir():
    """Remove temp directory after storing to DB."""
    if TEMP_DIR.exists():
        shutil.rmtree(TEMP_DIR)
        logger.info(f"Cleaned up temp directory: {TEMP_DIR}")


# ============================================================================
# AI AVATAR MAPPINGS
# ============================================================================

# Avatar definitions - DECOUPLED from scripts
# Any avatar can read any script
AVATAR_MAPPING = {
    "female-1": {
        "prompt": "Professional portrait of a young Chinese woman, natural makeup, confident smile, studio lighting, headshot",
        "gender": "female",
        "url": "https://images.unsplash.com/photo-1544005313-94ddf0286df2?w=512"
    },
    "female-2": {
        "prompt": "Professional portrait of an elegant Asian woman, subtle makeup, warm expression, soft lighting, headshot",
        "gender": "female",
        "url": "https://images.unsplash.com/photo-1531746020798-e6953c6e8e04?w=512"
    },
    "female-3": {
        "prompt": "Professional portrait of a friendly woman, natural look, approachable smile, business style headshot",
        "gender": "female",
        "url": "https://images.unsplash.com/photo-1438761681033-6461ffad8d80?w=512"
    },
    "male-1": {
        "prompt": "Professional portrait of a young Asian man, clean look, confident expression, studio lighting, headshot",
        "gender": "male",
        "url": "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=512"
    },
    "male-2": {
        "prompt": "Professional portrait of a middle-aged man, business professional, trustworthy expression, corporate headshot",
        "gender": "male",
        "url": "https://images.unsplash.com/photo-1472099645785-5658abf4ff4e?w=512"
    },
    "male-3": {
        "prompt": "Professional portrait of a young man, friendly smile, casual professional look, modern headshot",
        "gender": "male",
        "url": "https://images.unsplash.com/photo-1500648767791-00dcc994a43e?w=512"
    }
}

# Script definitions - DECOUPLED from avatars
# Organized by topic (matching MATERIAL_TOPICS)
SCRIPT_MAPPING = {
    "spokesperson": [
        {
            "id": "spokesperson-1",
            "text_en": "Welcome to our brand! I'm excited to introduce our latest innovative products that will transform your daily life.",
            "text_zh": "歡迎來到我們的品牌！我很高興為您介紹我們最新的創新產品，將改變您的日常生活。"
        },
        {
            "id": "spokesperson-2",
            "text_en": "Hello! As your brand ambassador, I'm thrilled to present our newest collection designed just for you.",
            "text_zh": "您好！作為品牌代言人，我很榮幸向您展示我們專為您設計的最新系列。"
        }
    ],
    "product_intro": [
        {
            "id": "product-intro-1",
            "text_en": "Hello everyone! Today I'll show you something truly special. Let's discover what makes our products unique.",
            "text_zh": "大家好！今天我要給您展示一些真正特別的東西。讓我們一起發現我們產品的獨特之處。"
        },
        {
            "id": "product-intro-2",
            "text_en": "Let me show you the amazing features of this product. It's designed with you in mind.",
            "text_zh": "讓我向您展示這款產品的驚人功能。它是專為您設計的。"
        }
    ],
    "customer_service": [
        {
            "id": "customer-service-1",
            "text_en": "Thank you for joining us! We've been working hard to bring you the best quality and experience possible.",
            "text_zh": "感謝您的加入！我們一直努力為您帶來最好的品質和體驗。"
        },
        {
            "id": "customer-service-2",
            "text_en": "Hello! I'm your dedicated customer service representative. Feel free to ask me anything, I'm here to help.",
            "text_zh": "您好！我是您的專屬客服代表。有任何問題都可以問我，我很樂意為您服務。"
        }
    ],
    "social_media": [
        {
            "id": "social-media-1",
            "text_en": "Hey everyone! Don't miss out on our exclusive offer. Subscribe now and save big on your first order!",
            "text_zh": "嗨大家好！不要錯過我們的獨家優惠。立即訂閱，首單享受超值折扣！"
        },
        {
            "id": "social-media-2",
            "text_en": "Hi there! Let me tell you about our amazing new features. Don't forget to like and subscribe!",
            "text_zh": "嗨！讓我告訴您關於我們驚人的新功能。記得點讚和訂閱！"
        }
    ]
}


# ============================================================================
# BACKGROUND REMOVAL MAPPING
# ============================================================================

BACKGROUND_REMOVAL_MAPPING = {
    "electronics": {
        "prompts": [
            "Professional product photo of a sleek smartwatch with metallic band on white background, studio lighting, 8K detail",
            "High-end wireless earbuds in charging case, minimalist white background, commercial photography",
            "Modern smartphone floating on white background, reflections, product photography"
        ]
    },
    "fashion": {
        "prompts": [
            "Designer sneakers on white background, studio lighting, fashion product photography",
            "Luxury leather handbag on white background, soft shadows, commercial quality",
            "Elegant high-heel shoes on white background, fashion editorial style"
        ]
    },
    "jewelry": {
        "prompts": [
            "Diamond engagement ring on white background, macro photography, sparkling reflections",
            "Gold necklace with pendant on white background, luxury jewelry photography",
            "Pearl earrings on white background, soft lighting, elegant product shot"
        ]
    },
    "food": {
        "prompts": [
            "Gourmet chocolate truffle on white background, food photography, appetizing",
            "Premium coffee beans scattered on white background, artisan quality",
            "Fresh organic fruit on white background, vibrant colors"
        ]
    },
    "cosmetics": {
        "prompts": [
            "Luxury lipstick on white background, beauty product photography, glossy finish",
            "Perfume bottle on white background, elegant lighting, premium product shot",
            "Skincare cream jar on white background, clean aesthetic"
        ]
    },
    "furniture": {
        "prompts": [
            "Modern minimalist chair on white background, furniture catalog style",
            "Elegant table lamp on white background, interior design photography",
            "Designer vase on white background, home decor product shot"
        ]
    },
    "toys": {
        "prompts": [
            "Colorful children's toy on white background, playful, bright colors",
            "Educational wooden blocks on white background, kids product photography",
            "Plush teddy bear on white background, soft toy product shot"
        ]
    },
    "sports": {
        "prompts": [
            "Professional tennis racket on white background, sports equipment photography",
            "Running shoes on white background, athletic product shot, dynamic",
            "Yoga mat rolled on white background, fitness product photography"
        ]
    }
}


# ============================================================================
# ROOM REDESIGN MAPPING
# ============================================================================

ROOM_REDESIGN_MAPPING = {
    "room_types": {
        "room-1": {
            "name": "Living Room",
            "name_zh": "客廳",
            "url": "https://images.unsplash.com/photo-1554995207-c18c203602cb?w=800",
            "room_type": "living_room"
        },
        "room-2": {
            "name": "Bedroom",
            "name_zh": "臥室",
            "url": "https://images.unsplash.com/photo-1616594039964-ae9021a400a0?w=800",
            "room_type": "bedroom"
        },
        "room-3": {
            "name": "Kitchen",
            "name_zh": "廚房",
            "url": "https://images.unsplash.com/photo-1556909114-f6e7ad7d3136?w=800",
            "room_type": "kitchen"
        },
        "room-4": {
            "name": "Bathroom",
            "name_zh": "浴室",
            "url": "https://images.unsplash.com/photo-1552321554-5fefe8c9ef14?w=800",
            "room_type": "bathroom"
        }
    },
    "styles": {
        "modern_minimalist": {
            "name": "Modern Minimalist",
            "name_zh": "現代簡約",
            "prompt": "modern minimalist interior design, clean lines, neutral colors, contemporary furniture"
        },
        "scandinavian": {
            "name": "Scandinavian",
            "name_zh": "北歐風格",
            "prompt": "scandinavian nordic interior design, hygge, wood textures, bright, cozy, white walls"
        },
        "japanese": {
            "name": "Japanese",
            "name_zh": "日式風格",
            "prompt": "japanese interior design, zen, tatami, bamboo, peaceful, wabi-sabi, natural materials"
        },
        "industrial": {
            "name": "Industrial",
            "name_zh": "工業風格",
            "prompt": "industrial interior design, exposed brick, metal accents, loft style, raw materials"
        },
        "mid_century_modern": {
            "name": "Mid-Century Modern",
            "name_zh": "中世紀現代",
            "prompt": "mid-century modern interior design, retro furniture, warm wood tones, organic shapes"
        }
    }
}


# ============================================================================
# PRODUCT SCENE MAPPING
# ============================================================================

PRODUCT_SCENE_MAPPING = {
    "products": {
        "product-1": {
            "name": "Watch",
            "name_zh": "手錶",
            "url": "https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=800"
        },
        "product-2": {
            "name": "Headphones",
            "name_zh": "耳機",
            "url": "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=800"
        },
        "product-3": {
            "name": "Sneaker",
            "name_zh": "運動鞋",
            "url": "https://images.unsplash.com/photo-1542291026-7eec264c27ff?w=800"
        },
        "product-4": {
            "name": "Camera",
            "name_zh": "相機",
            "url": "https://images.unsplash.com/photo-1526170375885-4d8ecf77b99f?w=800"
        },
        "product-5": {
            "name": "Perfume",
            "name_zh": "香水",
            "url": "https://images.unsplash.com/photo-1541643600914-78b084683601?w=800"
        }
    },
    "scenes": {
        "studio": {
            "name": "Studio",
            "name_zh": "攝影棚",
            "prompt": "professional studio lighting, solid color background, product photography"
        },
        "nature": {
            "name": "Nature",
            "name_zh": "自然",
            "prompt": "outdoor nature setting, sunlight, leaves, natural environment"
        },
        "luxury": {
            "name": "Luxury",
            "name_zh": "奢華",
            "prompt": "luxury marble background, elegant lighting, premium feeling"
        },
        "minimal": {
            "name": "Minimal",
            "name_zh": "極簡",
            "prompt": "minimalist abstract background, soft shadows, clean composition"
        },
        "lifestyle": {
            "name": "Lifestyle",
            "name_zh": "生活風格",
            "prompt": "lifestyle home setting, cozy atmosphere, everyday context"
        },
        "urban": {
            "name": "Urban",
            "name_zh": "都市",
            "prompt": "urban city backdrop, modern architecture, street style"
        },
        "seasonal": {
            "name": "Seasonal",
            "name_zh": "季節",
            "prompt": "seasonal autumn leaves background, warm colors, cozy feeling"
        },
        "holiday": {
            "name": "Holiday",
            "name_zh": "節日",
            "prompt": "festive holiday decoration background, christmas lights, celebration"
        }
    }
}


# ============================================================================
# SHORT VIDEO MAPPING
# ============================================================================

# Motion types available for video generation
# Each example should showcase a different motion effect
MOTION_TYPES = ["auto", "zoom-in", "zoom-out", "pan-left", "pan-right", "rotate"]

SHORT_VIDEO_MAPPING = {
    "auto": {
        "name": "Auto Motion",
        "name_zh": "自動動態",
        "motion": "auto",
        "prompts": [
            {
                "en": "Cinematic product showcase, luxury watch rotating slowly, golden hour lighting, 4K quality, smooth natural motion",
                "zh": "電影級產品展示，奢華手錶緩慢旋轉，黃金時刻光線，4K品質，流暢自然動態"
            },
            {
                "en": "Premium cosmetics product video, beauty items arranged artistically, soft lighting, natural movement",
                "zh": "高級化妝品產品影片，美妝產品藝術陳列，柔和光線，自然動態"
            }
        ]
    },
    "zoom-in": {
        "name": "Zoom In",
        "name_zh": "放大效果",
        "motion": "zoom-in",
        "prompts": [
            {
                "en": "Elegant jewelry close-up, diamond ring sparkling, gradual zoom revealing intricate details, luxury commercial",
                "zh": "優雅珠寶特寫，鑽戒閃耀，逐漸放大展現精緻細節，奢華廣告"
            },
            {
                "en": "Gourmet food presentation, delicious dish, camera zooming in to show texture and steam, appetizing video",
                "zh": "美食展示，美味料理，鏡頭放大展示質感與蒸氣，令人垂涎的影片"
            }
        ]
    },
    "zoom-out": {
        "name": "Zoom Out",
        "name_zh": "縮小效果",
        "motion": "zoom-out",
        "prompts": [
            {
                "en": "Fashion model full reveal, starting from elegant shoes, pulling back to show complete outfit, runway style",
                "zh": "時尚模特全身展示，從優雅鞋履開始，拉遠展示完整穿搭，走秀風格"
            },
            {
                "en": "Interior design showcase, room reveal from furniture detail to full space, architectural video",
                "zh": "室內設計展示，從家具細節到完整空間的房間呈現，建築影片"
            }
        ]
    },
    "pan-left": {
        "name": "Pan Left",
        "name_zh": "左移效果",
        "motion": "pan-left",
        "prompts": [
            {
                "en": "Product line showcase, multiple items displayed, smooth left pan revealing collection, commercial catalog",
                "zh": "產品線展示，多款商品陳列，平滑左移展現系列，商業目錄"
            },
            {
                "en": "Skincare routine display, bottles arranged in sequence, camera panning left through products, beauty brand video",
                "zh": "護膚流程展示，瓶瓶罐罐依序排列，鏡頭向左平移穿過產品，美妝品牌影片"
            }
        ]
    },
    "pan-right": {
        "name": "Pan Right",
        "name_zh": "右移效果",
        "motion": "pan-right",
        "prompts": [
            {
                "en": "Fashion accessories collection, sunglasses and bags displayed, smooth right pan, luxury brand showcase",
                "zh": "時尚配件系列，太陽眼鏡與包包陳列，平滑右移，奢侈品牌展示"
            },
            {
                "en": "Tech gadgets lineup, smartphones and tablets arranged, panoramic right movement, electronics commercial",
                "zh": "科技產品陣列，智慧型手機與平板電腦排列，全景右移，電子產品廣告"
            }
        ]
    },
    "rotate": {
        "name": "Rotate",
        "name_zh": "旋轉效果",
        "motion": "rotate",
        "prompts": [
            {
                "en": "360 degree product view, sleek wireless earbuds in case, rotating showcase, tech product reveal",
                "zh": "360度產品展示，時尚無線耳機及充電盒，旋轉展示，科技產品揭曉"
            },
            {
                "en": "Perfume bottle showcase, elegant glass design, slow rotation revealing all angles, luxury fragrance video",
                "zh": "香水瓶展示，優雅玻璃設計，慢速旋轉呈現各個角度，奢華香氛影片"
            }
        ]
    }
}


# ============================================================================
# TRY-ON MAPPING
# ============================================================================

# NOTE: input_image_url = CLOTHING preview image (shown in left panel)
#       result_image_url = model wearing the clothing (shown in right panel)
#
# MODEL REQUIREMENTS FOR KLING AI VIRTUAL TRY-ON:
# - Full body shot (head to at least waist visible)
# - Clear visibility of upper body/torso
# - Neutral pose with arms at sides or slightly bent
# - Plain or minimal background
# - Good lighting, no harsh shadows on body
# - Model wearing simple base clothing (t-shirt or tank top)
#
# We use AI-generated models to ensure consistent quality and
# compliance with Kling AI's requirements.

# Model photo prompts for AI generation (PiAPI T2I)
# These prompts generate full-body fashion model photos suitable for virtual try-on
MODEL_GENERATION_PROMPTS = {
    "female": [
        {
            "id": "female-fullbody-1",
            "prompt": "Professional full body fashion photography of a young Asian woman, standing pose with arms relaxed at sides, wearing simple white fitted tank top and light blue jeans, neutral gray studio background, soft even lighting, 3/4 body shot showing from head to knees, clear visibility of upper body and torso, fashion model pose, high quality, 8K",
            "description": "Young Asian woman - casual white tank top"
        },
        {
            "id": "female-fullbody-2",
            "prompt": "Full body fashion photo of a Caucasian woman in her 20s, relaxed standing pose, wearing plain black t-shirt and beige pants, white studio background, professional lighting, full body visible from head to feet, fashion catalog style, high resolution",
            "description": "Caucasian woman - black t-shirt"
        },
        {
            "id": "female-fullbody-3",
            "prompt": "Professional model photography of a young woman with medium brown skin, standing confidently, wearing simple gray fitted top and dark jeans, clean white background, soft studio lighting, full body shot, arms naturally at sides, fashion portrait, 8K quality",
            "description": "Diverse woman - gray fitted top"
        }
    ],
    "male": [
        {
            "id": "male-fullbody-1",
            "prompt": "Professional full body fashion photography of a young Asian man, standing pose with relaxed posture, wearing plain white crew neck t-shirt and navy blue chinos, neutral gray studio background, even lighting, 3/4 body shot from head to knees, clear torso visibility, fashion model look, high quality, 8K",
            "description": "Young Asian man - white t-shirt"
        },
        {
            "id": "male-fullbody-2",
            "prompt": "Full body fashion photo of a Caucasian man in his late 20s, confident standing pose, wearing simple black polo shirt and khaki pants, white studio background, professional photography lighting, full body visible, catalog style, high resolution",
            "description": "Caucasian man - black polo"
        },
        {
            "id": "male-fullbody-3",
            "prompt": "Professional model photography of a man with athletic build, standing naturally, wearing fitted gray t-shirt and dark denim jeans, clean white background, soft studio lighting, full body shot showing head to feet, arms relaxed, fashion portrait style, 8K",
            "description": "Athletic man - gray t-shirt"
        }
    ]
}

# Generated model library - populated by generate_model_library()
# Format: {"female-fullbody-1": {"gender": "female", "url": "/static/models/..."}}
GENERATED_MODEL_LIBRARY = {}

# Fallback: Original Unsplash URLs (facial close-ups) - used when no generated models available
# These will NOT work well with Kling AI Virtual Try-On but provide backward compatibility
TRYON_FALLBACK_MODELS = {
    "female-1": {
        "gender": "female",
        "url": "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=512",
        "note": "Facial close-up - may fail with Kling AI Try-On"
    },
    "female-2": {
        "gender": "female",
        "url": "https://images.unsplash.com/photo-1494790108377-be9c29b29330?w=512",
        "note": "Facial close-up - may fail with Kling AI Try-On"
    },
    "male-1": {
        "gender": "male",
        "url": "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=512",
        "note": "Facial close-up - may fail with Kling AI Try-On"
    }
}

TRYON_MAPPING = {
    # Models will be populated dynamically from GENERATED_MODEL_LIBRARY or fallback
    "models": {},
    "clothing": {
        "casual": [
            {
                "id": "casual-1",
                "name": "Casual Tank Top",
                "name_zh": "休閒背心套裝",
                "prompt": "black casual tank top with shorts, athletic style",
                "clothing_type": "general",
                "image_url": "https://images.unsplash.com/photo-1515886657613-9f3515b0c78f?w=400",
                "gender_restriction": None
            },
            {
                "id": "casual-2",
                "name": "Denim Jacket",
                "name_zh": "牛仔外套",
                "prompt": "blue denim jacket, casual style",
                "clothing_type": "general",
                "image_url": "https://images.unsplash.com/photo-1576995853123-5a10305d93c0?w=400",
                "gender_restriction": None
            }
        ],
        "formal": [
            {
                "id": "formal-1",
                "name": "Winter Coat",
                "name_zh": "冬季大衣",
                "prompt": "elegant beige winter coat, professional style",
                "clothing_type": "general",
                "image_url": "https://images.unsplash.com/photo-1539533018447-63fcce2678e4?w=400",
                "gender_restriction": None
            },
            {
                "id": "formal-2",
                "name": "Silk Scarf",
                "name_zh": "絲巾",
                "prompt": "elegant silk scarf, fashion accessory",
                "clothing_type": "general",
                "image_url": "https://images.unsplash.com/photo-1584030373081-f37b7bb4fa8e?w=400",
                "gender_restriction": None
            }
        ],
        "sportswear": [
            {
                "id": "sportswear-1",
                "name": "Athletic Jacket",
                "name_zh": "運動夾克",
                "prompt": "green athletic jacket, outdoor sportswear",
                "clothing_type": "general",
                "image_url": "https://images.unsplash.com/photo-1591047139829-d91aecb6caea?w=400",
                "gender_restriction": None
            },
            {
                "id": "sportswear-2",
                "name": "Sun Hat",
                "name_zh": "遮陽帽",
                "prompt": "stylish sun hat, summer accessory",
                "clothing_type": "general",
                "image_url": "https://images.unsplash.com/photo-1521369909029-2afed882baee?w=400",
                "gender_restriction": None
            }
        ],
        "outerwear": [
            {
                "id": "outerwear-1",
                "name": "Sunglasses",
                "name_zh": "太陽眼鏡",
                "prompt": "fashionable sunglasses, summer style",
                "clothing_type": "general",
                "image_url": "https://images.unsplash.com/photo-1511499767150-a48a237f0083?w=400",
                "gender_restriction": None
            }
        ],
        "dresses": [
            {
                "id": "dresses-1",
                "name": "Summer Dress",
                "name_zh": "夏季洋裝",
                "prompt": "red floral summer dress, feminine style",
                "clothing_type": "dress",
                "image_url": "https://images.unsplash.com/photo-1572804013427-4d7ca7268217?w=400",
                "gender_restriction": "female"  # Only female models
            },
            {
                "id": "dresses-2",
                "name": "Elegant Blouse",
                "name_zh": "優雅襯衫",
                "prompt": "elegant blouse, casual chic style",
                "clothing_type": "general",
                "image_url": "https://images.unsplash.com/photo-1564257631407-4deb1f99d992?w=400",
                "gender_restriction": None
            }
        ]
    }
}


# ============================================================================
# PATTERN GENERATE MAPPING
# ============================================================================

PATTERN_GENERATE_MAPPING = {
    "styles": {
        "seamless": {
            "name": "Seamless",
            "name_zh": "無縫圖案",
            "prompts": [
                {
                    "en": "Elegant rose floral pattern with gold and navy colors, seamless tile, high quality",
                    "zh": "優雅的玫瑰花卉圖案，金色與深藍色配色，無縫磁磚"
                },
                {
                    "en": "Japanese wave pattern in navy and white, seamless repeating design, traditional style",
                    "zh": "日式波浪紋樣，深藍與白色，無縫重複設計"
                }
            ]
        },
        "floral": {
            "name": "Floral",
            "name_zh": "花卉圖案",
            "prompts": [
                {
                    "en": "Watercolor cherry blossom pattern, soft pink and white, romantic style",
                    "zh": "水彩櫻花圖案，柔和粉白色，浪漫風格"
                },
                {
                    "en": "Tropical palm leaves seamless pattern, green and gold, summer vibes",
                    "zh": "熱帶棕櫚葉無縫圖案，綠色與金色，夏日氛圍"
                }
            ]
        },
        "geometric": {
            "name": "Geometric",
            "name_zh": "幾何圖案",
            "prompts": [
                {
                    "en": "Modern geometric pattern with triangles, black and gold, art deco style",
                    "zh": "現代幾何圖案搭配三角形，黑金配色，裝飾藝術風格"
                },
                {
                    "en": "Art deco golden lines pattern, elegant hexagonal design, luxury feel",
                    "zh": "裝飾藝術風格金線圖案，優雅六角形設計，奢華感"
                }
            ]
        },
        "abstract": {
            "name": "Abstract",
            "name_zh": "抽象圖案",
            "prompts": [
                {
                    "en": "Abstract marble texture with gold veins, luxury design, organic shapes",
                    "zh": "抽象大理石紋理配金色紋路，奢華設計，有機形狀"
                },
                {
                    "en": "Watercolor abstract splashes, vibrant colors, artistic expression",
                    "zh": "水彩抽象潑墨，鮮豔色彩，藝術表現"
                }
            ]
        },
        "traditional": {
            "name": "Traditional",
            "name_zh": "傳統紋樣",
            "prompts": [
                {
                    "en": "Chinese traditional cloud pattern, red and gold, auspicious design",
                    "zh": "中國傳統雲紋圖案，紅金配色，吉祥設計"
                },
                {
                    "en": "Japanese Seigaiha wave pattern, blue gradient, traditional motif",
                    "zh": "日式青海波紋，藍色漸層，傳統紋樣"
                }
            ]
        }
    }
}


# ============================================================================
# MAIN GENERATOR CLASS
# ============================================================================

class VidGoPreGenerator:
    """
    Unified VidGo Pre-generation Pipeline.

    Supports all 7 tools with mapping-based approach:
    - ai_avatar
    - background_removal
    - room_redesign
    - short_video
    - product_scene
    - try_on
    - pattern_generate
    - model_library (NEW: generates full-body model photos for try-on)
    """

    # Directory for generated model photos
    MODEL_LIBRARY_DIR = Path("/app/static/models")

    def __init__(self):
        # Initialize API clients
        self.piapi = PiAPIClient(os.getenv("PIAPI_KEY", ""))
        self.pollo = PolloClient(os.getenv("POLLO_API_KEY", ""))
        self.a2e = A2EClient(os.getenv("A2E_API_KEY", ""))
        self.rembg = RembgClient()

        # Ensure model library directory exists
        self.MODEL_LIBRARY_DIR.mkdir(parents=True, exist_ok=True)

        # Load existing model library
        self._load_model_library()

        # Stats tracking
        self.stats = {"success": 0, "failed": 0, "by_tool": {}}

        # Local results storage (batch to DB after generation)
        self.local_results: Dict[str, List[Dict]] = {}

    def _load_model_library(self):
        """Load existing model photos from disk into GENERATED_MODEL_LIBRARY."""
        global GENERATED_MODEL_LIBRARY, TRYON_MAPPING

        GENERATED_MODEL_LIBRARY.clear()
        model_dir = self.MODEL_LIBRARY_DIR

        if not model_dir.exists():
            logger.info("Model library directory does not exist, will use fallback models")
            TRYON_MAPPING["models"] = TRYON_FALLBACK_MODELS.copy()
            return

        # Scan for existing model images
        for gender in ["female", "male"]:
            gender_dir = model_dir / gender
            if gender_dir.exists():
                for img_file in gender_dir.glob("*.png"):
                    model_id = img_file.stem  # e.g., "female-fullbody-1"
                    GENERATED_MODEL_LIBRARY[model_id] = {
                        "gender": gender,
                        "url": f"/static/models/{gender}/{img_file.name}",
                        "local_path": str(img_file)
                    }
                    logger.debug(f"Loaded model: {model_id}")

        if GENERATED_MODEL_LIBRARY:
            logger.info(f"Loaded {len(GENERATED_MODEL_LIBRARY)} models from library")
            # Update TRYON_MAPPING with generated models
            TRYON_MAPPING["models"] = GENERATED_MODEL_LIBRARY.copy()
        else:
            logger.info("No generated models found, using fallback models")
            TRYON_MAPPING["models"] = TRYON_FALLBACK_MODELS.copy()

    async def check_apis(self) -> Dict[str, bool]:
        """Check which APIs are configured."""
        return {
            "piapi": bool(os.getenv("PIAPI_KEY")),
            "pollo": bool(os.getenv("POLLO_API_KEY")),
            "a2e": bool(os.getenv("A2E_API_KEY")),
            "rembg": self.rembg.available,
        }

    def _generate_lookup_hash(
        self,
        tool_type: str,
        prompt: str,
        effect_prompt: str = None,
        input_image_url: str = None
    ) -> str:
        """Generate unique lookup hash for Material."""
        content = f"{tool_type}:{prompt}:{effect_prompt or ''}:{input_image_url or ''}"
        return hashlib.sha256(content.encode()).hexdigest()[:64]

    # ========================================================================
    # AI AVATAR GENERATOR
    # ========================================================================

    async def generate_ai_avatar(self, limit: int = 10):
        """
        Generate AI Avatar videos.

        Combinations: Avatar × Script × Language
        Total potential: 6 avatars × 8 scripts × 2 languages = 96
        """
        logger.info("=" * 60)
        logger.info("AI AVATAR - Mapping Based Generation")
        logger.info("Avatars and Scripts are DECOUPLED")
        logger.info("=" * 60)

        self.stats["by_tool"]["ai_avatar"] = {"success": 0, "failed": 0}
        self.local_results["ai_avatar"] = []
        count = 0

        for avatar_id, avatar_data in AVATAR_MAPPING.items():
            if count >= limit:
                break

            for topic, scripts in SCRIPT_MAPPING.items():
                if count >= limit:
                    break

                for script in scripts:
                    if count >= limit:
                        break

                    for language in ["en", "zh-TW"]:
                        if count >= limit:
                            break

                        script_text = script["text_zh"] if language == "zh-TW" else script["text_en"]

                        logger.info(f"[{count+1}] Avatar: {avatar_id} | Topic: {topic} | Script: {script['id']} | Lang: {language}")
                        logger.info(f"  Script: {script_text[:40]}...")

                        start_time = time.time()

                        # Call A2E API
                        result = await self.a2e.generate_avatar(
                            script=script_text,
                            language=language,
                            image_url=avatar_data["url"],
                            gender=avatar_data["gender"],
                            save_locally=True
                        )

                        if not result["success"]:
                            logger.error(f"  Failed: {result.get('error', 'Unknown')}")
                            self.stats["failed"] += 1
                            self.stats["by_tool"]["ai_avatar"]["failed"] += 1
                            count += 1
                            continue

                        # Store locally
                        local_entry = {
                            "avatar_id": avatar_id,
                            "script_id": script["id"],
                            "topic": topic,
                            "language": language,
                            "prompt": script_text,
                            "input_image_url": avatar_data["url"],
                            "result_video_url": result["video_url"],
                            "input_params": {
                                "avatar_id": avatar_id,
                                "script_id": script["id"],
                                "language": language
                            },
                            "generation_steps": [{
                                "step": 1,
                                "api": "a2e",
                                "action": "avatar_generation",
                                "result_url": result["video_url"],
                                "duration_ms": int((time.time() - start_time) * 1000)
                            }],
                            "generation_cost": 0.10
                        }
                        self.local_results["ai_avatar"].append(local_entry)

                        logger.info(f"  Success: {result['video_url']}")
                        self.stats["success"] += 1
                        self.stats["by_tool"]["ai_avatar"]["success"] += 1
                        count += 1
                        await asyncio.sleep(2)

        await self._store_local_to_db("ai_avatar")

    # ========================================================================
    # BACKGROUND REMOVAL GENERATOR
    # ========================================================================

    async def generate_background_removal(self, limit: int = 10):
        """
        Generate Background Removal examples.

        Flow: Prompt → T2I → Rembg → Transparent PNG
        """
        logger.info("=" * 60)
        logger.info("BACKGROUND REMOVAL - T2I + Rembg")
        logger.info("=" * 60)

        self.stats["by_tool"]["background_removal"] = {"success": 0, "failed": 0}
        self.local_results["background_removal"] = []
        count = 0

        for topic, topic_data in BACKGROUND_REMOVAL_MAPPING.items():
            if count >= limit:
                break

            for prompt in topic_data["prompts"]:
                if count >= limit:
                    break

                logger.info(f"[{count+1}] Topic: {topic}")
                logger.info(f"  Prompt: {prompt[:50]}...")

                # Step 1: Generate source image
                logger.info("  Step 1: T2I...")
                t2i = await self.piapi.generate_image(prompt=prompt, width=1024, height=1024)

                if not t2i["success"]:
                    logger.error(f"  T2I Failed: {t2i.get('error')}")
                    self.stats["failed"] += 1
                    self.stats["by_tool"]["background_removal"]["failed"] += 1
                    count += 1
                    continue

                source_url = t2i["image_url"]
                logger.info(f"  Source: {source_url}")

                # Step 2: Remove background
                logger.info("  Step 2: Rembg...")
                if source_url.startswith("/static"):
                    local_path = f"/app{source_url}"
                    rembg_result = await self.rembg.remove_background_local(local_path)
                else:
                    rembg_result = await self.rembg.remove_background(source_url)

                if not rembg_result["success"]:
                    logger.error(f"  Rembg Failed: {rembg_result.get('error')}")
                    self.stats["failed"] += 1
                    self.stats["by_tool"]["background_removal"]["failed"] += 1
                    count += 1
                    continue

                result_url = rembg_result["image_url"]

                # Store locally
                local_entry = {
                    "topic": topic,
                    "prompt": prompt,
                    "input_image_url": source_url,
                    "result_image_url": result_url,
                    "generation_steps": [
                        {"step": 1, "api": "piapi", "action": "t2i", "result_url": source_url},
                        {"step": 2, "api": "rembg", "action": "remove_bg", "result_url": result_url}
                    ],
                    "generation_cost": 0.005
                }
                self.local_results["background_removal"].append(local_entry)

                logger.info(f"  Result: {result_url}")
                self.stats["success"] += 1
                self.stats["by_tool"]["background_removal"]["success"] += 1
                count += 1
                await asyncio.sleep(2)

        await self._store_local_to_db("background_removal")

    # ========================================================================
    # ROOM REDESIGN GENERATOR
    # ========================================================================

    async def generate_room_redesign(self, limit: int = 10):
        """
        Generate Room Redesign examples.

        Combinations: Room × Style
        Total: 4 rooms × 5 styles = 20
        """
        logger.info("=" * 60)
        logger.info("ROOM REDESIGN - Room × Style")
        logger.info("=" * 60)

        self.stats["by_tool"]["room_redesign"] = {"success": 0, "failed": 0}
        self.local_results["room_redesign"] = []
        count = 0

        room_types = ROOM_REDESIGN_MAPPING["room_types"]
        styles = ROOM_REDESIGN_MAPPING["styles"]

        for room_id, room_data in room_types.items():
            if count >= limit:
                break

            for style_id, style_data in styles.items():
                if count >= limit:
                    break

                logger.info(f"[{count+1}] Room: {room_data['name']} -> Style: {style_data['name']}")

                prompt = f"Photorealistic interior design of a {room_data['name'].lower()}, {style_data['prompt']}, architectural visualization, professional rendering, 8K"

                t2i = await self.piapi.generate_image(prompt=prompt)

                if not t2i["success"]:
                    logger.error(f"  Failed: {t2i.get('error')}")
                    self.stats["failed"] += 1
                    self.stats["by_tool"]["room_redesign"]["failed"] += 1
                    count += 1
                    continue

                local_entry = {
                    "topic": style_id,
                    "prompt": prompt,
                    "input_image_url": room_data["url"],
                    "result_image_url": t2i["image_url"],
                    "input_params": {
                        "room_id": room_id,
                        "style_id": style_id,
                        "room_type": room_data["room_type"]
                    },
                    "generation_cost": 0.005
                }
                self.local_results["room_redesign"].append(local_entry)

                logger.info(f"  Result: {t2i['image_url']}")
                self.stats["success"] += 1
                self.stats["by_tool"]["room_redesign"]["success"] += 1
                count += 1
                await asyncio.sleep(2)

        await self._store_local_to_db("room_redesign")

    # ========================================================================
    # SHORT VIDEO GENERATOR
    # ========================================================================

    async def generate_short_video(self, limit: int = 10):
        """
        Generate Short Video examples.

        Flow: Prompt → Pollo T2V → Video

        Each motion type gets its own examples to showcase the effect.
        Prompts are bilingual (en/zh) for proper display in frontend.
        """
        logger.info("=" * 60)
        logger.info("SHORT VIDEO - Pollo T2V with Motion Types")
        logger.info("=" * 60)

        self.stats["by_tool"]["short_video"] = {"success": 0, "failed": 0}
        self.local_results["short_video"] = []
        count = 0

        # Iterate through each motion type
        for motion_id, motion_data in SHORT_VIDEO_MAPPING.items():
            if count >= limit:
                break

            motion_name = motion_data["name"]
            motion_name_zh = motion_data["name_zh"]

            for prompt_data in motion_data["prompts"]:
                if count >= limit:
                    break

                prompt_en = prompt_data["en"]
                prompt_zh = prompt_data["zh"]

                logger.info(f"[{count+1}] Motion: {motion_name} ({motion_id})")
                logger.info(f"  Prompt (EN): {prompt_en[:50]}...")
                logger.info(f"  Prompt (ZH): {prompt_zh[:30]}...")

                # Use English prompt for generation (better results)
                result = await self.pollo.generate_video(prompt=prompt_en, length=5)

                if not result["success"]:
                    logger.error(f"  Failed: {result.get('error')}")
                    self.stats["failed"] += 1
                    self.stats["by_tool"]["short_video"]["failed"] += 1
                    count += 1
                    continue

                local_entry = {
                    "topic": motion_id,  # Use motion_id as topic
                    "prompt": prompt_en,
                    "prompt_zh": prompt_zh,  # Store Chinese prompt for frontend
                    "result_video_url": result["video_url"],
                    "generation_cost": 0.10,
                    "metadata": {
                        "motion": motion_id,
                        "motion_name": motion_name,
                        "motion_name_zh": motion_name_zh
                    }
                }
                self.local_results["short_video"].append(local_entry)

                logger.info(f"  Result: {result['video_url']}")
                self.stats["success"] += 1
                self.stats["by_tool"]["short_video"]["success"] += 1
                count += 1
                await asyncio.sleep(5)

        await self._store_local_to_db("short_video")

    # ========================================================================
    # PRODUCT SCENE GENERATOR
    # ========================================================================

    async def generate_product_scene(self, limit: int = 10):
        """
        Generate Product Scene examples.

        Combinations: Product × Scene
        Total: 5 products × 8 scenes = 40
        """
        logger.info("=" * 60)
        logger.info("PRODUCT SCENE - Product × Scene")
        logger.info("=" * 60)

        self.stats["by_tool"]["product_scene"] = {"success": 0, "failed": 0}
        self.local_results["product_scene"] = []
        count = 0

        products = PRODUCT_SCENE_MAPPING["products"]
        scenes = PRODUCT_SCENE_MAPPING["scenes"]

        for prod_id, prod_data in products.items():
            if count >= limit:
                break

            for scene_id, scene_data in scenes.items():
                if count >= limit:
                    break

                logger.info(f"[{count+1}] Product: {prod_data['name']} -> Scene: {scene_data['name']}")

                prompt = f"Professional product photography of a {prod_data['name']}, {scene_data['prompt']}, commercial lighting, 8K"

                t2i = await self.piapi.generate_image(prompt=prompt)

                if not t2i["success"]:
                    self.stats["failed"] += 1
                    self.stats["by_tool"]["product_scene"]["failed"] += 1
                    count += 1
                    continue

                local_entry = {
                    "topic": scene_id,
                    "prompt": prompt,
                    "input_image_url": prod_data["url"],
                    "result_image_url": t2i["image_url"],
                    "input_params": {
                        "product_id": prod_id,
                        "scene_type": scene_id
                    },
                    "generation_cost": 0.005
                }
                self.local_results["product_scene"].append(local_entry)

                logger.info(f"  Result: {t2i['image_url']}")
                self.stats["success"] += 1
                self.stats["by_tool"]["product_scene"]["success"] += 1
                count += 1
                await asyncio.sleep(1)

        await self._store_local_to_db("product_scene")

    # ========================================================================
    # TRY-ON GENERATOR
    # ========================================================================

    async def generate_try_on(self, limit: int = 10):
        """
        Generate Try-On examples using REAL Virtual Try-On API.

        Uses PiAPI's Kling AI Try-On API to actually overlay clothing
        onto model photos - NOT just generating images from text.

        Combinations: Model × Clothing (with gender restrictions)
        - Dresses/skirts: female models only
        - General clothing: any model

        IMPORTANT:
        - input_image_url = CLOTHING preview (what user selects)
        - result_image_url = model wearing clothing (REAL try-on result)

        MODEL LIBRARY:
        - Uses AI-generated full-body models from /static/models/
        - Models are uploaded to file hosting for PiAPI to access
        - Falls back to T2I if Kling AI Try-On fails
        """
        logger.info("=" * 60)
        logger.info("TRY-ON - Using Kling AI Virtual Try-On API")
        logger.info("=" * 60)

        # Reload model library in case it was just generated
        self._load_model_library()

        self.stats["by_tool"]["try_on"] = {"success": 0, "failed": 0}
        self.local_results["try_on"] = []
        count = 0

        models = TRYON_MAPPING["models"]
        clothing = TRYON_MAPPING["clothing"]

        if not models:
            logger.error("No models available! Run model_library first.")
            return

        logger.info(f"Using {len(models)} models from library")
        for mid, mdata in models.items():
            logger.info(f"  - {mid}: {mdata.get('url', 'N/A')[:50]}...")

        for model_id, model_data in models.items():
            if count >= limit:
                break

            for topic, clothes in clothing.items():
                if count >= limit:
                    break

                for cloth in clothes:
                    if count >= limit:
                        break

                    # Check gender restriction
                    gender_restriction = cloth.get("gender_restriction")
                    if gender_restriction and model_data["gender"] != gender_restriction:
                        logger.info(f"  Skipping: {cloth['name']} is {gender_restriction}-only, model is {model_data['gender']}")
                        continue

                    logger.info(f"[{count+1}] Model: {model_id} ({model_data['gender']}) -> Clothing: {cloth['name']} (Topic: {topic})")

                    # Get model image URL
                    # PiAPIClient._resolve_image_input() handles local files automatically
                    model_url = model_data["url"]
                    if model_url.startswith("/static/"):
                        # Use local path for base64 conversion
                        model_url = model_data.get("local_path") or f"/app{model_url}"

                    logger.info(f"  Model: {model_url[:60]}...")
                    logger.info(f"  Garment: {cloth['image_url'][:60]}...")

                    # Use REAL Virtual Try-On API (Kling AI via PiAPI)
                    # PiAPIClient automatically converts local files to base64 data URLs
                    tryon_result = await self.piapi.virtual_try_on(
                        model_image_url=model_url,
                        garment_image_url=cloth["image_url"]
                    )

                    if not tryon_result.get("success"):
                        logger.error(f"  Try-On Failed: {tryon_result.get('error')}")
                        # Fallback to T2I if Try-On API fails
                        logger.info("  Falling back to T2I generation...")
                        prompt = f"Professional fashion photography of a {model_data['gender']} model wearing {cloth['prompt']}, studio lighting, full body shot, high quality, 8K"
                        tryon_result = await self.piapi.generate_image(prompt=prompt)

                        if not tryon_result.get("success"):
                            logger.error(f"  Fallback T2I also failed: {tryon_result.get('error')}")
                            self.stats["failed"] += 1
                            self.stats["by_tool"]["try_on"]["failed"] += 1
                            count += 1
                            continue

                    # Extract result image URL
                    result_url = tryon_result.get("image_url") or tryon_result.get("output", {}).get("image_url")
                    if not result_url:
                        # Try to get from images array
                        images = tryon_result.get("output", {}).get("images", [])
                        if images:
                            result_url = images[0].get("url") if isinstance(images[0], dict) else images[0]

                    if not result_url:
                        logger.error("  No result URL in response")
                        self.stats["failed"] += 1
                        self.stats["by_tool"]["try_on"]["failed"] += 1
                        count += 1
                        continue

                    # IMPORTANT: input_image_url is the CLOTHING preview image
                    local_entry = {
                        "topic": topic,
                        "prompt": cloth["name"],
                        "prompt_zh": cloth.get("name_zh", cloth["name"]),
                        "input_image_url": cloth["image_url"],  # CLOTHING preview
                        "result_image_url": result_url,   # Model wearing clothing (REAL try-on)
                        "input_params": {
                            "model_id": model_id,
                            "model_url": model_data["url"],
                            "clothing_id": cloth["id"],
                            "clothing_type": cloth.get("clothing_type", "general"),
                            "gender_restriction": gender_restriction
                        },
                        "style_tags": [topic, cloth.get("clothing_type", "general")],
                        "generation_cost": 0.07  # Kling AI Try-On cost: $0.07 per image
                    }
                    self.local_results["try_on"].append(local_entry)

                    logger.info(f"  Success: {result_url}")
                    self.stats["success"] += 1
                    self.stats["by_tool"]["try_on"]["success"] += 1
                    count += 1
                    await asyncio.sleep(2)  # Rate limiting for Kling API

        await self._store_local_to_db("try_on")

    # ========================================================================
    # PATTERN GENERATOR
    # ========================================================================

    async def generate_pattern(self, limit: int = 10):
        """
        Generate Pattern designs.

        Combinations: Style × Prompt
        Total: 5 styles × 2 prompts = 10
        """
        logger.info("=" * 60)
        logger.info("PATTERN GENERATE - Style × Prompt")
        logger.info("=" * 60)

        self.stats["by_tool"]["pattern_generate"] = {"success": 0, "failed": 0}
        self.local_results["pattern_generate"] = []
        count = 0

        styles = PATTERN_GENERATE_MAPPING["styles"]

        for style_id, style_data in styles.items():
            if count >= limit:
                break

            for prompt_data in style_data["prompts"]:
                if count >= limit:
                    break

                prompt_en = prompt_data["en"]
                prompt_zh = prompt_data["zh"]

                logger.info(f"[{count+1}] Style: {style_data['name']} ({style_id})")
                logger.info(f"  Prompt: {prompt_en[:50]}...")

                full_prompt = f"Seamless pattern design, {prompt_en}, tileable, high quality, 8K"

                t2i = await self.piapi.generate_image(prompt=full_prompt, width=1024, height=1024)

                if not t2i["success"]:
                    logger.error(f"  T2I Failed: {t2i.get('error')}")
                    self.stats["failed"] += 1
                    self.stats["by_tool"]["pattern_generate"]["failed"] += 1
                    count += 1
                    continue

                local_entry = {
                    "topic": style_id,
                    "prompt": prompt_en,
                    "prompt_zh": prompt_zh,
                    "result_image_url": t2i["image_url"],
                    "input_params": {
                        "style_id": style_id,
                        "style_name": style_data["name"]
                    },
                    "style_tags": [style_id, "pattern", "seamless"],
                    "generation_cost": 0.005
                }
                self.local_results["pattern_generate"].append(local_entry)

                logger.info(f"  Success: {t2i['image_url']}")
                self.stats["success"] += 1
                self.stats["by_tool"]["pattern_generate"]["success"] += 1
                count += 1
                await asyncio.sleep(1)

        await self._store_local_to_db("pattern_generate")

    # ========================================================================
    # MODEL LIBRARY GENERATOR (NEW)
    # ========================================================================

    async def generate_model_library(self, limit: int = 6):
        """
        Generate full-body model photos for Virtual Try-On.

        This creates a library of AI-generated model photos that meet
        Kling AI Virtual Try-On requirements:
        - Full body shot (head to at least waist visible)
        - Clear visibility of upper body/torso
        - Neutral pose with arms at sides
        - Plain background
        - Simple base clothing

        These models are stored locally and reused for all try-on generations.

        Args:
            limit: Total number of models to generate (split between male/female)
        """
        logger.info("=" * 60)
        logger.info("MODEL LIBRARY - AI-Generated Full Body Models")
        logger.info("For Kling AI Virtual Try-On compatibility")
        logger.info("=" * 60)

        self.stats["by_tool"]["model_library"] = {"success": 0, "failed": 0}
        count = 0

        for gender, prompts in MODEL_GENERATION_PROMPTS.items():
            gender_dir = self.MODEL_LIBRARY_DIR / gender
            gender_dir.mkdir(parents=True, exist_ok=True)

            for prompt_data in prompts:
                if count >= limit:
                    break

                model_id = prompt_data["id"]
                output_path = gender_dir / f"{model_id}.png"

                # Skip if already exists
                if output_path.exists():
                    logger.info(f"[{count+1}] Model {model_id} already exists, skipping")
                    # Make sure it's in the library
                    GENERATED_MODEL_LIBRARY[model_id] = {
                        "gender": gender,
                        "url": f"/static/models/{gender}/{model_id}.png",
                        "local_path": str(output_path)
                    }
                    count += 1
                    continue

                logger.info(f"[{count+1}] Generating: {prompt_data['description']}")
                logger.info(f"  ID: {model_id}")

                # Generate with PiAPI T2I - use portrait dimensions (taller than wide)
                t2i = await self.piapi.generate_image(
                    prompt=prompt_data["prompt"],
                    width=768,   # Portrait width
                    height=1152  # Portrait height (3:2 aspect ratio, taller)
                )

                if not t2i["success"]:
                    logger.error(f"  Failed: {t2i.get('error')}")
                    self.stats["failed"] += 1
                    self.stats["by_tool"]["model_library"]["failed"] += 1
                    count += 1
                    continue

                # Move/copy to model library
                source_url = t2i["image_url"]
                if source_url.startswith("/static/generated/"):
                    source_path = Path(f"/app{source_url}")
                    if source_path.exists():
                        shutil.copy(source_path, output_path)
                        logger.info(f"  Saved to: {output_path}")
                    else:
                        logger.error(f"  Source file not found: {source_path}")
                        self.stats["failed"] += 1
                        self.stats["by_tool"]["model_library"]["failed"] += 1
                        count += 1
                        continue
                else:
                    # Download from remote URL
                    try:
                        import httpx
                        async with httpx.AsyncClient() as client:
                            response = await client.get(source_url, follow_redirects=True)
                            if response.status_code == 200:
                                output_path.write_bytes(response.content)
                                logger.info(f"  Downloaded to: {output_path}")
                            else:
                                logger.error(f"  Download failed: HTTP {response.status_code}")
                                continue
                    except Exception as e:
                        logger.error(f"  Download failed: {e}")
                        continue

                # Add to library
                GENERATED_MODEL_LIBRARY[model_id] = {
                    "gender": gender,
                    "url": f"/static/models/{gender}/{model_id}.png",
                    "local_path": str(output_path)
                }

                logger.info(f"  Success: Model {model_id} added to library")
                self.stats["success"] += 1
                self.stats["by_tool"]["model_library"]["success"] += 1
                count += 1
                await asyncio.sleep(2)

        # Update TRYON_MAPPING with new models
        if GENERATED_MODEL_LIBRARY:
            TRYON_MAPPING["models"] = GENERATED_MODEL_LIBRARY.copy()
            logger.info(f"\nModel library now has {len(GENERATED_MODEL_LIBRARY)} models")
        else:
            logger.warning("No models generated, using fallback models")
            TRYON_MAPPING["models"] = TRYON_FALLBACK_MODELS.copy()

    # ========================================================================
    # DATABASE STORAGE
    # ========================================================================

    async def _store_local_to_db(self, tool_name: str):
        """Store locally collected results to database."""
        tool_type_map = {
            "ai_avatar": ToolType.AI_AVATAR,
            "background_removal": ToolType.BACKGROUND_REMOVAL,
            "room_redesign": ToolType.ROOM_REDESIGN,
            "short_video": ToolType.SHORT_VIDEO,
            "product_scene": ToolType.PRODUCT_SCENE,
            "try_on": ToolType.TRY_ON,
            "pattern_generate": ToolType.PATTERN_GENERATE
        }

        if tool_name not in self.local_results:
            return

        entries = self.local_results[tool_name]
        if not entries:
            logger.info(f"No entries to store for {tool_name}")
            return

        logger.info(f"Storing {len(entries)} {tool_name} entries to database...")

        async with AsyncSessionLocal() as session:
            stored_count = 0
            for entry in entries:
                lookup_hash = self._generate_lookup_hash(
                    tool_type=tool_name,
                    prompt=entry["prompt"],
                    input_image_url=entry.get("input_image_url")
                )

                # Check if already exists
                existing = await session.execute(
                    select(Material).where(Material.lookup_hash == lookup_hash)
                )
                if existing.scalar_one_or_none():
                    logger.debug(f"  Already exists: {lookup_hash[:16]}...")
                    continue

                # Merge metadata into input_params if exists
                input_params = entry.get("input_params", {})
                if entry.get("metadata"):
                    input_params.update(entry["metadata"])

                material = Material(
                    lookup_hash=lookup_hash,
                    tool_type=tool_type_map[tool_name],
                    topic=entry["topic"],
                    language=entry.get("language", "en"),
                    source=MaterialSource.SEED,
                    status=MaterialStatus.APPROVED,
                    prompt=entry["prompt"],
                    prompt_zh=entry.get("prompt_zh"),
                    input_image_url=entry.get("input_image_url"),
                    input_params=input_params,
                    generation_steps=entry.get("generation_steps", []),
                    generation_cost_usd=entry.get("generation_cost", 0),
                    result_image_url=entry.get("result_image_url"),
                    result_video_url=entry.get("result_video_url"),
                    result_watermarked_url=entry.get("result_video_url") or entry.get("result_image_url"),
                    tags=entry.get("style_tags", []),
                    quality_score=0.9,
                    is_featured=True,
                    is_active=True
                )
                session.add(material)
                stored_count += 1

            await session.commit()
            logger.info(f"  Stored {stored_count} new entries")

        # Clear local results after storing
        self.local_results[tool_name] = []

    # ========================================================================
    # MAIN ENTRY
    # ========================================================================

    async def run(
        self,
        tool: Optional[str] = None,
        limit: int = 10,
        dry_run: bool = False
    ):
        """Run pre-generation pipeline."""
        logger.info("=" * 60)
        logger.info("VidGo Main Pre-generation Pipeline")
        logger.info("=" * 60)

        # Check APIs
        api_status = await self.check_apis()
        logger.info(f"API Status: {api_status}")

        if dry_run:
            logger.info("[DRY RUN] Would generate materials but not calling APIs")
            logger.info("Available tools:")
            for t in ["ai_avatar", "background_removal", "room_redesign",
                      "short_video", "product_scene", "try_on", "pattern_generate",
                      "model_library"]:
                logger.info(f"  - {t}")
            logger.info("\nModel Library Status:")
            logger.info(f"  Generated models: {len(GENERATED_MODEL_LIBRARY)}")
            logger.info(f"  Using fallback: {len(GENERATED_MODEL_LIBRARY) == 0}")
            return

        # Ensure temp directory
        ensure_temp_dir()

        # Tool mapping
        tools = {
            "model_library": self.generate_model_library,  # NEW: Run first to generate models
            "ai_avatar": self.generate_ai_avatar,
            "background_removal": self.generate_background_removal,
            "room_redesign": self.generate_room_redesign,
            "short_video": self.generate_short_video,
            "product_scene": self.generate_product_scene,
            "try_on": self.generate_try_on,
            "pattern_generate": self.generate_pattern,
        }

        if tool:
            if tool in tools:
                # Special handling: if running try_on, ensure model library exists first
                if tool == "try_on" and len(GENERATED_MODEL_LIBRARY) == 0:
                    logger.info("No model library found, generating models first...")
                    await self.generate_model_library(limit=6)

                await tools[tool](limit=limit)
            else:
                logger.error(f"Unknown tool: {tool}")
                logger.info(f"Available tools: {list(tools.keys())}")
        else:
            # Run all tools (model_library first, then others)
            # Generate model library first so try_on can use it
            await self.generate_model_library(limit=6)

            for name, func in tools.items():
                if name == "model_library":
                    continue  # Already ran
                try:
                    await func(limit=limit)
                except Exception as e:
                    logger.error(f"Error in {name}: {e}")

        # Cleanup temp
        cleanup_temp_dir()

        # Summary
        logger.info("\n" + "=" * 60)
        logger.info("SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Total Success: {self.stats['success']}")
        logger.info(f"Total Failed: {self.stats['failed']}")
        for tool_name, tool_stats in self.stats["by_tool"].items():
            logger.info(f"  {tool_name}: {tool_stats['success']} success, {tool_stats['failed']} failed")


# ============================================================================
# CLI ENTRY POINT
# ============================================================================

async def main():
    parser = argparse.ArgumentParser(
        description="VidGo Main Pre-generation Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python -m scripts.main_pregenerate --tool model_library --limit 6
    python -m scripts.main_pregenerate --tool try_on --limit 50
    python -m scripts.main_pregenerate --tool ai_avatar --limit 10
    python -m scripts.main_pregenerate --all --limit 20
    python -m scripts.main_pregenerate --dry-run

Available tools:
    model_library      - Generate full-body model photos for try-on (NEW)
    ai_avatar          - AI Avatar videos (avatar × script × language)
    background_removal - Background removal (T2I → rembg)
    room_redesign      - Room redesign (room × style)
    short_video        - Short videos (Pollo T2V)
    product_scene      - Product scenes (product × scene)
    try_on             - Virtual try-on (model × clothing) - uses model_library
    pattern_generate   - Pattern designs (style × prompt)

Workflow for Virtual Try-On:
    1. First run: python -m scripts.main_pregenerate --tool model_library
       This generates AI full-body model photos that meet Kling AI requirements.

    2. Then run: python -m scripts.main_pregenerate --tool try_on
       This uses the generated models for real virtual try-on.

    Note: Running --tool try_on without model_library will auto-generate models first.
        """
    )
    parser.add_argument(
        "--tool",
        type=str,
        help="Specific tool to generate (see list above)"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Max materials per tool (default: 10)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be generated without calling APIs"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Generate all tools"
    )

    args = parser.parse_args()

    generator = VidGoPreGenerator()
    await generator.run(
        tool=args.tool if not args.all else None,
        limit=args.limit,
        dry_run=args.dry_run
    )


if __name__ == "__main__":
    asyncio.run(main())
