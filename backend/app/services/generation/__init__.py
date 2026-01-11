"""
Generation Services Module

Provides unified interfaces for all AI generation providers.
NOTE: This is legacy code - prefer using ProviderRouter for new implementations.
"""
from .pollo_service import PolloGenerationService
from .factory import GenerationServiceFactory, get_generation_service

__all__ = [
    "PolloGenerationService",
    "GenerationServiceFactory",
    "get_generation_service",
]
