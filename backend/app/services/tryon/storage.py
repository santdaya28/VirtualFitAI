"""
Private Temporary Storage Service for VirtualFit AI Virtual Try-On.

Security Requirements:
1. Customer photos and temporary results are kept strictly isolated from public product images.
2. Under no circumstance may this storage directory be mounted via FastAPI StaticFiles.
3. Filenames are generated server-side using cryptographically secure UUIDs.
4. Client filenames are never used as filesystem paths to prevent path traversal attacks.
5. Automated or callable cleanup function purges files older than 1 hour (3600 seconds).
"""
import os
import time
import uuid
import logging
from pathlib import Path
from typing import Optional, Dict, Any

logger = logging.getLogger("virtualfit.tryon.storage")

# Root backend directory
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent

# Private temporary storage root: outside the public static 'uploads/' directory
STORAGE_ROOT = BASE_DIR / "storage" / "temp_tryon"
CUSTOMER_PHOTOS_DIR = STORAGE_ROOT / "customer_photos"
RESULTS_DIR = STORAGE_ROOT / "results"

# Ensure private directories exist with secure permissions
CUSTOMER_PHOTOS_DIR.mkdir(parents=True, exist_ok=True)
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

# Whitelisted image extensions for customer photos
ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
DEFAULT_EXTENSION = ".jpg"
DEFAULT_EXPIRATION_SECONDS = 3600  # 1 hour


def _sanitize_extension(ext: Optional[str], original_filename: Optional[str] = None) -> str:
    """
    Extracts and validates extension against allowed whitelist.
    Defaults to .jpg if missing or invalid.
    """
    candidate = ext
    if not candidate and original_filename:
        candidate = Path(original_filename).suffix

    if candidate:
        clean = candidate.lower().strip()
        if clean in ALLOWED_IMAGE_EXTENSIONS:
            return clean

    return DEFAULT_EXTENSION


def _resolve_and_verify(base_dir: Path, filename: str) -> Path:
    """
    Resolves filename inside base_dir and rigorously verifies that
    it does not escape base_dir via directory traversal (e.g. '../').
    Raises ValueError on traversal attempt, or FileNotFoundError if file does not exist.
    """
    if not filename or not isinstance(filename, str):
        raise ValueError("Filename must be a non-empty string.")

    # Extract base name to strip leading directory characters
    clean_name = os.path.basename(filename.strip())
    if not clean_name or clean_name in (".", ".."):
        raise ValueError("Invalid filename specified.")

    base_resolved = base_dir.resolve()
    target_resolved = (base_dir / clean_name).resolve()

    # Strict boundary check: target must be directly inside base_resolved
    if target_resolved.parent != base_resolved:
        logger.warning(f"Path traversal attempt blocked: '{filename}'")
        raise ValueError("Security violation: Path traversal detected.")

    return target_resolved


def save_customer_photo(
    file_bytes: bytes,
    original_filename: Optional[str] = None,
    extension: Optional[str] = None,
) -> str:
    """
    Saves a customer uploaded photo into private temporary storage.
    Generates an unpredictable server-side filename (UUID).
    Returns the generated internal filename (not a public URL).
    """
    if not file_bytes:
        raise ValueError("Customer photo file bytes cannot be empty.")

    safe_ext = _sanitize_extension(extension, original_filename)
    # Generate unpredictable UUID-based filename
    internal_filename = f"cust_{uuid.uuid4().hex}{safe_ext}"
    target_path = CUSTOMER_PHOTOS_DIR / internal_filename

    with open(target_path, "wb") as f:
        f.write(file_bytes)

    logger.info(f"Saved private customer photo: {internal_filename} ({len(file_bytes)} bytes)")
    return internal_filename


def get_customer_photo_path(filename: str) -> Path:
    """
    Retrieves the internal Path of a stored customer photo.
    Enforces path traversal checks and verifies file existence.
    """
    target_path = _resolve_and_verify(CUSTOMER_PHOTOS_DIR, filename)
    if not target_path.exists() or not target_path.is_file():
        raise FileNotFoundError(f"Customer photo '{filename}' not found or already purged.")
    return target_path


