"""
Genuine FASHN VTON v1.5 Virtual Try-On Provider for VirtualFit AI.

Executes genuine neural diffusion try-on inference using the official FASHN VTON v1.5 TryOnPipeline.
Strictly avoids any mock responses, simulated progress, placeholder images, or fallback providers.
"""
import os
import re
import uuid
import logging
import asyncio
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any, Union

# Base and Storage interfaces
from app.services.tryon.base import BaseTryOnProvider, TryOnExecutionResult
from app.services.tryon.storage import (
    CUSTOMER_PHOTOS_DIR,
    RESULTS_DIR,
    STORAGE_ROOT,
    get_customer_photo_path,
)

logger = logging.getLogger("virtualfit.tryon.fashn")

# Base project directory
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
DEFAULT_WEIGHTS_DIR = BASE_DIR / "models" / "fashn"
UPLOAD_DIR = BASE_DIR / "uploads"

# Lazy-loaded optional dependencies
try:
    import torch
except ImportError:
    torch = None

try:
    from PIL import Image
except ImportError:
    Image = None

try:
    from fashn_vton import TryOnPipeline
except ImportError:
    TryOnPipeline = None


def normalize_garment_category(
    category: Optional[str] = None,
    product_name: Optional[str] = None,
) -> str:
    """
    Normalizes retail product categories into FASHN VTON's expected category triad:
    'tops', 'bottoms', or 'one-pieces'.

    Rules:
    - shirts, T-shirts, kurtas, jackets, and blazers -> 'tops'
    - jeans, trousers, skirts, and shorts -> 'bottoms'
    - dresses, jumpsuits, rompers, bodysuits -> 'one-pieces'
    - Does NOT classify generic 'suit' as a one-piece (e.g. 'Suit Blazer' -> tops,
      'Suit Trouser' -> bottoms, generic/standalone 'Formal Suit' -> ambiguous/rejected).
    - Rejects ambiguous or unsupported categories rather than silently misclassifying.
    """
    cat_str = (category or "").strip().lower()
    name_str = (product_name or "").strip().lower()
    combined_tokens = f"{cat_str} {name_str}".strip()

    if not combined_tokens:
        raise ValueError(
            "Garment category and product name are both empty. Cannot determine category."
        )

    # 1. Direct match with official triad
    if cat_str in ("tops", "top"):
        return "tops"
    if cat_str in ("bottoms", "bottom"):
        return "bottoms"
    if cat_str in ("one-pieces", "one-piece", "onepiece"):
        return "one-pieces"

    # Ambiguous multi-piece or generic suit patterns that cannot be resolved to a single category
    ambiguous_suit_patterns = (
        r"\bpant\s*suit\b",
        r"\bpantsuit\b",
        r"\btwo[- ]piece\s+suit\b",
        r"\bthree[- ]piece\s+suit\b",
        r"\bsalwar\s*suit\b",
        r"\bbusiness\s*suit\b",
        r"\bformal\s*suit\b",
        r"\btrack\s*suit\b",
        r"\btracksuit\b",
        r"^(?:formal\s+)?suit$",
    )
    if any(re.search(pat, combined_tokens) for pat in ambiguous_suit_patterns):
        # Unless explicitly qualified as a blazer/jacket or trouser (e.g. "Suit Trouser", "Suit Blazer")
        has_specific_top = any(re.search(pat, combined_tokens) for pat in (r"\bblazer\b", r"\bbllazer\b", r"\bjacket\b"))
        has_specific_bottom = any(re.search(pat, combined_tokens) for pat in (r"\btrouser\b", r"\btrousers\b"))
        if has_specific_top and not has_specific_bottom:
            return "tops"
        elif has_specific_bottom and not has_specific_top:
            return "bottoms"
        else:
            raise ValueError(
                f"Cannot unambiguously resolve garment category for category='{category}', "
                f"product_name='{product_name}'. Expected tops, bottoms, or one-pieces."
            )

    # 2. Unambiguous one-piece garments
    one_piece_patterns = (
        r"\bjumpsuit",
        r"\bbodysuit",
        r"\bswimsuit",
        r"\bplaysuit",
        r"\bcatsuit",
        r"\bdress\b",
        r"\bdresses\b",
        r"\bgown\b",
        r"\bgowns\b",
        r"\bfrock",
        r"\bromper",
        r"\bmaxi\b",
        r"\bdungaree",
        r"\banarkali",
    )
    is_one_piece = any(re.search(pat, combined_tokens) for pat in one_piece_patterns)

    # 3. Tops & Upper-body garments
    top_patterns = (
        r"\bshirt",
        r"\bt-shirt",
        r"\btshirt",
        r"\btee\b",
        r"\bkurta",
        r"\bkurti",
        r"\bsherwani",
        r"\bachkan",
        r"\bblazer",
        r"\bbllazer",  # common typo guard
        r"\bjacket",
        r"\bcoat\b",
        r"\bhoodie",
        r"\bsweater",
        r"\bsweatshirt",
        r"\bblouse",
        r"\bpolo\b",
        r"\bvest\b",
        r"\bcardigan",
        r"\btank\b",
        r"\btop\b",
        r"\btunic",
    )
    is_top = any(re.search(pat, combined_tokens) for pat in top_patterns)

    # 4. Bottoms & Lower-body garments
    bottom_patterns = (
        r"\bjean",
        r"\btrouser",
        r"\bpant\b",
        r"\bpants\b",
        r"\bskirt",
        r"\bshort\b",
        r"\bshorts\b",
        r"\blegging",
        r"\bchinos",
        r"\bjogger",
        r"\bcargo",
        r"\bpalazzo",
        r"\bdhoti",
        r"\bpyjama",
    )
    is_bottom = any(re.search(pat, combined_tokens) for pat in bottom_patterns)

    # Resolution logic
    # Single match resolutions
    if is_top and not is_bottom and not is_one_piece:
        return "tops"
    if is_bottom and not is_top and not is_one_piece:
        return "bottoms"
    if is_one_piece and not is_top and not is_bottom:
        return "one-pieces"

    # Compound ambiguity handling (e.g. "Suit Blazer" vs "Formal Suit")
    if is_top and is_one_piece:
        # e.g. "blazer dress" -> one-pieces, "blazer suit" -> tops
        if "dress" in combined_tokens:
            return "one-pieces"
        if "blazer" in combined_tokens or "jacket" in combined_tokens:
            return "tops"

    # Disallow generic / ambiguous suits or unmapped clothing items
    raise ValueError(
        f"Cannot unambiguously resolve garment category for category='{category}', "
        f"product_name='{product_name}'. Expected tops, bottoms, or one-pieces."
    )


