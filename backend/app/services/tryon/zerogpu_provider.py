"""
VirtualFit AI — Hugging Face ZeroGPU Virtual Try-On Provider.

Connects VirtualFit AI to an authorized Hugging Face ZeroGPU inference worker
executing genuine FASHN VTON v1.5 neural diffusion try-on inference.

Key Capabilities & Strict Adherence:
1. Exact API contract matching app.py (Gradio 4/5 queue SSE protocol with fallback).
2. Configurable timeout (ZEROGPU_TIMEOUT_SECONDS, default: 300s) respecting Hugging Face limits.
3. Accurate image MIME type detection via magic bytes.
4. is_available() strictly distinguishes between configured URL and genuinely reachable worker.
5. Never claims NVIDIA A100/L4 hardware unless the worker explicitly reports it.
6. Never marks a session completed until a valid generated image is received, decoded, validated, and saved.
7. Never returns mock, placeholder, or simulated results.
8. Server-side token security (never exposed to frontend or application logs).
9. Strictly ₹0 commercial budget (Hugging Face ZeroGPU Free Tier).
"""
import os
import io
import re
import json
import uuid
import socket
import struct
import base64
import logging
import asyncio
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any, Tuple, Union, List

from app.services.tryon.base import BaseTryOnProvider, TryOnExecutionResult
from app.services.tryon.storage import (
    RESULTS_DIR,
    get_customer_photo_path,
)
from app.services.tryon import normalize_garment_category

logger = logging.getLogger("virtualfit.tryon.zerogpu")

# Default 300 seconds (5 minutes) total timeout to accommodate ZeroGPU queue time + 120s diffusion
DEFAULT_TIMEOUT_SECONDS = 300

# Structured upstream error categories
ERR_QUOTA_EXHAUSTED = "quota_exhausted"
ERR_SPACE_SLEEPING = "space_sleeping"
ERR_WORKER_OVERLOAD = "worker_overload"
ERR_INVALID_INPUTS = "invalid_inputs"
ERR_UPLOAD_FAILED = "upload_failed"
ERR_INFERENCE_EXCEPTION = "inference_exception"
ERR_NETWORK_TIMEOUT = "network_timeout"
ERR_WORKER_UNAVAILABLE = "worker_unavailable"


class _ZeroGPUWorkerExecutionError(RuntimeError):
    """Raised when an accepted Gradio queue job fails during SSE execution (not a wrong-route 404)."""


class _ZeroGPUClassifiedError(_ZeroGPUWorkerExecutionError):
    """Structured error carrying normalized category, safe public message, and retry delay."""

    def __init__(
        self,
        category: str,
        public_message: str,
        technical_detail: str = "",
        retry_after_seconds: int = 0,
        quota_resets_at: Optional[str] = None,
    ):
        super().__init__(technical_detail or public_message)
        self.category = category
        self.public_message = public_message
        self.technical_detail = technical_detail or public_message
        self.retry_after_seconds = max(0, int(retry_after_seconds))
        self.quota_resets_at = quota_resets_at


def redact_sensitive_text(message: Optional[str]) -> str:
    """Scrubs Hugging Face tokens and Bearer credentials before logging or UI display."""
    if not message:
        return ""
    cleaned = str(message)
    cleaned = re.sub(r"Bearer\s+[A-Za-z0-9._\-~+/]+=*", "Bearer [redacted-token]", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"hf_[A-Za-z0-9_-]{6,}", "[redacted-token]", cleaned)
    return cleaned


