"""
VirtualFit AI — FASHN VTON v1.5 Free GPU Standalone Benchmark Script.
Can be run on Google Colab or Kaggle (Terminal or Python script mode).
Requirements: Free T4 GPU, Python 3.10+, PyTorch with CUDA.
"""
import os
import sys
import time
import gc

def main():
    print("=" * 65)
    print("VIRTUALFIT AI: FASHN VTON v1.5 FREE GPU BENCHMARK")
    print("=" * 65)

    # 1. Hardware Pre-flight Check
    try:
        import torch
    except ImportError:
        print("[ERROR] PyTorch is not installed. Please install torch with CUDA support.")
        sys.exit(1)

    if not torch.cuda.is_available():
        print("\n[CRITICAL HALT] No NVIDIA CUDA GPU detected!")
        print("Please enable free T4 GPU in Google Colab (Runtime -> Change runtime type -> T4 GPU).")
        print("Stopping execution to prevent unaccelerated CPU overload.\n")
        sys.exit(1)

    device_name = torch.cuda.get_device_name(0)
    total_vram_gb = torch.cuda.get_device_properties(0).total_memory / (1024 ** 3)
    print(f"[PRE-FLIGHT] GPU Detected      : {device_name}")
    print(f"[PRE-FLIGHT] Total VRAM        : {total_vram_gb:.2f} GB")
    print(f"[PRE-FLIGHT] PyTorch Version   : {torch.__version__}")
    print("-" * 65)

    # 2. Clone repo if needed
    if not os.path.exists("fashn-vton-1.5"):
        print("[STEP 2] Cloning official repository...")
        os.system("git clone https://github.com/fashn-AI/fashn-vton-1.5.git")

    repo_dir = os.path.abspath("fashn-vton-1.5")
    sys.path.insert(0, repo_dir)
    os.chdir(repo_dir)

    # 3. Licence Verification
    if os.path.exists("LICENSE"):
        with open("LICENSE", "r") as f:
            lic = f.read()
        if "Apache License" in lic and "Version 2.0" in lic:
            print("[LICENCE] Verified Apache-2.0. Commercial use permitted.")
        else:
            print(f"[LICENCE WARNING] Unexpected licence text:\n{lic[:150]}")
    else:
        print("[LICENCE WARNING] LICENSE file not found in repo root.")

    # 4. Install dependencies
    print("[STEP 3] Verifying and installing dependencies...")
    os.system("pip install -q -e .")

    from PIL import Image
    from fashn_vton import TryOnPipeline

    # 5. Download Weights
    weights_dir = os.path.abspath("./weights")
    if not os.path.exists(os.path.join(weights_dir, "model.safetensors")):
        print("[STEP 4] Downloading official model weights (~2.2 GB)...")
        t0 = time.perf_counter()
        os.system(f"python scripts/download_weights.py --weights-dir {weights_dir}")
        print(f"[STEP 4] Weights downloaded in {time.perf_counter() - t0:.2f}s")
    else:
        print("[STEP 4] Model weights already exist in weights directory.")

    # 6. Benchmark Inference on Sample Images
    person_path = os.path.join(repo_dir, "examples/data/model.webp")
    garment_path = os.path.join(repo_dir, "examples/data/garment.webp")

    if not os.path.exists(person_path) or not os.path.exists(garment_path):
        print(f"[ERROR] Sample images not found: {person_path}, {garment_path}")
        sys.exit(1)

    person_img = Image.open(person_path).convert("RGB")
    garment_img = Image.open(garment_path).convert("RGB")
    print(f"[INPUT] Person Image : {person_path} ({person_img.size})")
    print(f"[INPUT] Garment Image: {garment_path} ({garment_img.size})")

    gc.collect()
    torch.cuda.empty_cache()
    torch.cuda.reset_peak_memory_stats()

    print("\n[STEP 5] Initializing TryOnPipeline...")
    t_load = time.perf_counter()
    pipeline = TryOnPipeline(weights_dir=weights_dir)
    print(f"[TIMING] Pipeline loaded in: {time.perf_counter() - t_load:.2f}s")

    print("[STEP 5] Running genuine AI virtual try-on inference (30 timesteps)...")
    t_infer = time.perf_counter()
    result = pipeline(
        person_image=person_img,
        garment_image=garment_img,
        category="tops",
        num_timesteps=30,
    )
    infer_duration = time.perf_counter() - t_infer

    peak_vram_mb = torch.cuda.max_memory_allocated() / (1024 ** 2)
    output_path = os.path.abspath("fashn_vton_benchmark_output.png")
    result.save(output_path)

    print("\n" + "=" * 65)
    print("BENCHMARK EXECUTION SUMMARY:")
    print("=" * 65)
    print(f"Device Used          : {device_name}")
    print(f"Inference Time       : {infer_duration:.2f} seconds")
    print(f"Peak VRAM Allocated  : {peak_vram_mb:.1f} MB ({peak_vram_mb / 1024:.2f} GB)")
    print(f"Output Image Res     : {result.size[0]} x {result.size[1]} px")
    print(f"Output File Saved To : {output_path}")
    print(f"Status               : 100% GENUINE AI INFERENCE COMPLETED")
    print("=" * 65)

if __name__ == "__main__":
    main()