def _prepare_rgb_image(img: Any) -> Any:
    """
    Safely prepares a PIL Image for neural network input:
    - Converts RGBA / LA / transparent images onto a clean white background.
    - Converts grayscale ('L') or palette ('P') images to standard 3-channel RGB.
    """
    if Image is None:
        raise ImportError("PIL (Pillow) is not installed. Please install pillow.")

    if not isinstance(img, Image.Image):
        raise TypeError(f"Expected PIL.Image.Image, got {type(img)}")

    # Handle transparency / alpha channel
    if img.mode in ("RGBA", "LA") or ("transparency" in img.info):
        alpha_img = img.convert("RGBA")
        background = Image.new("RGB", alpha_img.size, (255, 255, 255))
        background.paste(alpha_img, mask=alpha_img.split()[3])
        return background

    # Convert grayscale, palette, or CMYK to standard RGB
    if img.mode != "RGB":
        return img.convert("RGB")

    return img


def _resolve_image_source(source: Union[str, Path, Any]) -> Any:
    """
    Resolves an image source (filepath, URL, or PIL Image) into a verified RGB PIL Image.
    Protects against corrupt files and invalid image encodings.
    """
    if Image is None:
        raise ImportError("PIL (Pillow) is not installed. Please install pillow.")

    if isinstance(source, Image.Image):
        return _prepare_rgb_image(source)

    source_str = str(source).strip()
    if not source_str:
        raise ValueError("Image source path or URL cannot be empty.")

    # 1. Local path check
    candidate_path = Path(source_str)
    if candidate_path.exists() and candidate_path.is_file():
        try:
            with Image.open(candidate_path) as raw_img:
                raw_img.load()
                return _prepare_rgb_image(raw_img)
        except Exception as exc:
            raise ValueError(f"Failed to read image from '{candidate_path}': {exc}")

    # 2. Check private customer temporary storage
    try:
        resolved_customer = get_customer_photo_path(source_str)
        if resolved_customer.exists() and resolved_customer.is_file():
            with Image.open(resolved_customer) as raw_img:
                raw_img.load()
                return _prepare_rgb_image(raw_img)
    except (ValueError, FileNotFoundError):
        pass

    # 3. Check public uploads directory mapping (e.g. http://localhost:8000/uploads/xyz.jpg)
    if "/uploads/" in source_str:
        filename = source_str.split("/uploads/")[-1].split("?")[0]
        local_upload_path = UPLOAD_DIR / filename
        if local_upload_path.exists() and local_upload_path.is_file():
            try:
                with Image.open(local_upload_path) as raw_img:
                    raw_img.load()
                    return _prepare_rgb_image(raw_img)
            except Exception as exc:
                raise ValueError(f"Failed to read uploaded garment image '{local_upload_path}': {exc}")

    # 4. Remote HTTP/HTTPS URL
    if source_str.startswith(("http://", "https://")):
        import urllib.request
        import io
        try:
            req = urllib.request.Request(source_str, headers={"User-Agent": "VirtualFitAI-VTON/1.0"})
            with urllib.request.urlopen(req, timeout=10) as response:
                img_data = response.read()
            with Image.open(io.BytesIO(img_data)) as raw_img:
                raw_img.load()
                return _prepare_rgb_image(raw_img)
        except Exception as exc:
            raise ValueError(f"Failed to download remote garment image from '{source_str}': {exc}")

    raise FileNotFoundError(f"Image source could not be resolved or found: '{source_str}'")


