"""
Material Requirements Configuration

Defines minimum material requirements for each tool category and tool.
These requirements determine when showcase generation is needed.
"""
from typing import Dict, List, Optional
from dataclasses import dataclass


@dataclass
class ToolRequirement:
    """Requirements for a specific tool"""
    tool_id: str
    tool_name: str
    tool_name_zh: str
    min_showcases: int = 30  # Minimum showcase examples (30 per tool as per requirement)
    min_featured: int = 5    # Minimum featured examples
    generation_type: str = "image"  # "image" or "video"
    requires_source_image: bool = True
    default_prompts: List[Dict[str, str]] = None  # Seed prompts for generation

    def __post_init__(self):
        if self.default_prompts is None:
            self.default_prompts = []


@dataclass
class CategoryRequirement:
    """Requirements for a tool category"""
    category_id: str
    category_name: str
    category_name_zh: str
    tools: List[ToolRequirement]


# Complete material requirements for all tool categories
MATERIAL_REQUIREMENTS: Dict[str, CategoryRequirement] = {
    # ==========================================================================
    # EDIT TOOLS
    # ==========================================================================
    "edit_tools": CategoryRequirement(
        category_id="edit_tools",
        category_name="Edit Tools",
        category_name_zh="編輯工具",
        tools=[
            ToolRequirement(
                tool_id="universal_edit",
                tool_name="Universal Edit",
                tool_name_zh="萬能改圖",
                min_showcases=30,
                generation_type="image",
                default_prompts=[
                    {"prompt": "Change the sky to dramatic sunset with orange and purple clouds",
                     "prompt_zh": "將天空改為戲劇性的日落，橙色和紫色的雲彩"},
                    {"prompt": "Add a rainbow arching over the scene",
                     "prompt_zh": "在場景上方添加彩虹"},
                    {"prompt": "Transform daytime scene to night with stars and moon",
                     "prompt_zh": "將日間場景轉換為有星星和月亮的夜晚"},
                ]
            ),
            ToolRequirement(
                tool_id="hd_upscale",
                tool_name="HD Upscale",
                tool_name_zh="高清放大",
                min_showcases=30,
                generation_type="image",
                default_prompts=[
                    {"prompt": "Enhance to 4K resolution with improved sharpness and detail",
                     "prompt_zh": "增強至4K解析度，提升銳利度和細節"},
                ]
            ),
            ToolRequirement(
                tool_id="ai_cutout",
                tool_name="AI Cutout",
                tool_name_zh="AI摳圖",
                min_showcases=30,
                generation_type="image",
                default_prompts=[
                    {"prompt": "Remove background and isolate the main subject",
                     "prompt_zh": "移除背景並隔離主體"},
                ]
            ),
            ToolRequirement(
                tool_id="change_bg",
                tool_name="Change Background",
                tool_name_zh="換背景",
                min_showcases=30,
                generation_type="image",
                default_prompts=[
                    {"prompt": "Replace background with pure white for e-commerce",
                     "prompt_zh": "將背景替換為純白色用於電商"},
                    {"prompt": "Place subject in modern office environment",
                     "prompt_zh": "將主體放置在現代辦公室環境中"},
                ]
            ),
            ToolRequirement(
                tool_id="photo_cartoon",
                tool_name="Photo to Cartoon",
                tool_name_zh="真人轉漫畫",
                min_showcases=30,
                generation_type="image",
                default_prompts=[
                    {"prompt": "Transform to anime style with vibrant colors",
                     "prompt_zh": "轉換為動漫風格，鮮艷色彩"},
                    {"prompt": "Convert to Pixar 3D cartoon style",
                     "prompt_zh": "轉換為皮克斯3D卡通風格"},
                ]
            ),
            ToolRequirement(
                tool_id="ai_expand",
                tool_name="AI Expand",
                tool_name_zh="AI擴圖",
                min_showcases=30,
                generation_type="image",
                default_prompts=[
                    {"prompt": "Expand image borders to show more of the scene",
                     "prompt_zh": "擴展圖片邊界以顯示更多場景"},
                ]
            ),
        ]
    ),

    # ==========================================================================
    # E-COMMERCE
    # ==========================================================================
    "ecommerce": CategoryRequirement(
        category_id="ecommerce",
        category_name="E-Commerce",
        category_name_zh="產品電商",
        tools=[
            ToolRequirement(
                tool_id="product_design",
                tool_name="Product Design",
                tool_name_zh="AI產品設計",
                min_showcases=30,
                min_featured=5,
                generation_type="video",  # This tool generates videos
                default_prompts=[
                    {"prompt": "Create luxury product commercial with elegant rotation and spotlight",
                     "prompt_zh": "創建豪華產品廣告，優雅旋轉和聚光燈效果"},
                    {"prompt": "Product showcase with dynamic lighting and floating effect",
                     "prompt_zh": "產品展示，動態燈光和漂浮效果"},
                    {"prompt": "Cinematic product reveal with particle effects",
                     "prompt_zh": "電影級產品揭示，粒子效果"},
                ]
            ),
            ToolRequirement(
                tool_id="white_bg",
                tool_name="White Background",
                tool_name_zh="一鍵白底圖",
                min_showcases=30,
                generation_type="image",
                default_prompts=[
                    {"prompt": "Remove background and place on pure white for product listing",
                     "prompt_zh": "移除背景並放在純白背景上用於產品上架"},
                ]
            ),
            ToolRequirement(
                tool_id="scene_gen",
                tool_name="Scene Generation",
                tool_name_zh="場景圖生成",
                min_showcases=30,
                generation_type="image",
                default_prompts=[
                    {"prompt": "Place product in cozy morning scene with warm lighting",
                     "prompt_zh": "將產品放在溫馨的早晨場景中，暖色照明"},
                    {"prompt": "Create lifestyle setting with natural elements",
                     "prompt_zh": "創建具有自然元素的生活方式場景"},
                ]
            ),
            ToolRequirement(
                tool_id="model_tryon",
                tool_name="Model Try-on",
                tool_name_zh="模特試衣",
                min_showcases=30,
                generation_type="image",
                default_prompts=[
                    {"prompt": "Show clothing on professional model with studio lighting",
                     "prompt_zh": "在專業模特身上展示服裝，攝影棚燈光"},
                ]
            ),
        ]
    ),

    # ==========================================================================
    # ARCHITECTURE
    # ==========================================================================
    "architecture": CategoryRequirement(
        category_id="architecture",
        category_name="Architecture",
        category_name_zh="建築設計",
        tools=[
            ToolRequirement(
                tool_id="ai_concept",
                tool_name="AI Concept",
                tool_name_zh="AI概念圖",
                min_showcases=30,
                generation_type="image",
                default_prompts=[
                    {"prompt": "Generate modern architectural concept with glass facade",
                     "prompt_zh": "生成帶玻璃幕牆的現代建築概念"},
                    {"prompt": "Create futuristic building design with sustainable features",
                     "prompt_zh": "創建具有可持續特性的未來派建築設計"},
                ]
            ),
            ToolRequirement(
                tool_id="3d_render",
                tool_name="3D Render",
                tool_name_zh="3D渲染",
                min_showcases=30,
                generation_type="image",
                default_prompts=[
                    {"prompt": "Create photorealistic 3D render with marble countertops",
                     "prompt_zh": "創建帶大理石檯面的逼真3D渲染"},
                    {"prompt": "Render cozy interior with warm lighting and plants",
                     "prompt_zh": "渲染溫馨室內，暖色照明和植物"},
                ]
            ),
            ToolRequirement(
                tool_id="style_convert",
                tool_name="Style Convert",
                tool_name_zh="風格轉換",
                min_showcases=30,
                generation_type="image",
                default_prompts=[
                    {"prompt": "Convert to Mediterranean style with terracotta roof",
                     "prompt_zh": "轉換為地中海風格，陶瓦屋頂"},
                    {"prompt": "Transform to minimalist Japanese design",
                     "prompt_zh": "轉換為日式極簡設計"},
                ]
            ),
            ToolRequirement(
                tool_id="floor_plan",
                tool_name="Floor Plan",
                tool_name_zh="彩平圖",
                min_showcases=30,
                generation_type="image",
                default_prompts=[
                    {"prompt": "Enhance floor plan with furniture layout and colors",
                     "prompt_zh": "增強平面圖，添加家具佈局和顏色"},
                ]
            ),
        ]
    ),

    # ==========================================================================
    # PORTRAIT
    # ==========================================================================
    "portrait": CategoryRequirement(
        category_id="portrait",
        category_name="Portrait",
        category_name_zh="人像寫真",
        tools=[
            ToolRequirement(
                tool_id="face_swap",
                tool_name="Face Swap",
                tool_name_zh="人像換臉",
                min_showcases=30,
                generation_type="image",
                default_prompts=[
                    {"prompt": "Swap face while preserving natural lighting and expressions",
                     "prompt_zh": "換臉同時保留自然光線和表情"},
                ]
            ),
            ToolRequirement(
                tool_id="photo_restore",
                tool_name="Photo Restore",
                tool_name_zh="老照片修復",
                min_showcases=30,
                generation_type="image",
                default_prompts=[
                    {"prompt": "Restore photo, remove scratches, enhance clarity and add color",
                     "prompt_zh": "修復照片，去除劃痕，增強清晰度並添加色彩"},
                ]
            ),
            ToolRequirement(
                tool_id="ai_portrait",
                tool_name="AI Portrait",
                tool_name_zh="AI寫真",
                min_showcases=30,
                generation_type="image",
                default_prompts=[
                    {"prompt": "Create artistic portrait with professional studio lighting",
                     "prompt_zh": "創建藝術人像，專業攝影棚燈光"},
                    {"prompt": "Transform to oil painting style portrait",
                     "prompt_zh": "轉換為油畫風格人像"},
                ]
            ),
        ]
    ),
}


def get_tool_requirements(
    category_id: Optional[str] = None,
    tool_id: Optional[str] = None
) -> List[ToolRequirement]:
    """
    Get tool requirements filtered by category and/or tool.

    Args:
        category_id: Filter by category
        tool_id: Filter by specific tool

    Returns:
        List of ToolRequirement
    """
    requirements = []

    categories = [MATERIAL_REQUIREMENTS[category_id]] if category_id else MATERIAL_REQUIREMENTS.values()

    for category in categories:
        for tool in category.tools:
            if tool_id is None or tool.tool_id == tool_id:
                requirements.append(tool)

    return requirements


def get_all_tool_ids() -> List[str]:
    """Get all tool IDs across all categories"""
    tool_ids = []
    for category in MATERIAL_REQUIREMENTS.values():
        for tool in category.tools:
            tool_ids.append(tool.tool_id)
    return tool_ids


def get_total_required_showcases() -> int:
    """Calculate total minimum showcases needed"""
    total = 0
    for category in MATERIAL_REQUIREMENTS.values():
        for tool in category.tools:
            total += tool.min_showcases
    return total
