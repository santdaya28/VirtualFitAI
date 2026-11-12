"""
Virtual Try-On Provider Factory.

Instantiates and returns the configured Virtual Try-On provider.
Supports:
- 'mock': Provider-independent simulation engine for automated testing and UI validation.
- 'fashn': Genuine open-source neural diffusion pipeline (FASHN VTON v1.5).

Strictly rejects paid external cloud APIs (e.g. Replicate) under the project's ₹0 budget policy.
Fails loudly and informatively if an unsupported provider or uninstalled dependency is encountered.
"""
import os
import logging
from typing import Optional, Set
from app.services.tryon.base import BaseTryOnProvider
from app.services.tryon.mock_provider import MockTryOnProvider
from app.services.tryon.fashn_provider import FashnTryOnProvider
from app.services.tryon.zerogpu_provider import ZeroGPUTryOnProvider

logger = logging.getLogger("virtualfit.tryon.factory")

SUPPORTED_PROVIDERS: Set[str] = {"mock", "fashn", "zerogpu"}


def get_tryon_provider(provider_name: Optional[str] = None) -> BaseTryOnProvider:
    """
    Returns the active Virtual Try-On engine.

    Resolution order for provider selection:
    1. Explicit `provider_name` argument (if supplied)
    2. Environment variable `TRYON_PROVIDER`
    3. Environment variable `AI_TRYON_PROVIDER`
    4. Default: "mock"

    Raises ValueError if an unsupported or prohibited provider is requested.
    """
    resolved_name = (
        provider_name
        or os.getenv("TRYON_PROVIDER")
        or os.getenv("AI_TRYON_PROVIDER", "mock")
    ).lower().strip()

    if resolved_name == "mock":
        return MockTryOnProvider()

    if resolved_name == "fashn":
        logger.info("[Factory] Resolving genuine FASHN VTON v1.5 Try-On provider.")
        return FashnTryOnProvider()

    if resolved_name == "zerogpu":
        logger.info("[Factory] Resolving genuine Hugging Face ZeroGPU Try-On provider.")
        return ZeroGPUTryOnProvider()

    # Guardrail: Replicate or other paid cloud APIs are prohibited under ₹0 policy
    if resolved_name == "replicate":
        logger.error(
            "Provider 'replicate' was requested, but paid external cloud APIs are strictly "
            "prohibited under the VirtualFit AI ₹0 commercial budget policy."
        )
        raise ValueError(
            "Provider 'replicate' is disabled under the ₹0 budget policy. "
            "VirtualFit AI uses genuine open-source on-premise models (e.g., FASHN VTON v1.5)."
        )

    raise ValueError(
        f"Unsupported try-on provider: '{resolved_name}'. "
        f"Supported providers: {', '.join(sorted(SUPPORTED_PROVIDERS))}."
    )

