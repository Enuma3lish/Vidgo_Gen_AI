"""
Generation Service Factory

Provides unified access to all generation services and handles service selection.
"""
import logging
from typing import Optional, Dict, Type

from app.services.base import BaseGenerationService, GenerationType
from .goenhance_service import GoEnhanceGenerationService, get_goenhance_service
from .pollo_service import PolloGenerationService, get_pollo_service
from .leonardo_service import LeonardoGenerationService, get_leonardo_service

logger = logging.getLogger(__name__)


class GenerationServiceFactory:
    """
    Factory for creating and managing generation services.

    Provides:
    - Service selection by name or capability
    - Optimal service selection for generation types
    - Service fallback handling
    """

    # Service registry
    _services: Dict[str, Type[BaseGenerationService]] = {
        "goenhance": GoEnhanceGenerationService,
        "pollo_ai": PolloGenerationService,
        "leonardo": LeonardoGenerationService,
    }

    # Preferred services for each generation type
    _preferred_services: Dict[GenerationType, list] = {
        GenerationType.TEXT_TO_IMAGE: ["leonardo", "goenhance"],
        GenerationType.IMAGE_TO_IMAGE: ["goenhance"],
        GenerationType.IMAGE_TO_VIDEO: ["pollo_ai", "leonardo"],
        GenerationType.VIDEO_TO_VIDEO: ["goenhance"],
        GenerationType.IMAGE_UPSCALE: ["goenhance"],
        GenerationType.VIDEO_UPSCALE: ["goenhance"],
    }

    @classmethod
    def get_service(cls, service_name: str) -> Optional[BaseGenerationService]:
        """
        Get a specific generation service by name.

        Args:
            service_name: Service identifier (goenhance, pollo_ai, leonardo)

        Returns:
            BaseGenerationService instance or None
        """
        if service_name == "goenhance":
            return get_goenhance_service()
        elif service_name == "pollo_ai":
            return get_pollo_service()
        elif service_name == "leonardo":
            return get_leonardo_service()
        else:
            logger.warning(f"Unknown service: {service_name}")
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
            "goenhance": get_goenhance_service(),
            "pollo_ai": get_pollo_service(),
            "leonardo": get_leonardo_service(),
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
        # Default to Leonardo for general use
        return get_leonardo_service()