def sanitize_public_error_message(message: Optional[str]) -> str:
    """
    Strips URLs, filesystem paths, HF tokens, raw tracebacks, and stale hardcoded reset claims
    from any error string before it can reach customer-facing API responses or the UI.
    """
    if not message:
        return "AI fitting could not be completed. Please try again."

    cleaned = redact_sensitive_text(message)
    cleaned = re.sub(r"https?://[^\s\)\],'\"]+", "[remote-service]", cleaned)
    cleaned = re.sub(r"[A-Za-z]:\\[^\s'\"]+", "[local-path]", cleaned)
    cleaned = re.sub(r"/(?:tmp|var|app|backend|home|Users)/[^\s'\"]+", "[server-path]", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if len(cleaned) > 350:
        cleaned = cleaned[:347] + "..."
    return cleaned


def classify_upstream_error(
    raw_message: str = "",
    title: str = "",
    status_code: Optional[int] = None,
    exc: Optional[Exception] = None,
    quota_resets_at: Optional[str] = None,
) -> _ZeroGPUClassifiedError:
    """
    Maps raw Hugging Face / Gradio HTTP responses, SSE payloads, and transport exceptions
    into accurate structured categories with safe, honest customer messages.
    """
    if isinstance(exc, _ZeroGPUClassifiedError):
        return exc

    if status_code is None and isinstance(exc, urllib.error.HTTPError):
        status_code = exc.code

    raw_detail = f"{title}: {raw_message}".strip(": ") if title else raw_message
    if not raw_detail and exc is not None:
        raw_detail = str(exc)
    lower_msg = f"{title} {raw_message} {str(exc or '')}".lower()

    # 1. ZeroGPU Daily / Rolling 24h Quota Exhaustion (ONLY on genuine quota signals, NEVER on bare SSE null)
    is_quota_signal = any(
        token in lower_msg
        for token in (
            "zerogpu quota",
            "exceeded your zerogpu",
            "zerogpu runs limit",
            "daily zerogpu quota",
            "quota exceeded",
            "daily quota",
            "gpu quota",
            "runs limit",
        )
    )
    if status_code == 429 and not any(tok in lower_msg for tok in ("queue is full", "overload", "too busy")):
        is_quota_signal = True

    if is_quota_signal:
        msg = (
            "Free Hugging Face ZeroGPU compute quota is currently exhausted. "
            "ZeroGPU uses a rolling 24-hour quota window (not a fixed 00:00 UTC reset)."
        )
        if quota_resets_at:
            msg = (
                f"Free Hugging Face ZeroGPU compute quota is currently exhausted "
                f"(estimated reset time: {quota_resets_at})."
            )
        return _ZeroGPUClassifiedError(
            category=ERR_QUOTA_EXHAUSTED,
            public_message=msg,
            technical_detail=raw_detail or "HTTP 429 / ZeroGPU quota exceeded",
            retry_after_seconds=300,
            quota_resets_at=quota_resets_at,
        )

    # 2. Space Sleeping or Cold Boot
    if status_code in (502, 503, 504) or any(
        tok in lower_msg
        for tok in ("sleeping", "waking up", "cold start", "cold boot", "app_starting", "building", "paused", "stopped", "runtime_error")
    ):
        return _ZeroGPUClassifiedError(
            category=ERR_SPACE_SLEEPING,
            public_message="The AI fitting Space is currently waking up or starting on Hugging Face. Please wait ~30-60 seconds and try again.",
            technical_detail=raw_detail or f"Space sleeping / HTTP {status_code}",
            retry_after_seconds=35,
        )

    # 3. Worker Overload / Queue Full
    if any(
        tok in lower_msg
        for tok in ("queue is full", "queue_full", "overload", "too busy", "concurrent", "capacity", "too many requests")
    ):
        return _ZeroGPUClassifiedError(
            category=ERR_WORKER_OVERLOAD,
            public_message="The AI inference queue is temporarily busy handling other requests. Please wait a moment and try again.",
            technical_detail=raw_detail or "ZeroGPU queue overload",
            retry_after_seconds=45,
        )

    # 4. Result output validation failure (must remain inference_exception and preserve clear check keywords)
    if any(tok in lower_msg for tok in ("not a valid jpeg", "result image is too small", "outside permissible bounds", "empty response data", "failed to parse completed gradio")):
        return _ZeroGPUClassifiedError(
            category=ERR_INFERENCE_EXCEPTION,
            public_message="The AI worker returned data that was not a valid JPEG, PNG, or WebP image (or was too small).",
            technical_detail=raw_detail,
            retry_after_seconds=20,
        )

    # 5. Image Upload / Staging Failure
    if status_code == 413 or any(tok in lower_msg for tok in ("staging", "upload endpoint", "stage the uploaded")):
        return _ZeroGPUClassifiedError(
            category=ERR_UPLOAD_FAILED,
            public_message="Could not stage customer or garment images on the AI worker. Please ensure the photo is under 10 MB and try again.",
            technical_detail=raw_detail or f"Upload failure HTTP {status_code}",
            retry_after_seconds=0,
        )

    # 6. Invalid Inputs / Payload
    if isinstance(exc, FileNotFoundError) or status_code in (400, 422) or any(
        tok in lower_msg
        for tok in ("unsupported garment category", "could not be resolved", "invalid input", "validation error", "corrupt input")
    ):
        return _ZeroGPUClassifiedError(
            category=ERR_INVALID_INPUTS,
            public_message="The uploaded photo or selected garment could not be processed. Please upload a clear front-facing JPG, PNG, or WebP photo.",
            technical_detail=raw_detail or f"Input validation HTTP {status_code}",
            retry_after_seconds=0,
        )

    # 7. Network Timeout or Connection Interruption
    is_transport_error = isinstance(exc, urllib.error.URLError) and not isinstance(exc, urllib.error.HTTPError)
    if (
        isinstance(exc, (TimeoutError, socket.timeout, ConnectionResetError, BrokenPipeError))
        or (is_transport_error and any(tok in lower_msg for tok in ("timed out", "timeout", "reset", "eof")))
        or any(tok in lower_msg for tok in ("timed out", "timeout", "connection interrupted", "stream ended without emitting", "incomplete read", "closed before returning"))
    ):
        return _ZeroGPUClassifiedError(
            category=ERR_NETWORK_TIMEOUT,
            public_message="Connection to the AI inference service timed out or was interrupted. Please try again.",
            technical_detail=raw_detail or "Network timeout / stream interruption",
            retry_after_seconds=20,
        )

    # 8. Worker Unconfigured / Unreachable / Auth Rejected
    if "no zerogpu inference worker" in lower_msg:
        return _ZeroGPUClassifiedError(
            category=ERR_WORKER_UNAVAILABLE,
            public_message="AI generation is temporarily unavailable because no ZeroGPU inference worker is connected.",
            technical_detail=raw_detail,
            retry_after_seconds=60,
        )

    if status_code in (401, 403) or is_transport_error or any(
        tok in lower_msg for tok in ("getaddrinfo", "connection refused", "unreachable", "name or service not known", "not configured")
    ):
        return _ZeroGPUClassifiedError(
            category=ERR_WORKER_UNAVAILABLE,
            public_message="The AI inference worker is temporarily unreachable. Please try again shortly.",
            technical_detail=raw_detail or f"Worker unavailable HTTP {status_code}",
            retry_after_seconds=60,
        )

    # 9. Generic Inference Execution Exception (including Gradio /call/ SSE error: null)
    return _ZeroGPUClassifiedError(
        category=ERR_INFERENCE_EXCEPTION,
        public_message="The AI worker encountered a processing error or aborted image synthesis. Please try again shortly.",
        technical_detail=raw_detail or "Unspecified inference exception",
        retry_after_seconds=30,
    )


def detect_image_mime_and_ext(image_bytes: bytes) -> Tuple[str, str]:
    """
    Detects the exact MIME type and file extension from raw image magic bytes.
    Supports JPEG, PNG, and WebP.
    """
    if len(image_bytes) >= 3 and image_bytes.startswith(b"\xff\xd8\xff"):
        return "image/jpeg", ".jpg"
    if len(image_bytes) >= 8 and image_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png", ".png"
    if len(image_bytes) >= 12 and image_bytes.startswith(b"RIFF") and image_bytes[8:12] == b"WEBP":
        return "image/webp", ".webp"
    return "image/jpeg", ".jpg"


def image_to_base64_data_url(image_bytes: bytes) -> str:
    """Encodes raw image bytes into a data URL with verified MIME type."""
    mime, _ = detect_image_mime_and_ext(image_bytes)
    b64_str = base64.b64encode(image_bytes).decode("utf-8")
    return f"data:{mime};base64,{b64_str}"


def parse_data_url_to_bytes(data_url: str) -> Tuple[bytes, str]:
    """
    Decodes a base64 data URL into raw image bytes and detected extension.
    Example: 'data:image/png;base64,iVBORw...' -> (bytes, '.png')
    """
    if not data_url.startswith("data:"):
        raw_bytes = base64.b64decode(data_url)
        _, ext = detect_image_mime_and_ext(raw_bytes)
        return raw_bytes, ext

    header, encoded = data_url.split(",", 1)
    raw_bytes = base64.b64decode(encoded)
    _, ext = detect_image_mime_and_ext(raw_bytes)
    return raw_bytes, ext


def parse_image_dimensions(contents: bytes, ext: str) -> Optional[Tuple[int, int]]:
    """
    Parses image dimensions (width, height) directly from raw byte headers
    without requiring third-party imaging dependencies.
    """
    try:
        if ext == ".png" and contents.startswith(b"\x89PNG\r\n\x1a\n") and len(contents) >= 24:
            w, h = struct.unpack(">II", contents[16:24])
            return (w, h)
        elif ext == ".jpg" or contents.startswith(b"\xff\xd8\xff"):
            idx = 2
            length = len(contents)
            while idx < length - 9:
                if contents[idx] != 0xFF:
                    idx += 1
                    continue
                marker = contents[idx + 1]
                if marker in (0xC0, 0xC1, 0xC2, 0xC3):
                    h, w = struct.unpack(">HH", contents[idx + 5 : idx + 9])
                    return (w, h)
                if idx + 4 > length:
                    break
                seg_len = struct.unpack(">H", contents[idx + 2 : idx + 4])[0]
                idx += 2 + seg_len
        elif ext == ".webp" and contents.startswith(b"RIFF") and contents[8:12] == b"WEBP":
            chunk_type = contents[12:16]
            if chunk_type == b"VP8 " and len(contents) >= 30:
                w, h = struct.unpack("<HH", contents[26:30])
                return (w & 0x3FFF, h & 0x3FFF)
            elif chunk_type == b"VP8L" and len(contents) >= 25:
                b0, b1, b2, b3 = contents[21:25]
                w = 1 + (((b1 & 0x3F) << 8) | b0)
                h = 1 + (((b3 & 0x0F) << 10) | (b2 << 2) | ((b1 & 0xC0) >> 6))
                return (w, h)
    except Exception as exc:
        logger.debug(f"Could not parse image dimensions: {exc}")
    return None


class ZeroGPUTryOnProvider(BaseTryOnProvider):
    """
    Genuine FASHN VTON v1.5 Virtual Try-On Provider backed by Hugging Face ZeroGPU.
    Operates under a strict ₹0 budget using free community ZeroGPU hardware.
    """

    def __init__(
        self,
        space_url: Optional[str] = None,
        hf_token: Optional[str] = None,
        timeout_seconds: Optional[int] = None,
        num_timesteps: int = 30,
    ):
        if space_url is not None:
            raw_url = str(space_url).strip()
        else:
            raw_url = (
                os.getenv("ZEROGPU_API_URL")
                or os.getenv("HF_SPACE_URL")
                or os.getenv("HF_SPACE_ID")
                or ""
            ).strip()

        # Normalize space URL
        if raw_url and not raw_url.startswith(("http://", "https://")):
            # Convert 'username/space-name' into direct space URL
            raw_url = f"https://{raw_url.replace('/', '-')}.hf.space"

        self._space_url = raw_url.rstrip("/")

        # Server-side token: honor explicit hf_token parameter (even ""), never exposed in logs or API outputs
        raw_token = hf_token if hf_token is not None else (os.getenv("HF_TOKEN") or os.getenv("HF_ZEROGPU_TOKEN") or "")
        self._hf_token = str(raw_token).strip().strip('"').strip("'").strip()

        # Configurable timeout: reads ZEROGPU_TIMEOUT_SECONDS or HF_TIMEOUT_SECONDS
        env_timeout = os.getenv("ZEROGPU_TIMEOUT_SECONDS") or os.getenv("HF_TIMEOUT_SECONDS")
        if timeout_seconds is not None:
            self._timeout_seconds = max(30, int(timeout_seconds))
        elif env_timeout:
            try:
                self._timeout_seconds = max(30, int(env_timeout))
            except ValueError:
                self._timeout_seconds = DEFAULT_TIMEOUT_SECONDS
        else:
            self._timeout_seconds = DEFAULT_TIMEOUT_SECONDS

        self._num_timesteps = max(10, min(50, int(num_timesteps)))

        # Actual hardware reported by worker (None until verified)
        self._reported_hardware: Optional[str] = None

        logger.info(
            f"ZeroGPUTryOnProvider initialized (space_url='{self._space_url or 'NOT_CONFIGURED'}', "
            f"token_configured={bool(self._hf_token)}, timeout={self._timeout_seconds}s, "
            f"timesteps={self._num_timesteps})"
        )

    @property
    def provider_name(self) -> str:
        return "zerogpu"

    @property
    def space_url(self) -> str:
        return self._space_url

    @property
    def timeout_seconds(self) -> int:
        return self._timeout_seconds

    @property
    def reported_hardware(self) -> Optional[str]:
        return self._reported_hardware

    def __repr__(self) -> str:
        return (
            f"ZeroGPUTryOnProvider(space_url={self._space_url!r}, "
            f"token_configured={bool(self._hf_token)}, timeout_seconds={self._timeout_seconds})"
        )

    def _build_headers(self, include_content_type: bool = True) -> Dict[str, str]:
        """Builds standard headers for Hugging Face Space API calls."""
        headers = {
            "User-Agent": "VirtualFitAI-ZeroGPU-Client/1.0",
        }
        if include_content_type:
            headers["Content-Type"] = "application/json"
        if self._hf_token:
            headers["Authorization"] = f"Bearer {self._hf_token}"
        return headers

    def _is_trusted_hf_host(self, target_url: str) -> bool:
        """Restricts Bearer HF_TOKEN transmission strictly to Hugging Face / configured worker / local test hosts."""
        try:
            target_host = (urllib.parse.urlparse(target_url).hostname or "").lower()
            space_host = (urllib.parse.urlparse(self._space_url).hostname or "").lower() if self._space_url else ""
        except Exception:
            return False
        if not target_host:
            return False
        if space_host and target_host == space_host:
            return True
        if target_host in ("localhost", "127.0.0.1", "huggingface.co", "hf.co", "hf.space"):
            return True
        return target_host.endswith((".hf.space", ".huggingface.co", ".hf.co"))

    def _build_download_headers(self, target_url: str) -> Dict[str, str]:
        """Attaches HF Authorization header only when downloading from a trusted HF or worker host."""
        if self._is_trusted_hf_host(target_url):
            return self._build_headers(include_content_type=False)
        return {"User-Agent": "VirtualFitAI-ZeroGPU-Client/1.0"}

    def is_available(self) -> Tuple[bool, str]:
        """
        Validates whether the ZeroGPU inference worker is configured AND genuinely reachable.
        Distinguishes between:
        1. Worker URL not configured.
        2. Worker configured but unreachable (network error, connection refused, 404).
        3. Worker authentication failure (401/403).
        4. Worker daily quota exhausted (429).
        5. Worker sleeping / waking up (502 / 503 / 504 cold boot).
        6. Worker genuinely reachable and healthy (returns actual reported hardware).
        """
        if not self._space_url:
            return False, "AI generation is temporarily unavailable because no ZeroGPU inference worker is connected."

        probe_endpoints = [
            f"{self._space_url}/gradio_api/call/health",
            f"{self._space_url}/call/health",
            f"{self._space_url}/config",
            f"{self._space_url}/info",
            f"{self._space_url}/api/predict",
            f"{self._space_url}/",
        ]

        last_error = ""
        is_sleeping = False

        for endpoint in probe_endpoints:
            try:
                headers = self._build_headers(include_content_type=False)
                req = urllib.request.Request(endpoint, headers=headers, method="GET")
                with urllib.request.urlopen(req, timeout=5) as resp:
                    if resp.status == 200:
                        body = resp.read().decode("utf-8", errors="ignore")
                        # Parse reported hardware if available
                        try:
                            data = json.loads(body)
                            if isinstance(data, dict):
                                device = data.get("device") or data.get("hardware")
                                if device:
                                    self._reported_hardware = str(device).strip()
                                    return True, f"ZeroGPU worker genuinely reachable at {self._space_url} (Hardware: {self._reported_hardware})."
                        except Exception:
                            pass
                        return True, f"ZeroGPU worker genuinely reachable at {self._space_url}."
            except urllib.error.HTTPError as h_err:
                last_error = f"HTTP {h_err.code} {h_err.reason}"
                if h_err.code in (401, 403):
                    return False, f"ZeroGPU worker at {self._space_url} rejected authentication ({last_error}). Verify HF_TOKEN."
                if h_err.code == 429:
                    return False, "Hugging Face ZeroGPU compute quota is currently exhausted (rolling 24-hour usage window)."
                if h_err.code in (502, 503, 504):
                    is_sleeping = True
                    continue
                continue
            except urllib.error.URLError as u_err:
                last_error = str(u_err.reason)
                return False, f"ZeroGPU worker at {self._space_url} is unreachable: {last_error}"
            except Exception as exc:
                last_error = str(exc)
                return False, f"ZeroGPU worker at {self._space_url} connection error: {last_error}"

        if is_sleeping:
            return True, f"ZeroGPU worker is waking up from sleep at {self._space_url}. Inference may take 30-60s to boot."

        return False, f"ZeroGPU worker at {self._space_url} is unreachable: {last_error or 'No responsive endpoint'}"

    def _resolve_space_repo_id(self) -> Optional[str]:
        """Resolves Hugging Face Space repo slug (e.g. 'fashn-ai/fashn-vton-1.5') without GPU calls."""
        explicit_id = (os.getenv("HF_SPACE_ID") or "").strip()
        if "/" in explicit_id:
            return explicit_id
        if not self._space_url:
            return None
        try:
            req = urllib.request.Request(
                f"{self._space_url}/",
                headers=self._build_headers(include_content_type=False),
                method="GET",
            )
            with urllib.request.urlopen(req, timeout=4) as resp:
                link_header = resp.headers.get("Link") or resp.headers.get("link") or ""
                m = re.search(r"https://huggingface\.co/spaces/([^/>;\s]+/[^/>;\s]+)", link_header)
                if m:
                    return m.group(1)
        except Exception as exc:
            logger.debug(f"Could not resolve HF space repo id: {exc}")
        return None

    def check_space_runtime(self) -> Dict[str, Any]:
        """Queries Hugging Face Space runtime state (RUNNING/SLEEPING/hardware) without submitting jobs."""
        repo_id = self._resolve_space_repo_id()
        if not repo_id:
            return {}
        try:
            url = f"https://huggingface.co/api/spaces/{repo_id}/runtime"
            req = urllib.request.Request(url, headers=self._build_headers(include_content_type=False), method="GET")
            with urllib.request.urlopen(req, timeout=4) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    hw = (data.get("hardware") or {}).get("current")
                    if hw:
                        self._reported_hardware = str(hw).strip()
                    return {
                        "repo_id": repo_id,
                        "stage": data.get("stage"),
                        "hardware": hw,
                        "sha": data.get("sha"),
                    }
        except Exception as exc:
            logger.debug(f"Could not query HF Space runtime for '{repo_id}': {exc}")
        return {}

    def check_hf_account_quota(self) -> Dict[str, Any]:
        """
        Queries official Hugging Face ZeroGPU account quota endpoint when HF_TOKEN is configured.
        Returns normalized quota info without ever exposing tokens in outputs or logs.
        """
        if not self._hf_token:
            return {
                "authenticated": False,
                "token_configured": False,
                "resets_at": None,
                "quota_exhausted": None,
                "note": "No server-side HF_TOKEN configured; unauthenticated IP quota is rolling 24h.",
            }
        try:
            req = urllib.request.Request(
                "https://huggingface.co/api/spaces/zero-gpu/quota",
                headers=self._build_headers(include_content_type=False),
                method="GET",
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    raw_reset = data.get("resetsAt") if data.get("resetsAt") is not None else data.get("resets_at")
                    resets_iso = None
                    if isinstance(raw_reset, (int, float)) and raw_reset > 0:
                        ts_sec = raw_reset / 1000.0 if raw_reset > 1e11 else float(raw_reset)
                        resets_iso = datetime.fromtimestamp(ts_sec, tz=timezone.utc).isoformat()
                    elif isinstance(raw_reset, str) and raw_reset.strip():
                        resets_iso = raw_reset.strip()
                    current_val = data.get("current")
                    quota_exhausted = (float(current_val) <= 0) if isinstance(current_val, (int, float)) else None
                    return {
                        "authenticated": True,
                        "token_configured": True,
                        "base": data.get("base"),
                        "current": current_val,
                        "overquota_used": data.get("overquotaUsed"),
                        "resets_at": resets_iso,
                        "quota_exhausted": quota_exhausted,
                    }
        except urllib.error.HTTPError as h_err:
            if h_err.code in (401, 403):
                logger.warning(f"Official HF ZeroGPU quota API rejected configured HF_TOKEN (HTTP {h_err.code}).")
                return {
                    "authenticated": False,
                    "token_configured": True,
                    "status_code": h_err.code,
                    "resets_at": None,
                    "quota_exhausted": None,
                    "note": f"Configured HF_TOKEN was rejected by Hugging Face (HTTP {h_err.code}).",
                }
            logger.debug(f"Could not query official HF ZeroGPU quota API (HTTP {h_err.code}).")
            return {
                "authenticated": None,
                "token_configured": True,
                "status_code": h_err.code,
                "resets_at": None,
                "quota_exhausted": None,
                "note": f"Could not query Hugging Face ZeroGPU quota API (HTTP {h_err.code}).",
            }
        except Exception as exc:
            logger.debug(f"Could not query official HF ZeroGPU quota API: {redact_sensitive_text(str(exc))}")
        return {
            "authenticated": None,
            "token_configured": True,
            "resets_at": None,
            "quota_exhausted": None,
            "note": "Could not verify Hugging Face ZeroGPU quota.",
        }

    def _sync_db_session(
        self,
        db: Optional[Any],
        session_id: str,
        status: str,
        progress: int,
        stage_message: str,
        result_image_url: Optional[str] = None,
        error_message: Optional[str] = None,
        error_category: Optional[str] = None,
        retry_after_seconds: Optional[int] = None,
        quota_resets_at: Optional[str] = None,
    ) -> None:
        """Synchronizes execution progress and state with PostgreSQL TryOnSession record."""
        if db is None:
            return

        try:
            from app.models import TryOnSession
            session = db.get(TryOnSession, session_id)
            if session:
                session.status = status
                session.progress_percentage = progress
                session.stage_message = str(stage_message)[:250] if stage_message else None
                session.provider = self.provider_name
                session.provenance = "genuine_zerogpu"
                session.result_image_url = result_image_url
                session.error_message = str(error_message)[:1000] if error_message else None
                session.error_category = error_category[:64] if error_category else None
                session.retry_after_seconds = retry_after_seconds
                session.quota_resets_at = quota_resets_at[:64] if quota_resets_at else None
                session.updated_at = datetime.now(timezone.utc)
                db.commit()
                db.refresh(session)
        except Exception as exc:
            logger.warning(f"Failed to synchronize TryOnSession '{session_id}' in DB: {exc}")
            try:
                db.rollback()
            except Exception:
                pass

    async def _resolve_image_bytes(self, source: str) -> Tuple[bytes, str, str]:
        """
        Resolves local filepath, upload URL, or remote URL to (raw_bytes, mime_type, extension).
        """
        source_str = str(source).strip()

        # 1. Check local private customer photos
        try:
            photo_path = get_customer_photo_path(source_str)
            if photo_path.exists() and photo_path.is_file():
                raw = photo_path.read_bytes()
                mime, ext = detect_image_mime_and_ext(raw)
                return raw, mime, ext
        except (ValueError, FileNotFoundError):
            pass

        # 2. Check local path
        p = Path(source_str)
        if p.exists() and p.is_file():
            raw = p.read_bytes()
            mime, ext = detect_image_mime_and_ext(raw)
            return raw, mime, ext

        # 3. Check public uploads directory mapping (/uploads/xyz.jpg)
        if "/uploads/" in source_str:
            fname = source_str.split("/uploads/")[-1].split("?")[0]
            base_dir = Path(__file__).resolve().parent.parent.parent.parent
            local_upload = base_dir / "uploads" / fname
            if local_upload.exists() and local_upload.is_file():
                raw = local_upload.read_bytes()
                mime, ext = detect_image_mime_and_ext(raw)
                return raw, mime, ext

        # 4. Remote HTTP URL
        if source_str.startswith(("http://", "https://")):
            req = urllib.request.Request(source_str, headers={"User-Agent": "VirtualFitAI/1.0"})

            def _fetch():
                with urllib.request.urlopen(req, timeout=15) as r:
                    return r.read()

            try:
                raw = await asyncio.to_thread(_fetch)
            except (TimeoutError, socket.timeout) as exc:
                raise _ZeroGPUClassifiedError(
                    category=ERR_NETWORK_TIMEOUT,
                    public_message="Fetching the garment reference image timed out. Please try again.",
                    technical_detail=f"Source image fetch timed out ({source_str}): {exc}",
                    retry_after_seconds=15,
                )
            except Exception as exc:
                raise _ZeroGPUClassifiedError(
                    category=ERR_INVALID_INPUTS,
                    public_message="Could not load the selected garment reference image. Please choose another item and try again.",
                    technical_detail=f"Source image fetch failed ({source_str}): {exc}",
                    retry_after_seconds=0,
                )
            mime, ext = detect_image_mime_and_ext(raw)
            return raw, mime, ext

        raise FileNotFoundError(f"Image source could not be resolved: '{source_str}'")

    def _upload_file_to_gradio(self, file_bytes: bytes, filename: str, mime: str) -> Optional[str]:
        """
        Attempts to stage file on the remote Gradio Space via /gradio_api/upload or /upload.
        Returns the remote path string if successful, None if upload route is unsupported (404/405),
        or raises _ZeroGPUClassifiedError on genuine staging rejections/timeouts/5xx.
        """
        upload_endpoints = [
            f"{self._space_url}/gradio_api/upload",
            f"{self._space_url}/upload",
        ]
        boundary = f"----WebKitFormBoundary{uuid.uuid4().hex}"
        body = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="files"; filename="{filename}"\r\n'
            f"Content-Type: {mime}\r\n\r\n"
        ).encode("utf-8") + file_bytes + f"\r\n--{boundary}--\r\n".encode("utf-8")

        headers = self._build_headers(include_content_type=False)
        headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"

        sleeping_error = None
        for endpoint in upload_endpoints:
            req = urllib.request.Request(endpoint, data=body, headers=headers, method="POST")
            try:
                with urllib.request.urlopen(req, timeout=30) as resp:
                    if resp.status == 200:
                        resp_json = json.loads(resp.read().decode("utf-8"))
                        if isinstance(resp_json, list) and len(resp_json) > 0:
                            return resp_json[0]
            except urllib.error.HTTPError as h_err:
                err_body = ""
                try:
                    err_body = h_err.read().decode("utf-8", errors="ignore")
                except Exception:
                    pass
                logger.warning(f"Upload endpoint '{endpoint}' returned HTTP {h_err.code}: {err_body[:200]}")
                if h_err.code in (404, 405):
                    continue
                if h_err.code in (502, 503, 504):
                    sleeping_error = h_err
                    continue
                if h_err.code == 429:
                    raise classify_upstream_error(raw_message=err_body, status_code=429, exc=h_err)
                if h_err.code in (401, 403):
                    raise classify_upstream_error(raw_message=f"Upload auth HTTP {h_err.code}", status_code=h_err.code, exc=h_err)
                if h_err.code in (400, 413, 422, 500):
                    raise _ZeroGPUClassifiedError(
                        category=ERR_UPLOAD_FAILED,
                        public_message="Failed to upload images to the AI worker. Please ensure both images are valid and under 10 MB.",
                        technical_detail=f"Upload staging HTTP {h_err.code} at {endpoint}: {err_body[:200]}",
                        retry_after_seconds=0 if h_err.code in (400, 413, 422) else 20,
                    )
                continue
            except (TimeoutError, socket.timeout) as t_err:
                raise _ZeroGPUClassifiedError(
                    category=ERR_UPLOAD_FAILED,
                    public_message="Uploading customer or garment images to the AI worker timed out. Please try again.",
                    technical_detail=f"Upload staging timed out at {endpoint}: {t_err}",
                    retry_after_seconds=20,
                )
            except Exception as exc:
                logger.debug(f"Upload endpoint '{endpoint}' skipped ({exc}).")
                continue

        if sleeping_error is not None:
            raise classify_upstream_error(status_code=getattr(sleeping_error, "code", 503), exc=sleeping_error)
        return None

    def _download_image_from_urls(self, candidate_urls: List[str]) -> Tuple[bytes, str]:
        """Downloads and validates MIME type from the first reachable result URL."""
        last_exc: Optional[Exception] = None
        for idx, file_url in enumerate(candidate_urls):
            req = urllib.request.Request(file_url, headers=self._build_download_headers(file_url))
            try:
                with urllib.request.urlopen(req, timeout=30) as r:
                    raw = r.read()
                _, ext = detect_image_mime_and_ext(raw)
                return raw, ext
            except urllib.error.HTTPError as h_err:
                last_exc = h_err
                if h_err.code == 404 and idx + 1 < len(candidate_urls):
                    continue
                raise
        if last_exc is not None:
            raise last_exc
        raise ValueError("No result image URL was provided by ZeroGPU worker.")

    def _fetch_result_bytes(self, image_output: Any) -> Tuple[bytes, str]:
        """
        Extracts raw image bytes and detected extension from Gradio's output object.
        Supports:
        - dict with 'url': {"url": "https://.../file=/tmp/..."}
        - dict with 'path': {"path": "/tmp/.../result.png"}
        - data URL string: 'data:image/png;base64,...'
        - raw URL string: 'https://...'
        """
        if isinstance(image_output, dict):
            if "url" in image_output and image_output["url"]:
                file_url = image_output["url"]
                if not file_url.startswith(("http://", "https://")):
                    file_url = f"{self._space_url}{file_url}"
                return self._download_image_from_urls([file_url])

            if "path" in image_output and image_output["path"]:
                path_str = image_output["path"]
                if path_str.startswith("data:"):
                    return parse_data_url_to_bytes(path_str)
                # Gradio server-side file endpoint (classic /file= and Gradio 5/6 /gradio_api/file=)
                return self._download_image_from_urls([
                    f"{self._space_url}/file={path_str}",
                    f"{self._space_url}/gradio_api/file={path_str}",
                ])

        if isinstance(image_output, str):
            if image_output.startswith("data:"):
                return parse_data_url_to_bytes(image_output)
            if image_output.startswith(("http://", "https://")):
                return self._download_image_from_urls([image_output])

        raise ValueError(f"Unrecognized image output format from ZeroGPU worker: {type(image_output)}")

    def _inspect_space_config(self) -> Optional[Dict[str, Any]]:
        """
        Queries Gradio /config to detect api_prefix, api_name, fn_index, trigger_id, and input arity.
        Returns None when the Space does not expose valid JSON /config (e.g. legacy mock or HTML proxy).
        """
        try:
            cfg_req = urllib.request.Request(
                f"{self._space_url}/config",
                headers=self._build_headers(include_content_type=False),
                method="GET",
            )
            with urllib.request.urlopen(cfg_req, timeout=5) as cfg_resp:
                if cfg_resp.status != 200:
                    return None
                raw_body = cfg_resp.read().decode("utf-8", errors="ignore")
                cfg_data = json.loads(raw_body)
                if not isinstance(cfg_data, dict):
                    return None
                api_prefix = str(cfg_data.get("api_prefix") or "").rstrip("/")
                for dep in cfg_data.get("dependencies", []):
                    a_name = dep.get("api_name")
                    if a_name in ("try_on", "tryon"):
                        fn_index = dep.get("id")
                        targets = dep.get("targets") or []
                        trigger_id = None
                        if (
                            isinstance(targets, list)
                            and len(targets) > 0
                            and isinstance(targets[0], (list, tuple))
                            and len(targets[0]) > 0
                        ):
                            try:
                                trigger_id = int(targets[0][0])
                            except (TypeError, ValueError):
                                trigger_id = None
                        return {
                            "api_prefix": api_prefix,
                            "api_name": a_name,
                            "fn_index": fn_index if isinstance(fn_index, int) else None,
                            "trigger_id": trigger_id,
                            "input_count": len(dep.get("inputs") or []),
                        }
        except Exception:
            return None
        return None

    def _execute_gradio_queue_join(
        self,
        api_prefix: str,
        fn_index: int,
        trigger_id: Optional[int],
        payload_data: list,
        session_id: str,
        db: Optional[Any],
    ) -> Any:
        """
        Executes Gradio native queue protocol (/queue/join + /queue/data?session_hash=...),
        which preserves full unstripped JSON errors (including ZeroGPU quota & traceback metadata)
        that /gradio_api/call/<api> strips to 'data: null'.
        """
        import time

        prefix = f"/{api_prefix.strip('/')}" if api_prefix and api_prefix.strip("/") else ""
        base_api = f"{self._space_url}{prefix}"
        session_hash = uuid.uuid4().hex[:11]

        join_payload: Dict[str, Any] = {
            "data": payload_data,
            "fn_index": fn_index,
            "session_hash": session_hash,
        }
        if trigger_id is not None:
            join_payload["trigger_id"] = trigger_id

        join_url = f"{base_api}/queue/join"
        join_req = urllib.request.Request(
            join_url,
            data=json.dumps(join_payload).encode("utf-8"),
            headers=self._build_headers(include_content_type=True),
            method="POST",
        )
        with urllib.request.urlopen(join_req, timeout=30) as resp:
            if resp.status != 200:
                raise RuntimeError(f"Gradio queue/join returned HTTP {resp.status}")
            join_resp = json.loads(resp.read().decode("utf-8"))

        if "event_id" not in join_resp and "data" in join_resp:
            return join_resp["data"]

        sse_url = f"{base_api}/queue/data?session_hash={session_hash}"
        sse_req = urllib.request.Request(
            sse_url,
            headers=self._build_headers(include_content_type=False),
            method="GET",
        )
        sse_req.add_header("Accept", "text/event-stream")

        t0 = time.monotonic()
        with urllib.request.urlopen(sse_req, timeout=60) as stream:
            while True:
                if (time.monotonic() - t0) > self._timeout_seconds:
                    raise TimeoutError(
                        f"ZeroGPU inference exceeded configured timeout of {self._timeout_seconds}s "
                        f"(queue wait + diffusion synthesis)."
                    )

                line = stream.readline()
                if not line:
                    break

                line_str = line.decode("utf-8", errors="ignore").strip()
                if not line_str.startswith("data:"):
                    continue

                data_str = line_str.split(":", 1)[1].strip()
                if not data_str:
                    continue

                try:
                    evt = json.loads(data_str)
                except Exception:
                    continue

                msg = evt.get("msg")
                if msg in ("send_hash", "heartbeat"):
                    continue
                elif msg == "estimation":
                    q_rank = evt.get("rank")
                    stage_msg = (
                        f"Waiting in Hugging Face ZeroGPU queue (position: {q_rank})..."
                        if isinstance(q_rank, int)
                        else "Waiting in Hugging Face ZeroGPU queue..."
                    )
                    self._sync_db_session(db, session_id, "processing", 30, stage_msg)
                elif msg == "process_starts":
                    stage_msg = f"ZeroGPU allocated. Neural diffusion synthesis in progress ({self._num_timesteps} steps)..."
                    self._sync_db_session(db, session_id, "processing", 50, stage_msg)
                elif msg in ("process_generating", "generating", "progress"):
                    self._sync_db_session(db, session_id, "processing", 75, "Generating virtual try-on image...")
                elif msg == "queue_full":
                    raise classify_upstream_error(raw_message="queue is full", title="Queue full")
                elif msg == "unexpected_error":
                    raw_err = str(evt.get("message") or evt.get("error") or "Unexpected worker error")
                    raise classify_upstream_error(raw_message=raw_err, title=str(evt.get("title") or ""))
                elif msg == "process_completed":
                    if evt.get("success") is True:
                        out_obj = evt.get("output") or {}
                        return out_obj.get("data") if isinstance(out_obj, dict) else out_obj
                    out_obj = evt.get("output") if isinstance(evt.get("output"), dict) else {}
                    raw_err = str(out_obj.get("error") or evt.get("error") or "")
                    title = str(out_obj.get("title") or evt.get("title") or "")
                    lower_combined = f"{title} {raw_err}".lower()
                    resets_at = None
                    if ("quota" in lower_combined or "runs limit" in lower_combined) and self._hf_token:
                        resets_at = self.check_hf_account_quota().get("resets_at")
                    raise classify_upstream_error(raw_message=raw_err, title=title, quota_resets_at=resets_at)
                elif msg == "close_stream":
                    break

        raise _ZeroGPUClassifiedError(
            category=ERR_NETWORK_TIMEOUT,
            public_message="The AI worker stream closed unexpectedly before returning an image. Please try again.",
            technical_detail="ZeroGPU queue/data SSE stream ended without emitting process_completed.",
            retry_after_seconds=20,
        )

    def _execute_gradio_queue_call(
        self,
        call_url: str,
        payload_data: list,
        session_id: str,
        db: Optional[Any],
    ) -> Any:
        """
        Executes Gradio 4/5 Queue submission and Server-Sent Events (SSE) status polling.
        Tracks ZeroGPU queue positions, process starts, and completed output.
        """
        # 1. Post to call endpoint to obtain event_id
        submit_req = urllib.request.Request(
            call_url,
            data=json.dumps({"data": payload_data}).encode("utf-8"),
            headers=self._build_headers(include_content_type=True),
            method="POST",
        )

        with urllib.request.urlopen(submit_req, timeout=30) as resp:
            if resp.status != 200:
                raise RuntimeError(f"Gradio call submission returned HTTP {resp.status}")
            submit_resp = json.loads(resp.read().decode("utf-8"))

        event_id = submit_resp.get("event_id")
        if not event_id:
            # Older Gradio returned direct data
            if "data" in submit_resp:
                return submit_resp["data"]
            raise RuntimeError(f"Gradio call response did not contain an event_id: {submit_resp}")

        # 2. Open SSE stream for status updates and result
        sse_url = f"{call_url}/{event_id}"
        sse_req = urllib.request.Request(
            sse_url,
            headers=self._build_headers(include_content_type=False),
            method="GET",
        )
        sse_req.add_header("Accept", "text/event-stream")

        import time
        t0 = time.monotonic()

        with urllib.request.urlopen(sse_req, timeout=60) as stream:
            current_event = None

            while True:
                elapsed = time.monotonic() - t0
                if elapsed > self._timeout_seconds:
                    raise TimeoutError(
                        f"ZeroGPU inference exceeded configured timeout of {self._timeout_seconds}s "
                        f"(queue wait + diffusion synthesis)."
                    )

                line = stream.readline()
                if not line:
                    break

                line_str = line.decode("utf-8", errors="ignore").strip()

                if line_str.startswith("event:"):
                    current_event = line_str.split(":", 1)[1].strip()
                elif line_str.startswith("data:"):
                    data_str = line_str.split(":", 1)[1].strip()

                    if current_event == "heartbeat":
                        # Worker is actively running; keep connection open
                        continue

                    elif current_event == "estimation":
                        try:
                            est = json.loads(data_str)
                            if isinstance(est, (list, tuple)) and len(est) >= 1:
                                q_pos = est[0]
                                q_eta = est[1] if len(est) > 1 else 0
                                stage_msg = f"Queued in ZeroGPU (position: {q_pos}, estimated wait: {q_eta:.0f}s)..."
                                self._sync_db_session(db, session_id, "processing", 30, stage_msg)
                        except Exception:
                            pass

                    elif current_event == "process_starts":
                        stage_msg = f"ZeroGPU allocated. Neural diffusion synthesis in progress ({self._num_timesteps} steps)..."
                        self._sync_db_session(db, session_id, "processing", 50, stage_msg)

                    elif current_event == "generating":
                        self._sync_db_session(db, session_id, "processing", 75, "Generating virtual try-on image...")

                    elif current_event == "complete":
                        try:
                            complete_data = json.loads(data_str)
                            return complete_data
                        except Exception as exc:
                            raise _ZeroGPUClassifiedError(
                                category=ERR_INFERENCE_EXCEPTION,
                                public_message="The AI worker returned malformed completion data.",
                                technical_detail=f"Failed to parse completed Gradio event data: {exc}",
                                retry_after_seconds=20,
                            )

                    elif current_event == "error":
                        if not data_str or data_str == "null":
                            # Gradio /call/ strips exceptions to 'data: null'; never assume quota exhaustion blindly.
                            raise _ZeroGPUClassifiedError(
                                category=ERR_INFERENCE_EXCEPTION,
                                public_message="The AI worker aborted or rejected execution during processing. Please try again shortly.",
                                technical_detail="ZeroGPU worker emitted Gradio SSE 'event: error' with 'data: null'.",
                                retry_after_seconds=30,
                            )
                        raise classify_upstream_error(raw_message=data_str)

        raise _ZeroGPUClassifiedError(
            category=ERR_NETWORK_TIMEOUT,
            public_message="Connection to the AI inference worker ended before completion. Please try again.",
            technical_detail="ZeroGPU SSE event stream ended without emitting a complete event.",
            retry_after_seconds=20,
        )

    async def process_tryon(
        self,
        session_id: str,
        customer_photo_path: str,
        garment_image_url: str,
        category: Optional[str] = None,
        db: Optional[Any] = None,
    ) -> TryOnExecutionResult:
        """
        Executes genuine FASHN VTON v1.5 virtual try-on inference via Hugging Face ZeroGPU.
        Strictly enforces that no session is marked completed without a validated result image.
        """
        start_time = datetime.now(timezone.utc)
        logger.info(f"[ZeroGPU] Starting virtual try-on inference for session '{session_id}'...")

        # 1. Pre-flight check
        if not self._space_url:
            err_msg = "AI generation is temporarily unavailable because no ZeroGPU inference worker is connected."
            self._sync_db_session(
                db=db,
                session_id=session_id,
                status="failed",
                progress=0,
                stage_message=f"AI generation failed: {err_msg}",
                error_message=err_msg,
                error_category=ERR_WORKER_UNAVAILABLE,
                retry_after_seconds=60,
            )
            return TryOnExecutionResult(
                session_id=session_id,
                status="failed",
                progress_percentage=0,
                stage_message=f"AI generation failed: {err_msg}",
                provider=self.provider_name,
                result_image_url=None,
                error_message=err_msg,
                error_category=ERR_WORKER_UNAVAILABLE,
                retry_after_seconds=60,
                metadata={"is_simulation": False},
            )

        self._sync_db_session(
            db=db,
            session_id=session_id,
            status="processing",
            progress=15,
            stage_message="Loading and validating customer and garment reference images...",
        )

        try:
            # 2. Normalize and strictly validate category triad
            fashn_category = normalize_garment_category(category=category)
            logger.info(f"[ZeroGPU] Normalized garment category: '{fashn_category}'")

            # 3. Read image bytes and detect verified MIME types
            person_bytes, person_mime, person_ext = await self._resolve_image_bytes(customer_photo_path)
            garment_bytes, garment_mime, garment_ext = await self._resolve_image_bytes(garment_image_url)

            # Stage inputs via /upload or inline data URL
            person_remote_path = await asyncio.to_thread(
                self._upload_file_to_gradio,
                person_bytes,
                f"person_{session_id[:8]}{person_ext}",
                person_mime,
            )
            garment_remote_path = await asyncio.to_thread(
                self._upload_file_to_gradio,
                garment_bytes,
                f"garment_{session_id[:8]}{garment_ext}",
                garment_mime,
            )

            # Build exact Gradio component inputs matching app.py
            person_arg = {"path": person_remote_path} if person_remote_path else image_to_base64_data_url(person_bytes)
            garment_arg = {"path": garment_remote_path} if garment_remote_path else image_to_base64_data_url(garment_bytes)

            self._sync_db_session(
                db=db,
                session_id=session_id,
                status="processing",
                progress=25,
                stage_message="Submitting task to Hugging Face ZeroGPU worker...",
            )

            # 4. Dispatch via /queue/join + /queue/data primary when /config provides fn_index,
            #    falling back gracefully to /call/<api_name> or /api/predict/ when /config is absent.
            def _dispatch_worker():
                space_cfg = self._inspect_space_config()
                discovered_api = space_cfg.get("api_name") if space_cfg else None

                if space_cfg and space_cfg.get("fn_index") is not None:
                    use_8_args = discovered_api == "try_on" or space_cfg.get("input_count", 0) >= 8
                    join_args = (
                        [person_arg, garment_arg, fashn_category, "model", self._num_timesteps, 1.5, 42, True]
                        if use_8_args
                        else [person_arg, garment_arg, fashn_category, self._num_timesteps]
                    )
                    try:
                        return self._execute_gradio_queue_join(
                            api_prefix=space_cfg.get("api_prefix", ""),
                            fn_index=space_cfg["fn_index"],
                            trigger_id=space_cfg.get("trigger_id"),
                            payload_data=join_args,
                            session_id=session_id,
                            db=db,
                        )
                    except urllib.error.HTTPError as h_err:
                        err_body = ""
                        try:
                            err_body = h_err.read().decode("utf-8", errors="ignore")
                        except Exception:
                            pass
                        if h_err.code not in (404, 405):
                            resets_at = self.check_hf_account_quota().get("resets_at") if (h_err.code == 429 and self._hf_token) else None
                            raise classify_upstream_error(raw_message=err_body, status_code=h_err.code, exc=h_err, quota_resets_at=resets_at)
                        logger.debug(f"Gradio /queue/join unavailable ({h_err.code}); trying /call/ fallback.")
                    except (_ZeroGPUWorkerExecutionError, TimeoutError):
                        raise
                    except Exception as exc:
                        if isinstance(exc, (urllib.error.URLError, socket.timeout, ConnectionResetError)):
                            raise classify_upstream_error(exc=exc)
                        logger.debug(f"Gradio /queue/join skipped ({exc}); trying /call/ fallback.")

                # Build candidate endpoints based on discovery or standard order
                candidate_endpoints = []
                if discovered_api == "try_on":
                    candidate_endpoints.extend([
                        (f"{self._space_url}/gradio_api/call/try_on", [person_arg, garment_arg, fashn_category, "model", self._num_timesteps, 1.5, 42, True]),
                        (f"{self._space_url}/call/try_on", [person_arg, garment_arg, fashn_category, "model", self._num_timesteps, 1.5, 42, True]),
                        (f"{self._space_url}/gradio_api/call/tryon", [person_arg, garment_arg, fashn_category, self._num_timesteps]),
                        (f"{self._space_url}/call/tryon", [person_arg, garment_arg, fashn_category, self._num_timesteps]),
                    ])
                else:
                    candidate_endpoints.extend([
                        (f"{self._space_url}/gradio_api/call/tryon", [person_arg, garment_arg, fashn_category, self._num_timesteps]),
                        (f"{self._space_url}/gradio_api/call/try_on", [person_arg, garment_arg, fashn_category, "model", self._num_timesteps, 1.5, 42, True]),
                        (f"{self._space_url}/call/tryon", [person_arg, garment_arg, fashn_category, self._num_timesteps]),
                        (f"{self._space_url}/call/try_on", [person_arg, garment_arg, fashn_category, "model", self._num_timesteps, 1.5, 42, True]),
                    ])

                candidate_endpoints.append(
                    (f"{self._space_url}/api/predict/", [person_arg, garment_arg, fashn_category, self._num_timesteps])
                )

                last_exc = None
                for c_url, c_payload in candidate_endpoints:
                    try:
                        if "/call/" in c_url:
                            return self._execute_gradio_queue_call(
                                call_url=c_url,
                                payload_data=c_payload,
                                session_id=session_id,
                                db=db,
                            )
                        else:
                            # Direct /api/predict fallback
                            req = urllib.request.Request(
                                c_url,
                                data=json.dumps({"data": c_payload}).encode("utf-8"),
                                headers=self._build_headers(include_content_type=True),
                                method="POST",
                            )
                            with urllib.request.urlopen(req, timeout=self._timeout_seconds) as r:
                                res_json = json.loads(r.read().decode("utf-8"))
                                return res_json.get("data", [])
                    except urllib.error.HTTPError as h_err:
                        last_exc = h_err
                        if h_err.code in (404, 405, 422, 500):
                            # Try next candidate endpoint if route or signature differs
                            continue
                        err_body = ""
                        try:
                            err_body = h_err.read().decode("utf-8", errors="ignore")
                        except Exception:
                            pass
                        resets_at = self.check_hf_account_quota().get("resets_at") if (h_err.code == 429 and self._hf_token) else None
                        raise classify_upstream_error(raw_message=err_body, status_code=h_err.code, exc=h_err, quota_resets_at=resets_at)
                    except (_ZeroGPUWorkerExecutionError, TimeoutError):
                        raise
                    except Exception as e:
                        last_exc = e
                        logger.warning(f"ZeroGPU queue endpoint '{c_url}' raised: {e}")
                        if "/call/" in c_url:
                            continue
                        raise

                if last_exc:
                    if isinstance(last_exc, urllib.error.HTTPError):
                        err_body = ""
                        try:
                            err_body = last_exc.read().decode("utf-8", errors="ignore")
                        except Exception:
                            pass
                        raise classify_upstream_error(raw_message=err_body, status_code=last_exc.code, exc=last_exc)
                    raise classify_upstream_error(exc=last_exc)
                raise _ZeroGPUClassifiedError(
                    category=ERR_WORKER_UNAVAILABLE,
                    public_message="The AI inference endpoint did not respond. Please try again shortly.",
                    technical_detail="No candidate Gradio endpoint responded successfully.",
                    retry_after_seconds=60,
                )

            output_data = await asyncio.to_thread(_dispatch_worker)

            if not output_data:
                raise ValueError("ZeroGPU worker returned empty response data.")

            raw_image_output = output_data[0] if isinstance(output_data, list) else output_data

            # 5. Extract and validate genuine image binary
            result_bytes, detected_ext = await asyncio.to_thread(self._fetch_result_bytes, raw_image_output)

            if len(result_bytes) < 1000:
                raise ValueError(f"Received result image is too small ({len(result_bytes)} bytes) to be valid.")

            # Validate magic byte signature
            is_valid_magic = (
                result_bytes.startswith(b"\xff\xd8\xff")  # JPEG
                or result_bytes.startswith(b"\x89PNG\r\n\x1a\n")  # PNG
                or (result_bytes.startswith(b"RIFF") and result_bytes[8:12] == b"WEBP")  # WebP
            )
            if not is_valid_magic:
                raise ValueError("Received result binary is not a valid JPEG, PNG, or WebP image.")

            # Validate dimensions
            dims = parse_image_dimensions(result_bytes, detected_ext)
            if dims is not None:
                w, h = dims
                if w < 100 or h < 100 or w > 4096 or h > 4096:
                    raise ValueError(f"Result image dimensions ({w}x{h}) outside permissible bounds (100-4096).")

            # 6. Save genuine result to private RESULTS_DIR
            RESULTS_DIR.mkdir(parents=True, exist_ok=True)
            result_filename = f"res_{session_id}{detected_ext}"
            result_path = RESULTS_DIR / result_filename
            result_path.write_bytes(result_bytes)

            # Ensure file is saved and verified on disk
            if not result_path.exists() or result_path.stat().st_size == 0:
                raise IOError(f"Failed to persist result image to disk at '{result_path}'.")

            duration_seconds = (datetime.now(timezone.utc) - start_time).total_seconds()
            result_url = f"/api/tryon/{session_id}/result"

            # 7. Hardware attribution (never claim A100/L4 unless explicitly reported)
            if self._reported_hardware:
                device_label = f"ZeroGPU ({self._reported_hardware})"
                completed_msg = f"Virtual try-on synthesized successfully via Hugging Face ZeroGPU ({self._reported_hardware})."
            else:
                device_label = "ZeroGPU Worker"
                completed_msg = "Virtual try-on synthesized successfully via Hugging Face ZeroGPU worker."

            logger.info(
                f"[ZeroGPU] Success for session '{session_id}' in {duration_seconds:.2f}s! "
                f"Saved result: {result_filename} ({len(result_bytes)} bytes)"
            )

            # 8. Commit completed status to PostgreSQL
            self._sync_db_session(
                db=db,
                session_id=session_id,
                status="completed",
                progress=100,
                stage_message=completed_msg,
                result_image_url=result_url,
            )

            return TryOnExecutionResult(
                session_id=session_id,
                status="completed",
                progress_percentage=100,
                stage_message=completed_msg,
                provider=self.provider_name,
                result_image_url=result_url,
                error_message=None,
                metadata={
                    "device": device_label,
                    "category": fashn_category,
                    "timesteps": self._num_timesteps,
                    "duration_seconds": round(duration_seconds, 2),
                    "space_url": self._space_url,
                    "is_simulation": False,
                },
            )

        except Exception as exc:
            duration_seconds = (datetime.now(timezone.utc) - start_time).total_seconds()
            classified = classify_upstream_error(exc=exc)

            if classified.category == ERR_QUOTA_EXHAUSTED and not classified.quota_resets_at and self._hf_token:
                quota_info = await asyncio.to_thread(self.check_hf_account_quota)
                resets_at = quota_info.get("resets_at")
                if resets_at:
                    classified = classify_upstream_error(
                        raw_message=classified.technical_detail,
                        quota_resets_at=resets_at,
                        exc=classified,
                    )
                    classified.quota_resets_at = resets_at
                    classified.public_message = (
                        f"Free Hugging Face ZeroGPU compute quota is currently exhausted "
                        f"(estimated reset time: {resets_at})."
                    )

            logger.error(
                f"[ZeroGPU] Try-on inference failed for session '{session_id}' "
                f"[category={classified.category}, retry_after={classified.retry_after_seconds}s]: "
                f"{redact_sensitive_text(classified.technical_detail)}",
                exc_info=True,
            )

            public_error = sanitize_public_error_message(classified.public_message)
            stage_msg = f"AI generation failed: {public_error}"[:250]

            self._sync_db_session(
                db=db,
                session_id=session_id,
                status="failed",
                progress=0,
                stage_message=stage_msg,
                error_message=public_error,
                error_category=classified.category,
                retry_after_seconds=classified.retry_after_seconds,
                quota_resets_at=classified.quota_resets_at,
            )

            return TryOnExecutionResult(
                session_id=session_id,
                status="failed",
                progress_percentage=0,
                stage_message=stage_msg,
                provider=self.provider_name,
                result_image_url=None,
                error_message=public_error,
                error_category=classified.category,
                retry_after_seconds=classified.retry_after_seconds,
                quota_resets_at=classified.quota_resets_at,
                metadata={
                    "error_category": classified.category,
                    "technical_error": classified.technical_detail,
                    "retry_after_seconds": classified.retry_after_seconds,
                    "quota_resets_at": classified.quota_resets_at,
                    "is_simulation": False,
                    "duration_seconds": round(duration_seconds, 2),
                },
            )

    async def check_status(
        self,
        session_id: str,
        db: Optional[Any] = None,
    ) -> TryOnExecutionResult:
        """Queries status of an active or completed ZeroGPU try-on task."""
        if db is not None:
            try:
                from app.models import TryOnSession
                session = db.get(TryOnSession, session_id)
                if session:
                    device_label = f"ZeroGPU ({self._reported_hardware})" if self._reported_hardware else "ZeroGPU Worker"
                    return TryOnExecutionResult(
                        session_id=session.id,
                        status=session.status,
                        progress_percentage=session.progress_percentage,
                        stage_message=session.stage_message or "Processing virtual try-on",
                        provider=session.provider or self.provider_name,
                        result_image_url=session.result_image_url,
                        error_message=session.error_message,
                        error_category=getattr(session, "error_category", None),
                        retry_after_seconds=getattr(session, "retry_after_seconds", None),
                        quota_resets_at=getattr(session, "quota_resets_at", None),
                        metadata={"is_simulation": False, "device": device_label},
                    )
            except Exception as exc:
                logger.warning(f"Error querying session from DB: {exc}")

        return TryOnExecutionResult(
            session_id=session_id,
            status="pending",
            progress_percentage=0,
            stage_message="Virtual try-on task queued for ZeroGPU processing.",
            provider=self.provider_name,
            result_image_url=None,
            metadata={"is_simulation": False},
        )
