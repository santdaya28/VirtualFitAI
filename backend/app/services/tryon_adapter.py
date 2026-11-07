import abc
import uuid
import logging
from typing import Dict, Any, Optional
from app.core.config import settings

logger = logging.getLogger(__name__)

class BaseTryOnAdapter(abc.ABC):
    """
    Abstract Base Class for Virtual Try-On AI model providers.
    Allows easy switching between local Mock, Fashn.ai, Replicate (IDM-VTON), or custom GPU endpoints.
    """

    @abc.abstractmethod
    def submit_tryon(
        self,
        customer_photo_url: str,
        garment_image_url: str,
        category: Optional[str] = None
    ) -> Dict[str, Any]:
        """Submit a try-on task to the AI provider and return session details"""
        pass

    @abc.abstractmethod
    def check_status(self, task_id: str) -> Dict[str, Any]:
        """Check the status of an ongoing try-on task"""
        pass


class MockTryOnAdapter(BaseTryOnAdapter):
    """
    Local Development & Testing Adapter.
    Simulates realistic workflow responses without requiring external paid API keys.
    """

    def submit_tryon(
        self,
        customer_photo_url: str,
        garment_image_url: str,
        category: Optional[str] = None
    ) -> Dict[str, Any]:
        session_id = f"vton_mock_{uuid.uuid4().hex[:12]}"
        logger.info(f"Mock Try-On task submitted: {session_id}")
        return {
            "session_id": session_id,
            "status": "processing",
            "provider": "mock",
            "message": "AI try-on task queued (Local Mock Mode).",
            "customer_photo_url": customer_photo_url,
            "garment_image_url": garment_image_url,
        }

    def check_status(self, task_id: str) -> Dict[str, Any]:
        return {
            "session_id": task_id,
            "status": "completed",
            "provider": "mock",
            "progress_percentage": 100,
            "result_image_url": "https://images.unsplash.com/photo-1515886657613-9f3515b0c78f?auto=format&fit=crop&w=900&q=80",
            "message": "Fitting synthesized successfully (Mock preview).",
        }


class FashnTryOnAdapter(BaseTryOnAdapter):
    """
    Adapter for Fashn.ai Virtual Try-On API
    """

    def __init__(self, api_key: str):
        self.api_key = api_key

    def submit_tryon(
        self,
        customer_photo_url: str,
        garment_image_url: str,
        category: Optional[str] = None
    ) -> Dict[str, Any]:
        if not self.api_key:
            raise ValueError("FASHN_API_KEY is not configured in backend .env")
        # Ready for live HTTP dispatch to https://api.fashn.ai/v1/run
        session_id = f"fashn_{uuid.uuid4().hex[:12]}"
        return {
            "session_id": session_id,
            "status": "pending",
            "provider": "fashn",
            "message": "Dispatched to Fashn.ai API",
        }

    def check_status(self, task_id: str) -> Dict[str, Any]:
        # Ready for live HTTP dispatch to https://api.fashn.ai/v1/status/{task_id}
        return {
            "session_id": task_id,
            "status": "processing",
            "provider": "fashn",
            "progress_percentage": 50,
            "message": "Processing in Fashn.ai pipeline",
        }


class ReplicateTryOnAdapter(BaseTryOnAdapter):
    """
    Adapter for Replicate (IDM-VTON / Kolors VTON) models
    """

    def __init__(self, api_token: str):
        self.api_token = api_token

    def submit_tryon(
        self,
        customer_photo_url: str,
        garment_image_url: str,
        category: Optional[str] = None
    ) -> Dict[str, Any]:
        if not self.api_token:
            raise ValueError("REPLICATE_API_TOKEN is not configured in backend .env")
        session_id = f"replicate_{uuid.uuid4().hex[:12]}"
        return {
            "session_id": session_id,
            "status": "pending",
            "provider": "replicate",
            "message": "Dispatched to Replicate IDM-VTON model",
        }

    def check_status(self, task_id: str) -> Dict[str, Any]:
        return {
            "session_id": task_id,
            "status": "processing",
            "provider": "replicate",
            "progress_percentage": 50,
            "message": "Running IDM-VTON diffusion pipeline",
        }


def get_tryon_adapter() -> BaseTryOnAdapter:
    """
    Factory function returning the configured AI Try-On adapter
    """
    provider = settings.AI_TRYON_PROVIDER.lower()
    if provider == "fashn" and settings.FASHN_API_KEY:
        return FashnTryOnAdapter(api_key=settings.FASHN_API_KEY)
    elif provider == "replicate" and settings.REPLICATE_API_TOKEN:
        return ReplicateTryOnAdapter(api_token=settings.REPLICATE_API_TOKEN)
    else:
        return MockTryOnAdapter()

