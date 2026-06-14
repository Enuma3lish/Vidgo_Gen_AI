"""
Material Library Services Module

Handles asset/material management for showcases, demos, and user-generated content.
"""
from .library import MaterialLibraryService, get_material_library
from .collector import UserContentCollector, get_content_collector
from .requirements import MATERIAL_REQUIREMENTS, get_tool_requirements, get_all_tool_ids
from .generator import RealShowcaseGenerator, GenerationProgress

__all__ = [
    "MaterialLibraryService",
    "get_material_library",
    "UserContentCollector",
    "get_content_collector",
    "MATERIAL_REQUIREMENTS",
    "get_tool_requirements",
    "get_all_tool_ids",
    "RealShowcaseGenerator",
    "GenerationProgress",
]
