"""
Mock Virtual Try-On Provider for VirtualFit AI.

Simulates an asynchronous AI try-on pipeline with multi-stage progress updates (25%, 50%, 75%, 100%).
Does NOT call any external AI API.
Does NOT generate, manipulate, or return an image that could be mistaken for a genuine AI try-on result.
Does NOT claim that the customer is actually wearing the selected garment.
Explicitly clarifies that no AI-generated fitting image was produced.
"""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any

from app.services.tryon.base import BaseTryOnProvider, TryOnExecutionResult

logger = logging.getLogger("virtualfit.tryon.mock")

# In-memory status cache for tracking sessions without active DB connection
_MOCK_STATUS_CACHE: Dict[str, TryOnExecutionResult] = {}

SIMULATION_COMPLETED_NOTICE = (
    "Simulation completed. Note: Mock simulation mode active — "
    "no genuine AI-generated fitting image was produced."
)


class MockTryOnProvider(BaseTryOnProvider):
    """
    Simulated Virtual Try-On engine for testing, development, and workflow validation.
    Advances through 4 discrete stages (25%, 50%, 75%, 100%) asynchronously.
    """

    def __init__(self, stage_delay: float = 0.5):
        """
        :param stage_delay: Delay in seconds between each processing stage (default: 0.5s).
        """
        self._stage_delay = max(0.0, stage_delay)

    @property
    def provider_name(self) -> str:
        return "mock"

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
        Safely commits progress updates to the database TryOnSession if a DB session is provided.
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

    async def process_tryon(
        self,
        session_id: str,
        customer_photo_path: str,
        garment_image_url: str,
        category: Optional[str] = None,
        db: Optional[Any] = None,
    ) -> TryOnExecutionResult:
        """
        Executes simulated 4-stage try-on pipeline with async delays.
        Updates progress to 25%, 50%, 75%, and 100%.
        """
        logger.info(f"[MockProvider] Starting try-on simulation for session: {session_id}")

        stages = [
            (25, "Analyzing garment silhouette and key landmark points..."),
            (50, "Synthesizing body pose transformation and alignment..."),
            (75, "Rendering fabric texture blending and lighting adjustments..."),
            (100, SIMULATION_COMPLETED_NOTICE),
        ]

        try:
            for progress, message in stages:
                if self._stage_delay > 0:
                    await asyncio.sleep(self._stage_delay)

                is_complete = (progress == 100)
                current_status = "completed" if is_complete else "processing"

                result = TryOnExecutionResult(
                    session_id=session_id,
                    status=current_status,
                    progress_percentage=progress,
                    stage_message=message,
                    provider=self.provider_name,
                    result_image_url=None,  # Explicitly None: never returns fake fitting images
                    error_message=None,
                    metadata={
                        "is_simulation": True,
                        "notice": "Mock simulation mode. No AI-generated fitting image was produced.",
                        "category": category,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    },
                )

                # Update in-memory cache
                _MOCK_STATUS_CACHE[session_id] = result

                # Update PostgreSQL if DB session available
                self._sync_db_session(
                    db=db,
                    session_id=session_id,
                    status=current_status,
                    progress=progress,
                    stage_message=message,
                    result_image_url=None,
                )

                logger.debug(f"[MockProvider] Session {session_id} progress: {progress}% - {message}")

            logger.info(f"[MockProvider] Simulation successfully completed for session: {session_id}")
            return _MOCK_STATUS_CACHE[session_id]

        except Exception as exc:
            logger.error(f"[MockProvider] Simulation error for session {session_id}: {exc}")
            failed_result = TryOnExecutionResult(
                session_id=session_id,
                status="failed",
                progress_percentage=0,
                stage_message="Try-on simulation failed due to internal error.",
                provider=self.provider_name,
                result_image_url=None,
                error_message=str(exc),
                metadata={"is_simulation": True, "error": str(exc)},
            )
            _MOCK_STATUS_CACHE[session_id] = failed_result
            self._sync_db_session(
                db=db,
                session_id=session_id,
                status="failed",
                progress=0,
                stage_message=failed_result.stage_message,
                error_message=str(exc),
            )
            return failed_result

    async def check_status(
        self,
        session_id: str,
        db: Optional[Any] = None,
    ) -> TryOnExecutionResult:
        """
        Retrieves current progress and status for the mock session.
        Checks database first, falls back to in-memory status cache.
        """
        # 1. Attempt lookup in DB if db session provided
        if db is not None:
            try:
                from app.models import TryOnSession
                session = db.get(TryOnSession, session_id)
                if session:
                    return TryOnExecutionResult(
                        session_id=session.id,
                        status=session.status,
                        progress_percentage=session.progress_percentage,
                        stage_message=session.stage_message or "Processing virtual try-on simulation",
                        provider=session.provider or self.provider_name,
                        result_image_url=session.result_image_url,
                        error_message=session.error_message,
                        metadata={
                            "is_simulation": True,
                            "notice": "Mock simulation mode.",
                        },
                    )
            except Exception as exc:
                logger.warning(f"Error querying TryOnSession from DB: {exc}")

        # 2. Check in-memory cache
        if session_id in _MOCK_STATUS_CACHE:
            return _MOCK_STATUS_CACHE[session_id]

        # 3. Default state if session was not found
        return TryOnExecutionResult(
            session_id=session_id,
            status="pending",
            progress_percentage=0,
            stage_message="Virtual try-on task queued for processing.",
            provider=self.provider_name,
            result_image_url=None,
            metadata={"is_simulation": True},
        )

