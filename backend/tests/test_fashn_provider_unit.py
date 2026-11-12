"""
Unit tests for FashnTryOnProvider (Phase 5A).
Tests category normalization, device selection, lazy pipeline loading,
missing weights exceptions, and BaseTryOnProvider interface compliance.
"""
import sys
import os
from pathlib import Path

# Add backend root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.tryon.base import BaseTryOnProvider
from app.services.tryon.fashn_provider import (
    FashnTryOnProvider,
    normalize_garment_category,
)


def test_category_normalization():
    print("\n--- Testing Garment Category Normalization ---")

    # 1. Tops
    assert normalize_garment_category("Formal", "Classic Black Formal Blazer") == "tops"
    assert normalize_garment_category("Formal", "bllazer") == "tops"
    assert normalize_garment_category("Casual", "Cotton Crewneck T-shirt") == "tops"
    assert normalize_garment_category("Ethnic", "Embroidered Silk Kurta") == "tops"
    assert normalize_garment_category("Outerwear", "Winter Bomber Jacket") == "tops"
    assert normalize_garment_category("Tops", "Casual Button-down Shirt") == "tops"
    assert normalize_garment_category("Formal", "Suit Blazer") == "tops"

    # 2. Bottoms
    assert normalize_garment_category("Casual", "Slim Fit Denim Jeans") == "bottoms"
    assert normalize_garment_category("Formal", "Pleated Office Trousers") == "bottoms"
    assert normalize_garment_category("Casual", "Summer Chino Shorts") == "bottoms"
    assert normalize_garment_category("Ethnic", "Pleated Silk Skirt") == "bottoms"
    assert normalize_garment_category("Formal", "Suit Trouser") == "bottoms"

    # 3. One-pieces
    assert normalize_garment_category("Party", "Evening Gown Dress") == "one-pieces"
    assert normalize_garment_category("Casual", "Floral Summer Jumpsuit") == "one-pieces"
    assert normalize_garment_category("Casual", "Denim Romper") == "one-pieces"
    assert normalize_garment_category("Beachwear", "One-Piece Swimsuit") == "one-pieces"

    # 4. Suit disambiguation: generic / ambiguous suits must be rejected
    for ambiguous_suit in ("Formal Suit", "Business Suit", "Pant Suit", "Two-piece Suit"):
        try:
            normalize_garment_category("Formal", ambiguous_suit)
            assert False, f"'{ambiguous_suit}' should have been rejected as ambiguous"
        except ValueError as exc:
            assert "unambiguously resolve" in str(exc)

    # 5. Non-clothing or ambiguous categories must be rejected
    for non_garment in ("Leather Belt", "Sports Shoes", "Silk Scarf", "Wrist Watch"):
        try:
            normalize_garment_category("Accessories", non_garment)
            assert False, f"'{non_garment}' should have been rejected as ambiguous"
        except ValueError as exc:
            assert "unambiguously resolve" in str(exc)

    print("[PASS] Category normalization and ambiguity rejections verified.")


def test_device_selection_and_safety():
    print("\n--- Testing Device Configuration & Non-Silent Guardrails ---")

    # Default device configuration
    p_default = FashnTryOnProvider()
    assert p_default.provider_name == "fashn"
    assert p_default.device in ("cpu", "cuda")

    # Explicit CPU
    p_cpu = FashnTryOnProvider(device="cpu")
    assert p_cpu.device == "cpu"

    # Explicit CUDA when CUDA is unavailable must fail loudly (never silently claim GPU)
    try:
        import torch
        cuda_avail = torch is not None and torch.cuda.is_available()
    except (ImportError, AttributeError):
        cuda_avail = False

    if not cuda_avail:
        try:
            FashnTryOnProvider(device="cuda")
            assert False, "Should raise RuntimeError when CUDA requested on non-CUDA system"
        except RuntimeError as exc:
            assert "never silently claims gpu" in str(exc).lower() or "not available" in str(exc).lower()

    print("[PASS] Device configuration and non-silent fallback guardrails verified.")


def test_lazy_loading_and_missing_weights():
    print("\n--- Testing Lazy Loading & Missing Weights Exception ---")

    fake_weights_dir = Path("./nonexistent_fashn_weights_test_dir")
    p = FashnTryOnProvider(weights_dir=fake_weights_dir)

    # Instantiating provider must NOT attempt to load weights or crash immediately
    assert p._cached_pipeline is None

    # Calling _get_pipeline must raise FileNotFoundError or ImportError without auto-downloading
    try:
        p._get_pipeline()
        assert False, "Should have raised FileNotFoundError or ImportError"
    except (FileNotFoundError, ImportError) as exc:
        assert "not found" in str(exc).lower() or "missing" in str(exc).lower()

    print("[PASS] Lazy loading and pre-flight weights verification verified.")


def test_base_provider_compliance():
    print("\n--- Testing BaseTryOnProvider Interface Compliance ---")

    p = FashnTryOnProvider()
    assert isinstance(p, BaseTryOnProvider)
    assert p.provider_name == "fashn"
    assert hasattr(p, "process_tryon")
    assert hasattr(p, "check_status")

    print("[PASS] BaseTryOnProvider interface compliance verified.")


if __name__ == "__main__":
    test_category_normalization()
    test_device_selection_and_safety()
    test_lazy_loading_and_missing_weights()
    test_base_provider_compliance()
    print("\n==========================================")
    print("ALL PHASE 5A UNIT TESTS PASSED (100%)")
    print("==========================================")
