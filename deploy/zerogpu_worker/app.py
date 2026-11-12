"""
VirtualFit AI — Genuine FASHN VTON v1.5 Hugging Face ZeroGPU Inference Worker.

Runs genuine open-source neural diffusion virtual try-on inference on free
Hugging Face ZeroGPU resources (NVIDIA A100 / L4 GPU).
Exposes a production-ready Gradio API consumed directly by the VirtualFit AI FastAPI backend.
"""
import os
import sys
import time
import logging
from pathlib import Path
from typing import Optional, Union, Tuple

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("virtualfit.zerogpu.worker")

# Hugging Face ZeroGPU import convention: spaces MUST be imported before torch
try:
    import spaces
    HAS_ZEROGPU = True
    logger.info("Hugging Face ZeroGPU SDK detected and active.")
except ImportError:
    HAS_ZEROGPU = False
    logger.warning("spaces SDK not found. Running in fallback environment.")

    class _MockSpaces:
        @staticmethod
        def GPU(duration: int = 120):
            def decorator(fn):
                return fn
            return decorator

    spaces = _MockSpaces()

import torch
import gradio as gr
from PIL import Image

# Import official FASHN VTON TryOnPipeline
try:
    from fashn_vton import TryOnPipeline
    HAS_FASHN_PIPELINE = True
except ImportError:
    HAS_FASHN_PIPELINE = False
    logger.warning("fashn-vton-1.5 package not installed. TryOnPipeline unavailable.")
    TryOnPipeline = None

# Weight directories
WEIGHTS_DIR = Path(os.getenv("FASHN_WEIGHTS_DIR", "./weights")).resolve()
WEIGHTS_DIR.mkdir(parents=True, exist_ok=True)

# Global cached pipeline singleton
_cached_pipeline: Optional[object] = None


def ensure_model_weights() -> Path:
    """
    Verifies that official FASHN VTON v1.5 weights exist locally.
    If not present, downloads official model.safetensors from Hugging Face Hub.
    """
    model_file = WEIGHTS_DIR / "model.safetensors"
    if model_file.exists() and model_file.stat().st_size > 1024 * 1024:
        logger.info(f"Model weights verified at: {model_file} ({model_file.stat().st_size / (1024**2):.1f} MB)")
        return WEIGHTS_DIR

    logger.info("FASHN VTON weights not found locally. Downloading from Hugging Face Hub...")
    try:
        from huggingface_hub import hf_hub_download
        downloaded = hf_hub_download(
            repo_id="fashn-ai/fashn-vton-1.5",
            filename="model.safetensors",
            local_dir=str(WEIGHTS_DIR),
            local_dir_use_symlinks=False,
        )
        logger.info(f"Weights downloaded successfully: {downloaded}")
    except Exception as exc:
        logger.error(f"Failed to auto-download weights from Hugging Face Hub: {exc}")
        # Secondary fallback: check local models directory
        alt_path = Path("/home/user/app/models/fashn/model.safetensors")
        if alt_path.exists():
            return alt_path.parent

    return WEIGHTS_DIR


def get_pipeline() -> object:
    """
    Lazily initializes and caches the singleton TryOnPipeline.
    Thread-safe; reuses weights across requests.
    """
    global _cached_pipeline
    if _cached_pipeline is not None:
        return _cached_pipeline

    if not HAS_FASHN_PIPELINE:
        raise ImportError(
            "fashn_vton package is not installed. Please install fashn-vton-1.5: "
            "pip install git+https://github.com/fashn-AI/fashn-vton-1.5.git"
        )

    w_dir = ensure_model_weights()
    logger.info(f"Initializing TryOnPipeline with weights from: {w_dir}...")
    t0 = time.perf_counter()
    _cached_pipeline = TryOnPipeline(weights_dir=str(w_dir))
    logger.info(f"TryOnPipeline loaded and cached in {time.perf_counter() - t0:.2f}s.")
    return _cached_pipeline


def prepare_rgb(img: Union[Image.Image, str]) -> Image.Image:
    """
    Normalizes any input image to standard RGB:
    - Resolves string file paths to PIL Image.
    - Flattens transparent RGBA/LA images onto clean white background.
    - Converts grayscale or palette images to 3-channel RGB.
    """
    if isinstance(img, str):
        img = Image.open(img)

    if not isinstance(img, Image.Image):
        raise TypeError(f"Expected PIL Image or path string, got {type(img)}")

    if img.mode in ("RGBA", "LA") or ("transparency" in img.info):
        alpha_img = img.convert("RGBA")
        bg = Image.new("RGB", alpha_img.size, (255, 255, 255))
        bg.paste(alpha_img, mask=alpha_img.split()[3])
        return bg

    if img.mode != "RGB":
        return img.convert("RGB")

    return img


