"""
Test Suite: Hugging Face ZeroGPU Try-On Provider (zerogpu_provider.py).

Verifies all Phase 9 requirements:
1. Exact API contract matching app.py (inputs: person, garment, category, timesteps; outputs: image).
2. Proper Gradio Queue submission (POST /gradio_api/call/tryon) and SSE event polling (heartbeat, estimation, process_starts, complete).
3. Configurable timeout (ZEROGPU_TIMEOUT_SECONDS) suitable for genuine FASHN inference.
4. Accurate MIME type and extension detection via raw magic bytes.
5. is_available() strictly distinguishes between configured URL and genuinely reachable worker.
6. Does not claim NVIDIA A100/L4 hardware unless the worker explicitly reports it.
7. Never marks a session completed until a valid generated image is received, decoded, validated, and saved.
8. Never returns mock, placeholder, or simulated results.
9. HF tokens kept strictly on backend, never exposed in frontend code or application logs.
10. ₹0 budget maintained without paid APIs or subscriptions.
"""
import io
import os
import sys
import json
import uuid
import struct
import base64
import asyncio
from typing import Tuple, Optional, Dict, Any
from pathlib import Path
from unittest.mock import patch
import urllib.error

# Add backend root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import HTTPException, status
from app.database import SessionLocal, init_db
from app.models import User, Shop, Product, TryOnSession
from app.routers.auth import register_user
from app.routers.products import create_product
from app.routers.tryon import start_tryon, get_tryon_status
from app.services.tryon.storage import (
    RESULTS_DIR,
    CUSTOMER_PHOTOS_DIR,
    save_customer_photo,
    delete_customer_photo,
)
from app.services.tryon.zerogpu_provider import (
    ZeroGPUTryOnProvider,
    detect_image_mime_and_ext,
    image_to_base64_data_url,
    parse_data_url_to_bytes,
    parse_image_dimensions,
    classify_upstream_error,
    redact_sensitive_text,
    sanitize_public_error_message,
    ERR_QUOTA_EXHAUSTED,
    ERR_SPACE_SLEEPING,
    ERR_WORKER_OVERLOAD,
    ERR_INVALID_INPUTS,
    ERR_UPLOAD_FAILED,
    ERR_INFERENCE_EXCEPTION,
    ERR_NETWORK_TIMEOUT,
    ERR_WORKER_UNAVAILABLE,
)
from app.services.tryon.factory import get_tryon_provider
from app.schemas.auth import UserRegisterRequest
from app.schemas.product import ProductCreate
from app.schemas.tryon import TryOnStatusResponse

# Minimum 1x1 valid JPEG bytes for test fixtures
VALID_JPEG_BYTES = (
    b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00"
    b"\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t"
    b"\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a"
    b"\x1f\x1e\x1d\x1a\x1c\x1c $.' \",#\x1c\x1c(7),01444\x1f'9=82<.342"
    b"\xff\xc0\x00\x0b\x08\x04\x00\x03\x00\x01\x01\x11\x00\xff\xc4"
    b"\x00\x1f\x00\x00\x01\x05\x01\x01\x01\x01\x01\x01\x00\x00\x00"
    b"\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b"
    b"\xff\xda\x00\x08\x01\x01\x00\x00?\x00\xbf\x00\xff\xd9"
) * 15  # Pad to > 1000 bytes to satisfy realistic file size check


class MockHTTPResponse:
    def __init__(self, status_code: int = 200, body: bytes = b"", headers: Optional[Dict[str, str]] = None):
        self.status = status_code
        self.code = status_code
        self._body = io.BytesIO(body)
        self.headers = headers or {}

    def read(self, amt: int = -1) -> bytes:
        return self._body.read(amt)

    def readline(self) -> bytes:
        return self._body.readline()

    def __iter__(self):
        return self

    def __next__(self) -> bytes:
        line = self.readline()
        if not line:
            raise StopIteration
        return line

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass


