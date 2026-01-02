"""
Base service interfaces and abstract classes for modular service architecture.
"""
from .generation import BaseGenerationService, GenerationResult, GenerationType
from .material import BaseMaterialService, MaterialType, MaterialStatus, MaterialItem, MaterialRequirement

__all__ = [
    "BaseGenerationService",
    "GenerationResult",
    "GenerationType",
    "BaseMaterialService",
    "MaterialType",
    "MaterialStatus",
    "MaterialItem",
    "MaterialRequirement",
]
