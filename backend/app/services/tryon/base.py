"""
Provider-Independent Base Interface for VirtualFit AI Virtual Try-On.

Defines the abstract contract that all Virtual Try-On providers (Mock, Fashn, Replicate, custom GPUs)
must implement. Ensures decoupling between database/API routers and AI vendor backends.
"""
import abc
from dataclasses import dataclass, field
from typing import Optional, Dict, Any


@dataclass
class TryOnExecutionResult:
    """
    Structured outcome of a Virtual Try-On task or status inquiry.
    Independent of any specific AI vendor data structure.
    """
    session_id: str
    status: str  # "pending", "processing", "completed", "failed"
    progress_percentage: int  # 0 - 100
    stage_message: str
    provider: str
    result_image_url: Optional[str] = None
    error_message: Optional[str] = None
    error_category: Optional[str] = None
    retry_after_seconds: Optional[int] = None
    quota_resets_at: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_completed(self) -> bool:
        return self.status == "completed"

    @property
    def is_failed(self) -> bool:
        return self.status == "failed"


class BaseTryOnProvider(abc.ABC):
    """
    Abstract Base Class for Virtual Try-On generation engines.
    """

    @property
    @abc.abstractmethod
    def provider_name(self) -> str:
        """
        Unique provider name attribute (e.g. 'mock', 'fashn', 'replicate').
        """
        pass

    @abc.abstractmethod
    async def process_tryon(
        self,
        session_id: str,
        customer_photo_path: str,
        garment_image_url: str,
        category: Optional[str] = None,
        db: Optional[Any] = None,
    ) -> TryOnExecutionResult:
        """
        Asynchronously executes or simulates the try-on pipeline.
        Implementations should update database session status & progress
        as processing advances across stages.
        """
        pass

    @abc.abstractmethod
    async def check_status(
        self,
        session_id: str,
        db: Optional[Any] = None,
    ) -> TryOnExecutionResult:
        """
        Inquires current progress and status for an ongoing or completed try-on session.
        """
        pass

