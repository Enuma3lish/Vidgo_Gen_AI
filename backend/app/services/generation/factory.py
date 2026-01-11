"""
Generation Service Factory

Provides unified access to all generation services and handles service selection.
NOTE: This is legacy code - prefer using ProviderRouter for new implementations.
"""
import logging
from typing import Optional, Dict, Type

from app.services.base import BaseGenerationService, GenerationType
from .pollo_service import PolloGenerationService, get_pollo_service

logger = logging.getLogger(__name__)


class GenerationServiceFactory:
    """
    Factory for creating and managing generation services.

    NOTE: Prefer using ProviderRouter instead. This factory is kept for
    backward compatibility with existing code. Use ProviderRouter with
    PiAPI for T2I, I2V, T2V, V2V, Interior, and Background Removal.

    Provides:
    - Service selection by name or capability
    - Optimal service selection for generation types
    - Service fallback handling
    """

    # Service registry - Use ProviderRouter with PiAPI for most operations
    _services: Dict[str, Type[BaseGenerationService]] = {
        "pollo_ai": PolloGenerationService,
    }

    # Preferred services for each generation type
    # NOTE: Use ProviderRouter (PiAPI primary) for T2I, I2V, T2V, V2V, Interior
    _preferred_services: Dict[GenerationType, list] = {
        GenerationType.TEXT_TO_IMAGE: ["pollo_ai"],
        GenerationType.IMAGE_TO_IMAGE: ["pollo_ai"],
        GenerationType.IMAGE_TO_VIDEO: ["pollo_ai"],
        GenerationType.VIDEO_TO_VIDEO: ["pollo_ai"],
        GenerationType.IMAGE_UPSCALE: ["pollo_ai"],
        GenerationType.VIDEO_UPSCALE: ["pollo_ai"],
    }

    @classmethod
    def get_service(cls, service_name: str) -> Optional[BaseGenerationService]:
        """
        Get a specific generation service by name.

        Args:
            service_name: Service identifier (pollo_ai)

        Returns:
            BaseGenerationService instance or None
        """
        if service_name == "pollo_ai":
            return get_pollo_service()
        else:
            logger.warning(f"Unknown service: {service_name}. Use ProviderRouter instead.")
            return None

    @classmethod
    def get_service_for_type(
        cls,
        generation_type: GenerationType,
        preferred: Optional[str] = None
    ) -> Optional[BaseGenerationService]:
        """
        Get the best service for a generation type.

        Args:
            generation_type: Type of generation needed
            preferred: Optional preferred service name

        Returns:
            Best available BaseGenerationService for the type
        """
        # If preferred service is specified and supports the type, use it
        if preferred:
            service = cls.get_service(preferred)
            if service and generation_type in service.supported_types:
                return service

        # Get from preference list
        preferred_list = cls._preferred_services.get(generation_type, [])

        for service_name in preferred_list:
            service = cls.get_service(service_name)
            if service and generation_type in service.supported_types:
                return service

        logger.error(f"No service available for generation type: {generation_type}")
        return None

    @classmethod
    def get_all_services(cls) -> Dict[str, BaseGenerationService]:
        """Get all available services"""
        return {
            "pollo_ai": get_pollo_service(),
        }

    @classmethod
    def get_capabilities(cls) -> Dict[str, list]:
        """Get capabilities of all services"""
        capabilities = {}
        for name, service in cls.get_all_services().items():
            capabilities[name] = [gt.value for gt in service.supported_types]
        return capabilities


def get_generation_service(
    service_name: Optional[str] = None,
    generation_type: Optional[GenerationType] = None
) -> Optional[BaseGenerationService]:
    """
    Convenience function to get a generation service.

    NOTE: Prefer using ProviderRouter for new implementations.
    Use ProviderRouter with PiAPI for T2I, I2V, T2V, V2V, Interior.

    Args:
        service_name: Specific service to get
        generation_type: Type of generation (if no service specified, finds best match)

    Returns:
        BaseGenerationService instance
    """
    if service_name:
        return GenerationServiceFactory.get_service(service_name)
    elif generation_type:
        return GenerationServiceFactory.get_service_for_type(generation_type)
    else:
        # Default to Pollo for legacy compatibility
        return get_pollo_service()