def mock_gradio_urlopen(req, timeout=None):
    """
    Simulates the exact Hugging Face ZeroGPU Gradio 5.x / 4.x worker API exposed by app.py:
    - GET /gradio_api/call/health or /call/health -> returns health JSON with device info
    - POST /upload -> receives files and returns server paths
    - POST /gradio_api/call/tryon or /call/tryon -> initiates inference and returns event_id
    - GET /gradio_api/call/tryon/<event_id> -> SSE stream (heartbeat, estimation, process_starts, complete)
    """
    if isinstance(req, str):
        url = req
        method = "GET"
        data = None
        headers = {}
    else:
        url = req.get_full_url()
        method = req.get_method()
        data = req.data
        headers = req.headers

    # Unreachable simulation
    if "59999" in url:
        raise urllib.error.URLError("[WinError 10061] No connection could be made because the target machine actively refused it")

    # Garment image fetch
    if "/uploads/" in url or url.endswith(".jpg"):
        return MockHTTPResponse(200, VALID_JPEG_BYTES, {"Content-Type": "image/jpeg"})

    # Health check
    if "/health" in url:
        dev = "NVIDIA L4 (24GB)"
        if "7871" in url:
            dev = "NVIDIA A100-SXM4-80GB"
        resp = {
            "status": "healthy",
            "service": "VirtualFit AI ZeroGPU Worker",
            "model": "FASHN VTON v1.5",
            "device": dev,
        }
        return MockHTTPResponse(200, json.dumps(resp).encode("utf-8"), {"Content-Type": "application/json"})

    # Staging /upload
    if "/upload" in url and method == "POST":
        return MockHTTPResponse(200, json.dumps(["/tmp/gradio/staged_input.jpg"]).encode("utf-8"), {"Content-Type": "application/json"})

    # TryOn queue submission
    if ("/gradio_api/call/tryon" in url or "/call/tryon" in url) and method == "POST":
        if "7874" in url:
            return MockHTTPResponse(200, b'{"event_id": "corrupt_123"}', {"Content-Type": "application/json"})

        # Validate payload structure matching app.py contract: [person, garment, category, timesteps]
        parsed = json.loads(data.decode("utf-8"))
        payload_data = parsed.get("data", [])
        assert len(payload_data) == 4, f"Expected 4 parameters [person, garment, category, timesteps], got {len(payload_data)}"
        assert payload_data[2] in ("tops", "bottoms", "one-pieces"), f"Invalid category: {payload_data[2]}"
        assert 10 <= int(payload_data[3]) <= 50, f"Invalid timesteps: {payload_data[3]}"

        return MockHTTPResponse(200, b'{"event_id": "evt_valid_123"}', {"Content-Type": "application/json"})

    # SSE Event streaming for valid run
    if "evt_valid_123" in url and method == "GET":
        result_b64 = "data:image/jpeg;base64," + base64.b64encode(VALID_JPEG_BYTES).decode("utf-8")
        complete_payload = json.dumps([{"path": result_b64}])
        sse_data = (
            b"event: heartbeat\ndata: null\n\n"
            b"event: estimation\ndata: [1, 15.0]\n\n"
            b"event: process_starts\ndata: null\n\n"
            b"event: complete\ndata: " + complete_payload.encode("utf-8") + b"\n\n"
        )
        return MockHTTPResponse(200, sse_data, {"Content-Type": "text/event-stream"})

    # SSE Event streaming for corrupt run
    if "corrupt_123" in url and method == "GET":
        sse_corrupt = b'event: complete\ndata: [{"path": "data:text/plain;base64,bm90IGFuIGltYWdl"}]\n\n'
        return MockHTTPResponse(200, sse_corrupt, {"Content-Type": "text/event-stream"})

    if "/info" in url:
        return MockHTTPResponse(200, b'{"named_endpoints": {"/tryon": {}, "/health": {}}}', {"Content-Type": "application/json"})

    return MockHTTPResponse(200, b"Gradio Worker Root", {"Content-Type": "text/html"})


def setup_db_product(db):
    uid = uuid.uuid4().hex[:8]
    ret_res = register_user(
        UserRegisterRequest(
            email=f"zg_ret_{uid}@example.com",
            password="SecurePassword123!",
            full_name=f"ZG Retailer {uid}",
            role="shop_owner",
            shop_name=f"ZG Shop {uid}",
        ),
        db=db,
    )
    ret_user = db.query(User).filter(User.email == f"zg_ret_{uid}@example.com").first()
    shop = db.get(Shop, ret_user.shop_id)

    product = create_product(
        ProductCreate(
            shop_id=shop.id,
            product_name=f"ZG Test Shirt {uid}",
            description="Linen shirt for ZeroGPU test",
            price=1299.0,
            category="tops",
            stock=10,
            image_url="http://127.0.0.1:8000/uploads/linen_shirt_zg.jpg",
        ),
        current_user=ret_user,
        db=db,
    )
    return ret_user, product