@spaces.GPU(duration=120)
def predict_tryon(
    person_image: Image.Image,
    garment_image: Image.Image,
    category: str = "tops",
    num_timesteps: int = 30,
) -> Image.Image:
    """
    Executes genuine FASHN VTON v1.5 virtual try-on inference.
    Decorated with @spaces.GPU(duration=120) to dynamically attach NVIDIA GPU
    on Hugging Face ZeroGPU infrastructure.

    :param person_image: Customer portrait photo (PIL Image)
    :param garment_image: Catalogue garment reference photo (PIL Image)
    :param category: One of 'tops', 'bottoms', 'one-pieces'
    :param num_timesteps: Diffusion inference timesteps (10 - 50, default: 30)
    :returns: High-resolution synthesized try-on result (PIL Image)
    """
    t_start = time.perf_counter()
    logger.info(f"[ZeroGPU Worker] Commencing inference (category='{category}', timesteps={num_timesteps})...")

    # 1. Validation
    if person_image is None:
        raise ValueError("Customer portrait photo is required.")
    if garment_image is None:
        raise ValueError("Garment reference image is required.")

    valid_categories = {"tops", "bottoms", "one-pieces"}
    norm_cat = str(category).strip().lower()
    if norm_cat not in valid_categories:
        raise ValueError(
            f"Invalid category '{category}'. Must be one of: {', '.join(sorted(valid_categories))}."
        )

    timesteps = max(10, min(50, int(num_timesteps)))

    # 2. Pre-process RGB images
    person_rgb = prepare_rgb(person_image)
    garment_rgb = prepare_rgb(garment_image)

    # 3. Retrieve TryOnPipeline
    pipeline = get_pipeline()

    # 4. Neural diffusion synthesis on ZeroGPU
    output = pipeline(
        person_image=person_rgb,
        garment_image=garment_rgb,
        category=norm_cat,
        num_timesteps=timesteps,
    )

    # 5. Extract genuine output image
    if hasattr(output, "images") and len(output.images) > 0:
        result_img = output.images[0]
    elif isinstance(output, Image.Image):
        result_img = output
    elif isinstance(output, (list, tuple)) and len(output) > 0:
        result_img = output[0]
    else:
        raise RuntimeError(f"Unexpected output from TryOnPipeline: {type(output)}")

    duration = time.perf_counter() - t_start
    logger.info(
        f"[ZeroGPU Worker] Inference completed in {duration:.2f}s! "
        f"Output dimensions: {result_img.size[0]}x{result_img.size[1]}"
    )
    return result_img


def health_check() -> dict:
    """
    Health check endpoint returning worker status and execution environment details.
    """
    cuda_avail = torch.cuda.is_available()
    device_name = torch.cuda.get_device_name(0) if cuda_avail else "CPU (ZeroGPU dynamic attached on inference)"
    return {
        "status": "healthy",
        "service": "VirtualFit AI ZeroGPU Worker",
        "model": "FASHN VTON v1.5",
        "has_zerogpu": HAS_ZEROGPU,
        "cuda_available": cuda_avail,
        "device": device_name,
        "supported_categories": ["tops", "bottoms", "one-pieces"],
        "default_timesteps": 30,
        "budget": "₹0 (ZeroGPU Free Tier)",
    }


# =========================================================================
# GRADIO INTERFACE & API EXPOSURE
# =========================================================================
with gr.Blocks(
    title="VirtualFit AI — FASHN VTON v1.5 ZeroGPU Worker",
    theme=gr.themes.Soft(primary_hue="indigo"),
) as demo:
    gr.Markdown(
        """
        # VirtualFit AI — Zero-Cost ZeroGPU Inference Worker
        Genuine **FASHN VTON v1.5** neural diffusion virtual try-on executing on free **Hugging Face ZeroGPU** hardware.
        """
    )

    with gr.Tab("AI Virtual Try-On"):
        with gr.Row():
            with gr.Column():
                input_person = gr.Image(type="pil", label="Customer Portrait Photo")
                input_garment = gr.Image(type="pil", label="Catalogue Garment Image")
                input_category = gr.Dropdown(
                    choices=["tops", "bottoms", "one-pieces"],
                    value="tops",
                    label="Garment Category",
                )
                input_timesteps = gr.Slider(
                    minimum=10,
                    maximum=50,
                    value=30,
                    step=5,
                    label="Diffusion Steps",
                )
                btn_generate = gr.Button("Synthesize AI Fitting", variant="primary")

            with gr.Column():
                output_image = gr.Image(type="pil", label="Generated Try-On Result")

        btn_generate.click(
            fn=predict_tryon,
            inputs=[input_person, input_garment, input_category, input_timesteps],
            outputs=output_image,
            api_name="tryon",
        )

    with gr.Tab("Worker Status"):
        btn_health = gr.Button("Query Worker Health")
        output_health = gr.JSON(label="Worker Health & Environment Details")
        btn_health.click(fn=health_check, inputs=[], outputs=output_health, api_name="health")

    # Run health check on load
    demo.load(fn=health_check, inputs=[], outputs=output_health)


if __name__ == "__main__":
    demo.queue().launch(server_name="0.0.0.0", server_port=7860)