class FashnTryOnProvider(BaseTryOnProvider):
    """
    Genuine FASHN VTON v1.5 Virtual Try-On Provider.

    Executes neural diffusion try-on inference using the official FASHN VTON TryOnPipeline.
    Implements lazy model loading, singleton pipeline caching, strict category normalization,
    and genuine result persistence.
    """

    _cached_pipeline: Optional[Any] = None
    _pipeline_lock = threading.Lock()

    def __init__(
        self,
        weights_dir: Optional[Union[str, Path]] = None,
        device: Optional[str] = None,
        num_timesteps: int = 30,
    ):
        """
        Initializes provider configuration without loading weights into memory prematurely.

        :param weights_dir: Path to official weights containing model.safetensors.
                            Defaults to FASHN_VTON_WEIGHTS_DIR or backend/models/fashn.
        :param device: Execution device ('cuda' or 'cpu'). Defaults to FASHN_VTON_DEVICE or auto-detection.
        :param num_timesteps: Diffusion inference timesteps (default: 30).
        """
        env_weights = os.getenv("FASHN_VTON_WEIGHTS_DIR") or os.getenv("FASHN_WEIGHTS_DIR")
        self._weights_dir = Path(weights_dir or env_weights or DEFAULT_WEIGHTS_DIR).resolve()

        # Configurable device selection with strict non-silent fallback
        env_device = os.getenv("FASHN_VTON_DEVICE")
        req_device = (device or env_device or "").strip().lower()

        if req_device:
            if req_device.startswith("cuda"):
                if torch is None or not torch.cuda.is_available():
                    raise RuntimeError(
                        f"Device '{req_device}' was explicitly requested for FASHN VTON, "
                        "but CUDA is not available on this machine. Never silently claims GPU inference on CPU."
                    )
                self._device = req_device
            elif req_device == "cpu":
                self._device = "cpu"
            else:
                raise ValueError(f"Unsupported device requested: '{req_device}'. Must be 'cpu' or 'cuda'.")
        else:
            # Auto-detection
            if torch is not None and torch.cuda.is_available():
                self._device = "cuda"
            else:
                self._device = "cpu"

        self._num_timesteps = max(10, min(100, int(num_timesteps)))
        logger.info(
            f"FashnTryOnProvider configured (device='{self._device}', "
            f"weights_dir='{self._weights_dir}', timesteps={self._num_timesteps})"
        )

    @property
    def provider_name(self) -> str:
        return "fashn"

    @property
    def device(self) -> str:
        return self._device

    @property
    def weights_dir(self) -> Path:
        return self._weights_dir

    @property
    def num_timesteps(self) -> int:
        return self._num_timesteps

    def is_available(self) -> tuple[bool, str]:
        """
        Validates whether a permitted genuine inference execution environment is available.
        Checks for:
        1. Configured authorized remote inference worker URL (FASHN_INFERENCE_URL or REMOTE_GPU_URL).
        2. Or local neural dependencies (torch, Pillow, fashn_vton) and weights (model.safetensors).

        Returns (available: bool, reason: str).
        """
        worker_url = os.getenv("FASHN_INFERENCE_URL") or os.getenv("REMOTE_GPU_URL")
        if worker_url and worker_url.strip():
            return True, f"Remote inference worker configured at {worker_url.strip()}"

        missing_deps = []
        if torch is None:
            missing_deps.append("torch")
        if Image is None:
            missing_deps.append("pillow")
        if TryOnPipeline is None:
            missing_deps.append("fashn-vton-1.5")

        if missing_deps:
            return False, "AI generation is temporarily unavailable because no inference worker is connected."

        model_file = self._weights_dir / "model.safetensors"
        if not model_file.exists():
            return False, "AI generation is temporarily unavailable because no inference worker is connected."

        return True, f"Local FASHN VTON v1.5 pipeline available on {self._device}."

    def _get_pipeline(self) -> Any:
        """
        Lazily loads and caches the genuine TryOnPipeline singleton.
        Reuses the pipeline across subsequent requests rather than reloading ~2.2 GB of weights.
        Thread-safe. Does NOT download weights automatically.
        """
        with self._pipeline_lock:
            if self._cached_pipeline is not None:
                return self._cached_pipeline

            # 1. Dependency verification
            missing_deps = []
            if torch is None:
                missing_deps.append("torch")
            if Image is None:
                missing_deps.append("Pillow")
            if TryOnPipeline is None:
                missing_deps.append("fashn-vton-1.5")

            if missing_deps:
                raise ImportError(
                    f"FASHN VTON v1.5 dependencies are missing ({', '.join(missing_deps)}). "
                    "Please install PyTorch, onnxruntime, and fashn-vton-1.5 before running inference."
                )

            # 2. Weights directory verification (never auto-downloads)
            if not self._weights_dir.exists() or not self._weights_dir.is_dir():
                raise FileNotFoundError(
                    f"FASHN VTON weights directory '{self._weights_dir}' does not exist. "
                    "Official model weights must be pre-downloaded manually. Auto-download is disabled."
                )

            model_file = self._weights_dir / "model.safetensors"
            if not model_file.exists():
                raise FileNotFoundError(
                    f"FASHN VTON model weights file '{model_file}' not found. "
                    "Please ensure official safetensors weights are placed in the weights directory."
                )

            logger.info(
                f"[FashnProvider] Loading genuine TryOnPipeline from '{self._weights_dir}' "
                f"onto device '{self._device}'..."
            )

            # 3. Pipeline instantiation
            try:
                # TryOnPipeline initializes with weights_dir and automatically targets device
                pipeline = TryOnPipeline(weights_dir=str(self._weights_dir))
                self._cached_pipeline = pipeline
                logger.info("[FashnProvider] TryOnPipeline loaded and cached successfully.")
                return self._cached_pipeline
            except Exception as exc:
                logger.error(f"[FashnProvider] Failed to load TryOnPipeline: {exc}", exc_info=True)
                raise RuntimeError(f"Failed to initialize genuine FASHN VTON pipeline: {exc}")

    def _sync_db_session(
        self,
        db: Optional[Any],
        session_id: str,
        status: str,
        progress: int,
        stage_message: str,
        result_image_url: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> None:
        """
        Synchronizes execution progress and state with the PostgreSQL TryOnSession record.
        """
        if db is None:
            return

        try:
            from app.models import TryOnSession
            session = db.get(TryOnSession, session_id)
            if session:
                session.status = status
                session.progress_percentage = progress
                session.stage_message = stage_message
                session.provider = self.provider_name
                session.result_image_url = result_image_url
                session.error_message = error_message
                session.updated_at = datetime.now(timezone.utc)
                db.commit()
                db.refresh(session)
        except Exception as exc:
            logger.warning(f"Failed to synchronize TryOnSession '{session_id}' in DB: {exc}")
            try:
                db.rollback()
            except Exception:
                pass

    async def _dispatch_remote_inference(
        self,
        worker_url: str,
        session_id: str,
        customer_photo_path: str,
        garment_image_url: str,
        category: str,
        db: Optional[Any] = None,
    ) -> TryOnExecutionResult:
        """
        Dispatches genuine try-on inference to an authorized remote GPU inference worker.
        Transfers customer portrait and garment reference, monitors remote progress,
        and streams back the generated image into private RESULTS_DIR.
        """
        import urllib.request
        import urllib.error

        logger.info(f"[FashnProvider] Dispatching remote inference for session '{session_id}' to {worker_url}...")
        start_time = datetime.now(timezone.utc)

        self._sync_db_session(
            db=db,
            session_id=session_id,
            status="processing",
            progress=25,
            stage_message=f"Dispatching inference to remote GPU worker ({worker_url})...",
        )

        try:
            resolved_customer = get_customer_photo_path(customer_photo_path)
            with open(resolved_customer, "rb") as f:
                photo_bytes = f.read()

            endpoint = worker_url.rstrip("/") + "/generate"
            boundary = f"----WebKitFormBoundary{uuid.uuid4().hex}"

            body_parts = [
                f"--{boundary}\r\nContent-Disposition: form-data; name=\"customer_photo\"; filename=\"photo.jpg\"\r\nContent-Type: image/jpeg\r\n\r\n".encode("utf-8"),
                photo_bytes,
                b"\r\n",
                f"--{boundary}\r\nContent-Disposition: form-data; name=\"garment_image_url\"\r\n\r\n{garment_image_url}\r\n".encode("utf-8"),
                f"--{boundary}\r\nContent-Disposition: form-data; name=\"category\"\r\n\r\n{category}\r\n".encode("utf-8"),
                f"--{boundary}\r\nContent-Disposition: form-data; name=\"session_id\"\r\n\r\n{session_id}\r\n".encode("utf-8"),
                f"--{boundary}--\r\n".encode("utf-8"),
            ]
            payload = b"".join(body_parts)

            req = urllib.request.Request(
                endpoint,
                data=payload,
                headers={
                    "Content-Type": f"multipart/form-data; boundary={boundary}",
                    "User-Agent": "VirtualFitAI-RemoteClient/1.0",
                },
                method="POST",
            )

            self._sync_db_session(
                db=db,
                session_id=session_id,
                status="processing",
                progress=60,
                stage_message="Remote GPU neural diffusion synthesis in progress...",
            )

            def _send_request():
                with urllib.request.urlopen(req, timeout=180) as resp:
                    return resp.read()

            resp_data = await asyncio.to_thread(_send_request)

            RESULTS_DIR.mkdir(parents=True, exist_ok=True)
            result_filename = f"res_{session_id}.jpg"
            result_file_path = RESULTS_DIR / result_filename
            with open(result_file_path, "wb") as f:
                f.write(resp_data)

            duration_seconds = (datetime.now(timezone.utc) - start_time).total_seconds()
            result_url = f"/api/tryon/{session_id}/result"
            completed_msg = f"Virtual try-on generated successfully via remote GPU worker ({worker_url})."

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
                    "device": "remote_gpu",
                    "worker_url": worker_url,
                    "category": category,
                    "duration_seconds": round(duration_seconds, 2),
                    "is_simulation": False,
                },
            )

        except Exception as exc:
            duration_seconds = (datetime.now(timezone.utc) - start_time).total_seconds()
            error_text = f"Remote GPU worker inference failed: {str(exc)}"
            logger.error(f"[FashnProvider] Remote inference error for session '{session_id}': {error_text}")

            self._sync_db_session(
                db=db,
                session_id=session_id,
                status="failed",
                progress=0,
                stage_message=error_text,
                error_message=error_text,
            )

            return TryOnExecutionResult(
                session_id=session_id,
                status="failed",
                progress_percentage=0,
                stage_message=error_text,
                provider=self.provider_name,
                result_image_url=None,
                error_message=error_text,
                metadata={
                    "device": "remote_gpu",
                    "worker_url": worker_url,
                    "error": error_text,
                    "is_simulation": False,
                    "duration_seconds": round(duration_seconds, 2),
                },
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
        Executes genuine FASHN VTON v1.5 virtual try-on inference.

        1. Validates worker availability or local model environment.
        2. Normalizes category ('tops', 'bottoms', 'one-pieces').
        3. If remote GPU worker is configured, dispatches asynchronously to worker.
        4. Otherwise executes local TryOnPipeline neural diffusion model.
        5. Extracts generated image and persists to private storage.
        6. Commits completed session state to PostgreSQL.
        """
        worker_url = os.getenv("FASHN_INFERENCE_URL") or os.getenv("REMOTE_GPU_URL")
        is_avail, avail_reason = self.is_available()

        if not is_avail:
            error_msg = "AI generation is temporarily unavailable because no inference worker is connected."
            stage_msg = f"AI generation failed: {error_msg}"
            self._sync_db_session(
                db=db,
                session_id=session_id,
                status="failed",
                progress=0,
                stage_message=stage_msg,
                error_message=error_msg,
            )
            return TryOnExecutionResult(
                session_id=session_id,
                status="failed",
                progress_percentage=0,
                stage_message=stage_msg,
                provider=self.provider_name,
                result_image_url=None,
                error_message=error_msg,
                metadata={"device": str(self._device), "is_simulation": False},
            )

        fashn_category = normalize_garment_category(category=category)

        # Route to remote GPU worker if configured
        if worker_url and worker_url.strip():
            return await self._dispatch_remote_inference(
                worker_url=worker_url.strip(),
                session_id=session_id,
                customer_photo_path=customer_photo_path,
                garment_image_url=garment_image_url,
                category=fashn_category,
                db=db,
            )

        logger.info(f"[FashnProvider] Starting genuine local AI try-on for session '{session_id}'...")
        start_time = datetime.now(timezone.utc)

        # Notify DB: Session is actively processing
        self._sync_db_session(
            db=db,
            session_id=session_id,
            status="processing",
            progress=15,
            stage_message="Loading and validating customer and garment images...",
        )

        try:
            logger.info(f"[FashnProvider] Normalized garment category: '{fashn_category}'")

            # 2. Resolve and convert input images
            person_img = _resolve_image_source(customer_photo_path)
            garment_img = _resolve_image_source(garment_image_url)

            logger.info(
                f"[FashnProvider] Images ready: person={person_img.size} ({person_img.mode}), "
                f"garment={garment_img.size} ({garment_img.mode})"
            )

            # 3. Retrieve cached pipeline
            self._sync_db_session(
                db=db,
                session_id=session_id,
                status="processing",
                progress=30,
                stage_message=f"Initializing FASHN VTON neural model on {self._device}...",
            )
            pipeline = self._get_pipeline()

            # 4. Execute neural diffusion inference
            self._sync_db_session(
                db=db,
                session_id=session_id,
                status="processing",
                progress=50,
                stage_message=f"Synthesizing virtual try-on ({self._num_timesteps} diffusion steps on {self._device})...",
            )

            # Perform actual pipeline inference offloaded to a worker thread so asyncio loop is not blocked
            # Reference: pipeline(person_image=..., garment_image=..., category=..., num_timesteps=...)
            output = await asyncio.to_thread(
                pipeline,
                person_image=person_img,
                garment_image=garment_img,
                category=fashn_category,
                num_timesteps=self._num_timesteps,
            )

            # 5. Extract genuine output PIL Image
            if hasattr(output, "images") and len(output.images) > 0:
                result_img = output.images[0]
            elif Image is not None and isinstance(output, Image.Image):
                result_img = output
            elif isinstance(output, (list, tuple)) and len(output) > 0:
                result_img = output[0]
            else:
                raise RuntimeError(
                    f"Unexpected output type from FASHN VTON TryOnPipeline: {type(output)}"
                )

            # 6. Save genuine generated result image into private storage
            RESULTS_DIR.mkdir(parents=True, exist_ok=True)
            result_filename = f"res_{session_id}.jpg"
            result_file_path = RESULTS_DIR / result_filename
            result_img.save(result_file_path, format="JPEG", quality=95)

            result_url = f"/api/tryon/{session_id}/result"
            duration_seconds = (datetime.now(timezone.utc) - start_time).total_seconds()

            logger.info(
                f"[FashnProvider] Inference completed in {duration_seconds:.2f}s! "
                f"Saved result: '{result_filename}' ({result_img.size[0]}x{result_img.size[1]})"
            )

            # 7. Update PostgreSQL state to completed
            completed_message = (
                f"Virtual try-on generated successfully using FASHN VTON v1.5 on {self._device}."
            )
            self._sync_db_session(
                db=db,
                session_id=session_id,
                status="completed",
                progress=100,
                stage_message=completed_message,
                result_image_url=result_url,
            )

            return TryOnExecutionResult(
                session_id=session_id,
                status="completed",
                progress_percentage=100,
                stage_message=completed_message,
                provider=self.provider_name,
                result_image_url=result_url,
                error_message=None,
                metadata={
                    "device": str(self._device),
                    "category": fashn_category,
                    "timesteps": self._num_timesteps,
                    "image_dimensions": [result_img.size[0], result_img.size[1]],
                    "duration_seconds": round(duration_seconds, 2),
                    "result_filename": result_filename,
                    "is_simulation": False,
                },
            )

        except Exception as exc:
            duration_seconds = (datetime.now(timezone.utc) - start_time).total_seconds()
            error_text = str(exc)
            logger.error(
                f"[FashnProvider] Try-on inference failed for session '{session_id}': {error_text}",
                exc_info=True,
            )

            # Specific error diagnosis
            if "out of memory" in error_text.lower():
                user_friendly_error = (
                    f"Hardware memory limit exceeded on {self._device} during neural diffusion. "
                    "Reduce image dimensions or diffusion timesteps."
                )
            else:
                user_friendly_error = f"AI inference failed: {error_text}"

            self._sync_db_session(
                db=db,
                session_id=session_id,
                status="failed",
                progress=0,
                stage_message=user_friendly_error,
                error_message=error_text,
            )

            return TryOnExecutionResult(
                session_id=session_id,
                status="failed",
                progress_percentage=0,
                stage_message=user_friendly_error,
                provider=self.provider_name,
                result_image_url=None,
                error_message=error_text,
                metadata={
                    "device": str(self._device),
                    "error": error_text,
                    "is_simulation": False,
                    "duration_seconds": round(duration_seconds, 2),
                },
            )

    async def check_status(
        self,
        session_id: str,
        db: Optional[Any] = None,
    ) -> TryOnExecutionResult:
        """
        Queries status and progress for an active or completed FASHN VTON session.
        """
        if db is not None:
            try:
                from app.models import TryOnSession
                session = db.get(TryOnSession, session_id)
                if session:
                    return TryOnExecutionResult(
                        session_id=session.id,
                        status=session.status,
                        progress_percentage=session.progress_percentage,
                        stage_message=session.stage_message or "Processing virtual try-on",
                        provider=session.provider or self.provider_name,
                        result_image_url=session.result_image_url,
                        error_message=session.error_message,
                        metadata={"device": str(self._device), "is_simulation": False},
                    )
            except Exception as exc:
                logger.warning(f"Error querying TryOnSession from DB: {exc}")

        return TryOnExecutionResult(
            session_id=session_id,
            status="pending",
            progress_percentage=0,
            stage_message="Virtual try-on task queued for processing.",
            provider=self.provider_name,
            result_image_url=None,
            metadata={"device": str(self._device), "is_simulation": False},
        )