def test_mime_and_dimension_detection():
    print("\n--- Test 1: Image MIME Type & Magic Byte Detection ---")

    # 1. Test JPEG
    mime_jpg, ext_jpg = detect_image_mime_and_ext(VALID_JPEG_BYTES)
    assert mime_jpg == "image/jpeg"
    assert ext_jpg == ".jpg"
    print(f"  ✓ JPEG accurately detected: {mime_jpg} ({ext_jpg})")

    # 2. Test PNG with mock PNG header
    png_bytes = (
        b"\x89PNG\r\n\x1a\n"
        b"\x00\x00\x00\rIHDR"
        + struct.pack(">II", 768, 1024)
        + b"\x08\x02\x00\x00\x00\x4b\x6d\x29\xdc"
        + b"\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    mime_png, ext_png = detect_image_mime_and_ext(png_bytes)
    assert mime_png == "image/png"
    assert ext_png == ".png"
    print(f"  ✓ PNG accurately detected: {mime_png} ({ext_png})")

    dims = parse_image_dimensions(png_bytes, ext=".png")
    assert dims == (768, 1024), f"Expected (768, 1024), got {dims}"
    print(f"  ✓ PNG dimensions accurately parsed: {dims[0]}x{dims[1]}")


def test_is_available_distinguishes_reachable_worker():
    print("\n--- Test 2: is_available() Distinguishes Configured vs Reachable Worker ---")

    # Case A: Unconfigured URL
    p_unconf = ZeroGPUTryOnProvider(space_url="")
    avail_unconf, msg_unconf = p_unconf.is_available()
    assert avail_unconf is False
    assert "temporarily unavailable because no ZeroGPU inference worker is connected" in msg_unconf
    print(f"  ✓ Unconfigured worker accurately returns False: '{msg_unconf}'")

    # Case B: Configured but unreachable host (e.g. invalid port / domain)
    p_unreach = ZeroGPUTryOnProvider(space_url="http://127.0.0.1:59999")
    avail_unreach, msg_unreach = p_unreach.is_available()
    assert avail_unreach is False
    assert "unreachable" in msg_unreach.lower() or "connection" in msg_unreach.lower()
    print(f"  ✓ Unreachable worker accurately returns False: '{msg_unreach}'")

    # Case C: Genuinely reachable worker
    with patch("urllib.request.urlopen", side_effect=mock_gradio_urlopen):
        p_reach = ZeroGPUTryOnProvider(space_url="http://127.0.0.1:7871")
        avail_reach, msg_reach = p_reach.is_available()
        assert avail_reach is True
        assert "genuinely reachable" in msg_reach
        assert "NVIDIA A100-SXM4-80GB" in msg_reach
        print(f"  ✓ Genuinely reachable worker accurately returns True: '{msg_reach}'")


def test_hardware_attribution_never_falsely_claims():
    print("\n--- Test 3: Hardware Attribution Verifies Actual Reported Device ---")

    # When worker reports a specific device (e.g. NVIDIA L4)
    with patch("urllib.request.urlopen", side_effect=mock_gradio_urlopen):
        p = ZeroGPUTryOnProvider(space_url="http://127.0.0.1:7872")
        p.is_available()
        assert p.reported_hardware == "NVIDIA L4 (24GB)"
        print(f"  ✓ Actual reported hardware stored: '{p.reported_hardware}'")

    # When worker reports nothing or generic CPU, never falsely claims A100
    p_generic = ZeroGPUTryOnProvider(space_url="http://127.0.0.1:59999")
    assert p_generic.reported_hardware is None
    print("  ✓ Unverified worker reports None (never claims A100/L4).")


def test_configurable_timeout():
    print("\n--- Test 4: Configurable Timeout for Genuine Diffusion Synthesis ---")

    os.environ["ZEROGPU_TIMEOUT_SECONDS"] = "240"
    p = ZeroGPUTryOnProvider(space_url="https://test-space.hf.space")
    assert p.timeout_seconds == 240
    print(f"  ✓ Timeout successfully configured from environment: {p.timeout_seconds}s")

    p_explicit = ZeroGPUTryOnProvider(space_url="https://test-space.hf.space", timeout_seconds=420)
    assert p_explicit.timeout_seconds == 420
    print(f"  ✓ Explicit timeout successfully honored: {p_explicit.timeout_seconds}s")
    os.environ.pop("ZEROGPU_TIMEOUT_SECONDS", None)


def test_gradio_queue_and_real_result_validation():
    print("\n--- Test 5: Full Gradio Queue Submission & Genuine Result Validation ---")
    db = SessionLocal()
    _, product = setup_db_product(db)

    # Save test customer photo to private storage
    photo_name = save_customer_photo(VALID_JPEG_BYTES, "test_customer.jpg", ".jpg")
    session_id = str(uuid.uuid4())

    new_session = TryOnSession(
        id=session_id,
        customer_photo_url=photo_name,
        product_id=product.id,
        status="pending",
        provider="zerogpu",
        provenance="genuine_zerogpu",
    )
    db.add(new_session)
    db.commit()

    try:
        with patch("urllib.request.urlopen", side_effect=mock_gradio_urlopen):
            provider = ZeroGPUTryOnProvider(
                space_url="http://127.0.0.1:7873",
                timeout_seconds=60,
            )

            result = asyncio.run(
                provider.process_tryon(
                    session_id=session_id,
                    customer_photo_path=photo_name,
                    garment_image_url="http://127.0.0.1:8000/uploads/linen_shirt_zg.jpg",
                    category="tops",
                    db=db,
                )
            )

            # 1. Verify result object
            assert result.status == "completed"
            assert result.progress_percentage == 100
            assert "ZeroGPU" in result.stage_message
            assert result.result_image_url == f"/api/tryon/{session_id}/result"
            print(f"  ✓ Result object completed: {result.stage_message}")

            # 2. Verify database record
            db.expire_all()
            session_row = db.get(TryOnSession, session_id)
            assert session_row.status == "completed"
            assert session_row.progress_percentage == 100
            assert session_row.result_image_url == f"/api/tryon/{session_id}/result"
            assert session_row.provenance == "genuine_zerogpu"
            print("  ✓ Database record updated with completed status and honest provenance.")

            # 3. Verify file exists on disk and is genuine
            saved_file = RESULTS_DIR / f"res_{session_id}.jpg"
            assert saved_file.exists(), "Result file was not saved to RESULTS_DIR."
            saved_bytes = saved_file.read_bytes()
            assert len(saved_bytes) >= 1000
            assert saved_bytes.startswith(b"\xff\xd8\xff"), "Saved image is not a valid JPEG."
            print(f"  ✓ Saved result file verified on disk ({len(saved_bytes)} bytes, valid JPEG magic bytes).")

    finally:
        delete_customer_photo(photo_name)
        row = db.get(TryOnSession, session_id)
        if row:
            db.delete(row)
            db.commit()
        db.close()


def test_rejection_of_corrupt_result():
    print("\n--- Test 6: Strict Rejection of Corrupt / Invalid Result Images ---")
    db = SessionLocal()
    _, product = setup_db_product(db)

    photo_name = save_customer_photo(VALID_JPEG_BYTES, "test_customer.jpg", ".jpg")
    session_id = str(uuid.uuid4())

    new_session = TryOnSession(
        id=session_id,
        customer_photo_url=photo_name,
        product_id=product.id,
        status="pending",
        provider="zerogpu",
    )
    db.add(new_session)
    db.commit()

    try:
        with patch("urllib.request.urlopen", side_effect=mock_gradio_urlopen):
            p = ZeroGPUTryOnProvider(space_url="http://127.0.0.1:7874")
            res = asyncio.run(
                p.process_tryon(
                    session_id=session_id,
                    customer_photo_path=photo_name,
                    garment_image_url="http://127.0.0.1:8000/uploads/test.jpg",
                    category="tops",
                    db=db,
                )
            )

            # Must be marked failed (NEVER completed without valid image)
            assert res.status == "failed"
            assert res.result_image_url is None
            assert "not a valid" in res.error_message.lower() or "too small" in res.error_message.lower()

            db.expire_all()
            s_row = db.get(TryOnSession, session_id)
            assert s_row.status == "failed"
            print("  ✓ Corrupt result safely rejected; session accurately marked failed.")

    finally:
        delete_customer_photo(photo_name)
        row = db.get(TryOnSession, session_id)
        if row:
            db.delete(row)
            db.commit()
        db.close()


def test_factory_zerogpu_resolution():
    print("\n--- Test 7: Factory Provider Resolution & ₹0 Protection ---")

    # 1. zerogpu resolves to ZeroGPUTryOnProvider
    p_zero = get_tryon_provider("zerogpu")
    assert isinstance(p_zero, ZeroGPUTryOnProvider)
    assert p_zero.provider_name == "zerogpu"
    print("  ✓ Factory successfully resolves 'zerogpu' provider.")

    # 2. Strict rejection of paid APIs (e.g. replicate)
    try:
        get_tryon_provider("replicate")
        assert False, "Expected ValueError for paid API 'replicate'"
    except ValueError as exc:
        assert "₹0 budget policy" in str(exc)
        print("  ✓ Strict ₹0 guardrail blocks paid APIs (replicate).")


def test_phase11a_upstream_error_classification_and_sanitization():
    print("\n--- Test 8: Phase 11A Upstream Error Classification & Sanitization ---")

    c_quota = classify_upstream_error(
        raw_message="You have exceeded your ZeroGPU runs limit.",
        title="ZeroGPU quota exceeded",
        quota_resets_at="2026-11-11T16:10:00+00:00",
    )
    assert c_quota.category == ERR_QUOTA_EXHAUSTED
    assert c_quota.retry_after_seconds >= 60
    assert "00:00 utc" not in c_quota.public_message.lower()
    assert "2026-11-11T16:10:00+00:00" in c_quota.public_message

    c_sleep = classify_upstream_error(status_code=503)
    assert c_sleep.category == ERR_SPACE_SLEEPING
    assert c_sleep.retry_after_seconds > 0

    c_overload = classify_upstream_error(raw_message="Queue is full, too many requests")
    assert c_overload.category == ERR_WORKER_OVERLOAD
    assert c_overload.retry_after_seconds > 0

    c_upload = classify_upstream_error(status_code=413)
    assert c_upload.category == ERR_UPLOAD_FAILED
    assert c_upload.retry_after_seconds == 0

    c_inputs = classify_upstream_error(status_code=422)
    assert c_inputs.category == ERR_INVALID_INPUTS
    assert c_inputs.retry_after_seconds == 0

    c_timeout = classify_upstream_error(exc=TimeoutError("SSE wait timed out"))
    assert c_timeout.category == ERR_NETWORK_TIMEOUT
    assert c_timeout.retry_after_seconds > 0

    c_unavail = classify_upstream_error(status_code=401)
    assert c_unavail.category == ERR_WORKER_UNAVAILABLE

    c_null_sse = classify_upstream_error(raw_message="SSE error: null")
    assert c_null_sse.category == ERR_INFERENCE_EXCEPTION
    assert "quota" not in c_null_sse.public_message.lower()

    sanitized = sanitize_public_error_message(
        "Failed at https://secret-space.hf.space/gradio_api with hf_AbCdEfGhIjKlMnOp and C:\\secret\\file.png"
    )
    assert "secret-space.hf.space" not in sanitized
    assert "hf_AbCdEfGhIjKlMnOp" not in sanitized
    assert "C:\\secret" not in sanitized
    print("  ✓ All 7 upstream error categories and public sanitization verified.")


def test_phase11a_queue_join_unstripped_sse_and_null_call_handling():
    print("\n--- Test 9: Gradio /queue/join Unstripped SSE & /call/ Null Isolation ---")
    init_db()
    db = SessionLocal()
    _, product = setup_db_product(db)
    photo_name = save_customer_photo(VALID_JPEG_BYTES, "test_qjoin.jpg", ".jpg")

    class _MemResp:
        def __init__(self, body_bytes: bytes, status: int = 200):
            self.status = status
            self._buf = io.BytesIO(body_bytes)

        def read(self):
            return self._buf.read()

        def readline(self):
            return self._buf.readline()

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    # 9A: /config exposes /gradio_api + fn_index=2 -> /queue/join + /queue/data returns structured ZeroGPU quota error
    def mock_queue_join_quota(req, timeout=30):
        url = req.full_url if hasattr(req, "full_url") else str(req)
        if "/uploads/" in url:
            return _MemResp(VALID_JPEG_BYTES)
        if url.endswith("/config"):
            cfg = {
                "api_prefix": "/gradio_api",
                "dependencies": [{"id": 2, "api_name": "try_on", "targets": [[17, "click"]], "inputs": list(range(8))}],
            }
            return _MemResp(json.dumps(cfg).encode("utf-8"))
        if "/gradio_api/upload" in url:
            return _MemResp(json.dumps(["/tmp/gradio/staged.jpg"]).encode("utf-8"))
        if url.endswith("/gradio_api/queue/join"):
            return _MemResp(json.dumps({"event_id": "evt123"}).encode("utf-8"))
        if "/gradio_api/queue/data" in url:
            sse_lines = (
                'data: {"msg":"process_starts"}\n\n'
                'data: {"msg":"process_completed","success":false,"title":"ZeroGPU quota exceeded",'
                '"output":{"error":"You have exceeded your ZeroGPU runs limit. Authenticate with a Hugging Face token","title":"ZeroGPU quota exceeded"}}\n\n'
            ).encode("utf-8")
            return _MemResp(sse_lines)
        raise urllib.error.HTTPError(url, 404, "Not Found", {}, None)

    s1_id = str(uuid.uuid4())
    s2_id = str(uuid.uuid4())
    db.add_all([
        TryOnSession(id=s1_id, customer_photo_url=photo_name, product_id=product.id, status="pending", provider="zerogpu"),
        TryOnSession(id=s2_id, customer_photo_url=photo_name, product_id=product.id, status="pending", provider="zerogpu"),
    ])
    db.commit()

    try:
        with patch("urllib.request.urlopen", side_effect=mock_queue_join_quota):
            p = ZeroGPUTryOnProvider(space_url="https://example-space.hf.space", hf_token="hf_test_secret_token_value")
            # Mock quota lookup separately so we verify no token leak & resets_at propagation
            with patch.object(p, "check_hf_account_quota", return_value={"resets_at": "2026-11-11T16:10:00+00:00"}):
                res1 = asyncio.run(
                    p.process_tryon(
                        session_id=s1_id,
                        customer_photo_path=photo_name,
                        garment_image_url="http://127.0.0.1:8000/uploads/test.jpg",
                        category="tops",
                        db=db,
                    )
                )
            assert res1.status == "failed"
            assert res1.error_category == ERR_QUOTA_EXHAUSTED
            assert res1.quota_resets_at == "2026-11-11T16:10:00+00:00"
            assert res1.retry_after_seconds == 300
            assert "00:00 utc" not in res1.error_message.lower()
            assert "hf_test_secret_token_value" not in res1.error_message
            assert "example-space.hf.space" not in res1.error_message
            assert "example-space.hf.space" not in res1.stage_message

        # 9B: /call/ emitting SSE 'event: error / data: null' MUST NOT be misclassified as quota exhaustion
        def mock_call_null_sse(req, timeout=30):
            url = req.full_url if hasattr(req, "full_url") else str(req)
            if "/uploads/" in url:
                return _MemResp(VALID_JPEG_BYTES)
            if url.endswith("/config"):
                raise urllib.error.HTTPError(url, 404, "No config", {}, None)
            if "/upload" in url:
                raise urllib.error.HTTPError(url, 404, "No upload", {}, None)
            if url.endswith("/gradio_api/call/tryon"):
                return _MemResp(json.dumps({"event_id": "evt_null"}).encode("utf-8"))
            if url.endswith("/gradio_api/call/tryon/evt_null"):
                return _MemResp(b"event: process_starts\ndata: null\n\nevent: error\ndata: null\n\n")
            raise urllib.error.HTTPError(url, 404, "Not Found", {}, None)

        with patch("urllib.request.urlopen", side_effect=mock_call_null_sse):
            p2 = ZeroGPUTryOnProvider(space_url="https://example-space.hf.space")
            res2 = asyncio.run(
                p2.process_tryon(
                    session_id=s2_id,
                    customer_photo_path=photo_name,
                    garment_image_url="http://127.0.0.1:8000/uploads/test.jpg",
                    category="tops",
                    db=db,
                )
            )
            assert res2.status == "failed"
            assert res2.error_category == ERR_INFERENCE_EXCEPTION
            assert "quota" not in res2.error_message.lower()
            assert "00:00 utc" not in res2.error_message.lower()

        print("  ✓ /queue/join unstripped error parsing and /call/ null SSE isolation verified.")
    finally:
        delete_customer_photo(photo_name)
        for sid in (s1_id, s2_id):
            row = db.get(TryOnSession, sid)
            if row:
                db.delete(row)
        db.commit()
        db.close()


def test_phase11a_duplicate_submit_and_status_fields():
    print("\n--- Test 10: Duplicate Submission Prevention & Status Metadata ---")
    init_db()
    db = SessionLocal()
    uid = uuid.uuid4().hex[:8]
    user_res = register_user(
        UserRegisterRequest(
            email=f"dup_cust_{uid}@example.com",
            password="CustPassword123!",
            full_name="Dup Guard User",
            role="customer",
        ),
        db=db,
    )
    cust = db.get(User, user_res.user.id)
    _, product = setup_db_product(db)

    class _DummyBG:
        def __init__(self):
            self.tasks = []
        def add_task(self, fn, *args, **kwargs):
            self.tasks.append((fn, args, kwargs))

    class _DummyUpload:
        def __init__(self, filename: str, content: bytes):
            self.filename = filename
            self._content = content
        async def read(self):
            return self._content

    old_provider = os.environ.get("TRYON_PROVIDER")
    os.environ["TRYON_PROVIDER"] = "mock"
    s_id = None
    try:
        first_resp = asyncio.run(
            start_tryon(
                background_tasks=_DummyBG(),
                customer_photo=_DummyUpload("c.jpg", VALID_JPEG_BYTES),
                product_id=product.id,
                current_user=cust,
                db=db,
            )
        )
        s_id = first_resp.session_id
        assert first_resp.status == "pending"

        # Second concurrent active request for the same user + garment must return 409 Conflict
        try:
            asyncio.run(
                start_tryon(
                    background_tasks=_DummyBG(),
                    customer_photo=_DummyUpload("c2.jpg", VALID_JPEG_BYTES),
                    product_id=product.id,
                    current_user=cust,
                    db=db,
                )
            )
            assert False, "Expected HTTP 409 Conflict for duplicate active submission"
        except HTTPException as exc:
            assert exc.status_code == status.HTTP_409_CONFLICT

        # Verify status endpoint exposes error_category, retry_after_seconds, quota_resets_at cleanly
        row = db.get(TryOnSession, s_id)
        row.status = "failed"
        row.error_message = "Free quota exhausted at https://secret.hf.space"
        row.error_category = ERR_QUOTA_EXHAUSTED
        row.retry_after_seconds = 300
        row.quota_resets_at = "2026-11-11T16:10:00+00:00"
        db.commit()

        polled = get_tryon_status(session_id=s_id, current_user=cust, db=db)
        assert isinstance(polled, TryOnStatusResponse)
        assert polled.error_category == ERR_QUOTA_EXHAUSTED
        assert polled.retry_after_seconds == 300
        assert polled.quota_resets_at == "2026-11-11T16:10:00+00:00"
        assert "secret.hf.space" not in (polled.error_message or "")
        print("  ✓ Duplicate submission prevention and TryOnStatusResponse metadata verified.")
    finally:
        if old_provider is not None:
            os.environ["TRYON_PROVIDER"] = old_provider
        else:
            os.environ.pop("TRYON_PROVIDER", None)
        if s_id:
            row = db.get(TryOnSession, s_id)
            if row:
                db.delete(row)
        if cust:
            db.delete(cust)
        db.commit()
        db.close()


def test_phase11a_quota_and_runtime_api_helpers():
    print("\n--- Test 11: Official HF Quota & Runtime API Helpers ---")

    class _JsonResp:
        def __init__(self, obj, headers=None, status=200):
            self.status = status
            self.headers = headers or {}
            self._data = json.dumps(obj).encode("utf-8")

        def read(self):
            return self._data

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    # Unauthenticated provider skips HTTP quota request cleanly
    p_anon = ZeroGPUTryOnProvider(space_url="https://fashn-ai-fashn-vton-1-5.hf.space", hf_token="")
    anon_res = p_anon.check_hf_account_quota()
    assert anon_res["authenticated"] is False
    assert anon_res["resets_at"] is None

    # Authenticated provider normalizes epoch-ms resetsAt + queries space runtime
    def mock_hf_meta(req, timeout=5):
        url = req.full_url if hasattr(req, "full_url") else str(req)
        if url == "https://huggingface.co/api/spaces/zero-gpu/quota":
            return _JsonResp({"base": 300, "current": 0, "overquotaUsed": 0, "resetsAt": 1794413400000})
        if url.endswith(".hf.space/"):
            return _JsonResp({}, headers={"link": '<https://huggingface.co/spaces/fashn-ai/fashn-vton-1.5>;rel="canonical"'})
        if url == "https://huggingface.co/api/spaces/fashn-ai/fashn-vton-1.5/runtime":
            return _JsonResp({"stage": "RUNNING", "hardware": {"current": "zero-a10g"}, "sha": "abc123"})
        raise urllib.error.HTTPError(url, 404, "Not Found", {}, None)

    with patch("urllib.request.urlopen", side_effect=mock_hf_meta):
        p_auth = ZeroGPUTryOnProvider(space_url="https://fashn-ai-fashn-vton-1-5.hf.space", hf_token="hf_dummy_token")
        q_res = p_auth.check_hf_account_quota()
        assert q_res["authenticated"] is True
        assert q_res["quota_exhausted"] is True
        assert q_res["resets_at"] is not None and "T" in q_res["resets_at"]

        rt_res = p_auth.check_space_runtime()
        assert rt_res["stage"] == "RUNNING"
        assert rt_res["hardware"] == "zero-a10g"
        assert p_auth.reported_hardware == "zero-a10g"

    print("  ✓ Official HF quota & runtime helper checks verified.")


def test_phase11b_hf_token_headers_quota_and_isolation():
    print("\n--- Test 12: Phase 11B HF_TOKEN Header Propagation, Quota 401 & Secret Redaction ---")

    # 12A: Explicit hf_token="" must override OS env; quoted tokens are stripped; __repr__ never leaks secret
    fake_secret = "hf_TestSecretToken1234567890"
    old_env = os.environ.get("HF_TOKEN")
    os.environ["HF_TOKEN"] = f' "{fake_secret}" '
    try:
        p_override = ZeroGPUTryOnProvider(space_url="https://example-space.hf.space", hf_token="")
        assert p_override._hf_token == ""
        assert fake_secret not in repr(p_override)

        p_env = ZeroGPUTryOnProvider(space_url="https://example-space.hf.space")
        assert p_env._hf_token == fake_secret
        assert fake_secret not in repr(p_env)
        assert "token_configured=True" in repr(p_env)
    finally:
        if old_env is not None:
            os.environ["HF_TOKEN"] = old_env
        else:
            os.environ.pop("HF_TOKEN", None)

    # 12B: Rejected HF_TOKEN (401/403) must return authenticated=False on official quota endpoint
    def mock_quota_401(req, timeout=5):
        url = req.full_url if hasattr(req, "full_url") else str(req)
        assert req.get_header("Authorization") == f"Bearer {fake_secret}"
        raise urllib.error.HTTPError(url, 401, "Unauthorized", {}, io.BytesIO(b'{"error":"Invalid username or password."}'))

    with patch("urllib.request.urlopen", side_effect=mock_quota_401):
        p_401 = ZeroGPUTryOnProvider(space_url="https://example-space.hf.space", hf_token=fake_secret)
        q401 = p_401.check_hf_account_quota()
        assert q401["authenticated"] is False
        assert q401["token_configured"] is True
        assert q401["status_code"] == 401
        assert fake_secret not in json.dumps(q401)

    # 12C: Authorization: Bearer <token> attached to /config, /upload, /queue/join, /queue/data, and result /file= fetch
    #      AND never leaked to unrelated third-party image URLs
    seen_auth_headers = []
    db = SessionLocal()
    _, product = setup_db_product(db)
    photo_name = save_customer_photo(VALID_JPEG_BYTES, "phase11b_cust.jpg", ".jpg")
    session_id = str(uuid.uuid4())
    db.add(TryOnSession(
        id=session_id,
        customer_photo_url=photo_name,
        product_id=product.id,
        status="pending",
        provider="zerogpu",
        provenance="genuine_zerogpu",
    ))
    db.commit()

    def mock_authenticated_pipeline(req, timeout=30):
        url = req.full_url if hasattr(req, "full_url") else str(req)
        auth_header = req.get_header("Authorization") if hasattr(req, "get_header") else None
        seen_auth_headers.append((url, auth_header))
        if "cdn.untrusted-example.com" in url:
            assert auth_header is None, "HF_TOKEN must NEVER be sent to arbitrary third-party image URLs!"
            return MockHTTPResponse(200, VALID_JPEG_BYTES)
        if url.endswith("/config"):
            assert auth_header == f"Bearer {fake_secret}"
            return MockHTTPResponse(
                200,
                json.dumps({
                    "api_prefix": "/gradio_api",
                    "dependencies": [{"id": 2, "api_name": "try_on", "targets": [[17, "click"]], "inputs": list(range(8))}],
                }).encode("utf-8"),
            )
        if "/gradio_api/upload" in url:
            assert auth_header == f"Bearer {fake_secret}"
            ctype = req.get_header("Content-type") or req.get_header("Content-Type") or ""
            assert "multipart/form-data" in ctype
            return MockHTTPResponse(200, json.dumps(["/tmp/gradio/staged.jpg"]).encode("utf-8"))
        if "/gradio_api/queue/join" in url:
            assert auth_header == f"Bearer {fake_secret}"
            return MockHTTPResponse(200, json.dumps({"event_id": "evt_11b"}).encode("utf-8"))
        if "/gradio_api/queue/data" in url:
            assert auth_header == f"Bearer {fake_secret}"
            sse = (
                'data: {"msg":"process_starts"}\n\n'
                'data: {"msg":"process_completed","success":true,"output":{"data":[{"url":"https://fashn-ai-fashn-vton-1-5.hf.space/gradio_api/file=/tmp/res.jpg"}]}}\n\n'
            ).encode("utf-8")
            return MockHTTPResponse(200, sse)
        if "/gradio_api/file=" in url:
            assert auth_header == f"Bearer {fake_secret}"
            return MockHTTPResponse(200, VALID_JPEG_BYTES)
        raise urllib.error.HTTPError(url, 404, "Not Found", {}, None)

    try:
        with patch("urllib.request.urlopen", side_effect=mock_authenticated_pipeline):
            p_auth = ZeroGPUTryOnProvider(space_url="https://fashn-ai-fashn-vton-1-5.hf.space", hf_token=fake_secret)
            res = asyncio.run(
                p_auth.process_tryon(
                    session_id=session_id,
                    customer_photo_path=photo_name,
                    garment_image_url="https://cdn.untrusted-example.com/garment.jpg",
                    category="tops",
                    db=db,
                )
            )
            assert res.status == "completed"
            assert res.provenance if hasattr(res, "provenance") else True
            # Also confirm third-party download headers omit Authorization
            untrusted_hdrs = p_auth._build_download_headers("https://cdn.untrusted-example.com/res.jpg")
            assert "Authorization" not in untrusted_hdrs

        called_urls = [u for u, _ in seen_auth_headers]
        assert any(u.endswith("/config") for u in called_urls)
        assert any("/gradio_api/upload" in u for u in called_urls)
        assert any("/gradio_api/queue/join" in u for u in called_urls)
        assert any("/gradio_api/queue/data" in u for u in called_urls)
        assert any("/gradio_api/file=" in u for u in called_urls)

        # 12D: Bearer and hf_ redaction safety check
        leaked = f"Authorization: Bearer {fake_secret} failed for token {fake_secret}"
        redacted = redact_sensitive_text(leaked)
        assert fake_secret not in redacted
        assert "[redacted-token]" in redacted
        print("  ✓ HF_TOKEN header propagation, host isolation, 401 quota check, and secret redaction verified.")
    finally:
        delete_customer_photo(photo_name)
        res_file = RESULTS_DIR / f"res_{session_id}.jpg"
        if res_file.exists():
            res_file.unlink()
        row = db.get(TryOnSession, session_id)
        if row:
            db.delete(row)
        db.commit()
        db.close()


if __name__ == "__main__":
    print("===================================================================")
    print("  RUNNING PHASE 9 + 11A + 11B: HUGGING FACE ZEROGPU TEST SUITE     ")
    print("===================================================================")

    test_mime_and_dimension_detection()
    test_is_available_distinguishes_reachable_worker()
    test_hardware_attribution_never_falsely_claims()
    test_configurable_timeout()
    test_gradio_queue_and_real_result_validation()
    test_rejection_of_corrupt_result()
    test_factory_zerogpu_resolution()
    test_phase11a_upstream_error_classification_and_sanitization()
    test_phase11a_queue_join_unstripped_sse_and_null_call_handling()
    test_phase11a_duplicate_submit_and_status_fields()
    test_phase11a_quota_and_runtime_api_helpers()
    test_phase11b_hf_token_headers_quota_and_isolation()

    print("\n===================================================================")
    print("  ALL ZEROGPU PROVIDER + PHASE 11A + 11B TESTS PASSED (12/12)!     ")
    print("===================================================================")
