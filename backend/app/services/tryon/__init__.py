"""
VirtualFit AI Try-On Service Package.

Provides:
- Private temporary file storage and 1-hour lifecycle purging
- Abstract BaseTryOnProvider & TryOnExecutionResult
- MockTryOnProvider for realistic multi-stage simulation without external calls
- Provider factory resolving configured engines safely
"""
from app.services.tryon.storage import (
    save_customer_photo,
    get_customer_photo_path,
    get_customer_photo_bytes,
    delete_customer_photo,
    save_result_file,
    get_result_path,
    delete_result_file,
    cleanup_expired_files,
    STORAGE_ROOT,
    CUSTOMER_PHOTOS_DIR,
    RESULTS_DIR,
)
from app.services.tryon.base import (
    BaseTryOnProvider,
    TryOnExecutionResult,
)
from app.services.tryon.mock_provider import (
    MockTryOnProvider,
    SIMULATION_COMPLETED_NOTICE,
)
from app.services.tryon.fashn_provider import (
    FashnTryOnProvider,
    normalize_garment_category,
)
from app.services.tryon.zerogpu_provider import ZeroGPUTryOnProvider
from app.services.tryon.factory import (
    get_tryon_provider,
    SUPPORTED_PROVIDERS,
)

__all__ = [
    # Storage
    "save_customer_photo",
    "get_customer_photo_path",
    "get_customer_photo_bytes",
    "delete_customer_photo",
    "save_result_file",
    "get_result_path",
    "delete_result_file",
    "cleanup_expired_files",
    "STORAGE_ROOT",
    "CUSTOMER_PHOTOS_DIR",
    "RESULTS_DIR",
    # Base
    "BaseTryOnProvider",
    "TryOnExecutionResult",
    # Mock Provider
    "MockTryOnProvider",
    "SIMULATION_COMPLETED_NOTICE",
    # Genuine FASHN Provider
    "FashnTryOnProvider",
    "normalize_garment_category",
    # ZeroGPU Provider
    "ZeroGPUTryOnProvider",
    # Factory
    "get_tryon_provider",
    "SUPPORTED_PROVIDERS",
]