def get_customer_photo_bytes(filename: str) -> bytes:
    """
    Reads and returns the raw bytes of a stored customer photo internally.
    """
    target_path = get_customer_photo_path(filename)
    with open(target_path, "rb") as f:
        return f.read()


def delete_customer_photo(filename: str) -> bool:
    """
    Explicitly deletes a customer photo from private temporary storage.
    Returns True if successfully deleted, False if file did not exist.
    """
    try:
        target_path = _resolve_and_verify(CUSTOMER_PHOTOS_DIR, filename)
        if target_path.exists() and target_path.is_file():
            target_path.unlink()
            logger.info(f"Purged private customer photo: {filename}")
            return True
        return False
    except (ValueError, FileNotFoundError):
        return False


def save_result_file(
    file_bytes: bytes,
    extension: str = ".txt",
) -> str:
    """
    Saves temporary execution result data or logs into private results storage.
    Returns the internal filename.
    """
    if not file_bytes:
        raise ValueError("Result data bytes cannot be empty.")

    safe_ext = extension.strip().lower() if extension.startswith(".") else f".{extension.strip().lower()}"
    internal_filename = f"res_{uuid.uuid4().hex}{safe_ext}"
    target_path = RESULTS_DIR / internal_filename

    with open(target_path, "wb") as f:
        f.write(file_bytes)

    logger.info(f"Saved private result file: {internal_filename}")
    return internal_filename


def get_result_path(filename: str) -> Path:
    """
    Retrieves the internal Path of a temporary result file.
    Enforces path traversal protection.
    """
    target_path = _resolve_and_verify(RESULTS_DIR, filename)
    if not target_path.exists() or not target_path.is_file():
        raise FileNotFoundError(f"Result file '{filename}' not found.")
    return target_path


def delete_result_file(filename: str) -> bool:
    """
    Deletes a temporary result file from storage.
    """
    try:
        target_path = _resolve_and_verify(RESULTS_DIR, filename)
        if target_path.exists() and target_path.is_file():
            target_path.unlink()
            logger.info(f"Purged private result file: {filename}")
            return True
        return False
    except (ValueError, FileNotFoundError):
        return False


def cleanup_expired_files(max_age_seconds: int = DEFAULT_EXPIRATION_SECONDS) -> Dict[str, Any]:
    """
    Purges temporary files from customer_photos/ and results/ older than max_age_seconds (default: 3600s / 1hr).
    DOES NOT touch the public product catalog 'uploads/' directory.
    Returns a summary of purged files.
    """
    now = time.time()
    cutoff = now - max_age_seconds

    customer_deleted = 0
    results_deleted = 0

    # Scan and clean customer_photos
    for entry in CUSTOMER_PHOTOS_DIR.iterdir():
        if entry.is_file():
            try:
                mtime = entry.stat().st_mtime
                if mtime < cutoff:
                    entry.unlink()
                    customer_deleted += 1
            except Exception as exc:
                logger.warning(f"Error purging expired customer photo {entry.name}: {exc}")

    # Scan and clean results
    for entry in RESULTS_DIR.iterdir():
        if entry.is_file():
            try:
                mtime = entry.stat().st_mtime
                if mtime < cutoff:
                    entry.unlink()
                    results_deleted += 1
            except Exception as exc:
                logger.warning(f"Error purging expired result file {entry.name}: {exc}")

    total_deleted = customer_deleted + results_deleted
    if total_deleted > 0:
        logger.info(
            f"Temporary storage cleanup: purged {customer_deleted} customer photos, "
            f"{results_deleted} results (total: {total_deleted})"
        )

    return {
        "customer_photos_purged": customer_deleted,
        "results_purged": results_deleted,
        "total_purged": total_deleted,
        "cutoff_seconds": max_age_seconds,
    }

