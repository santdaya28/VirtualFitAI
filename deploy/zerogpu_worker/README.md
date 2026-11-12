---
title: VirtualFit AI — FASHN VTON v1.5 ZeroGPU Worker
emoji: 👗
colorFrom: indigo
colorTo: purple
sdk: gradio
sdk_version: 5.6.0
app_file: app.py
pinned: false
license: apache-2.0
short_description: Free ZeroGPU inference worker for VirtualFit AI Virtual Try-On
---

# VirtualFit AI — Hugging Face ZeroGPU Inference Worker

This repository contains the standalone, zero-cost GPU inference worker for **VirtualFit AI**.
It runs the genuine **FASHN VTON v1.5** neural diffusion model on free **Hugging Face ZeroGPU** (NVIDIA A100 / L4 GPU) resources with **₹0 budget**.

---

## 1. ZeroGPU Architecture Overview

Hugging Face ZeroGPU provides free, dynamic GPU acceleration using the `spaces.GPU` context manager.
- **Dynamic Allocation**: GPUs (NVIDIA A100-SXM4-80GB or L4) are dynamically attached during the execution of `@spaces.GPU(duration=120)`.
- **Zero Idle Cost**: When inference finishes, the GPU is released to the community pool, preventing idle GPU billing.
- **Queue Management**: Built-in Gradio Queue manages concurrent inference requests without crashing.

---

## 2. Deployment Instructions (Zero-Cost Setup)

### Step 1: Create a Free Hugging Face Space
1. Log in to your free [Hugging Face](https://huggingface.co/) account.
2. Click **New Space** (`https://huggingface.co/new-space`).
3. Choose:
   - **Space Name**: `virtualfit-tryon-worker`
   - **License**: `Apache-2.0`
   - **SDK**: `Gradio`
   - **Space Hardware**: **ZeroGPU (Free)**
   - **Visibility**: Public (recommended for free community use) or Private.

### Step 2: Push Worker Files to Space
Clone your new Space repository and copy the files from `deploy/zerogpu_worker/`:
```bash
git clone https://huggingface.co/spaces/<your-username>/virtualfit-tryon-worker
cd virtualfit-tryon-worker

# Copy worker files:
cp -r /path/to/VirtualFitAI/deploy/zerogpu_worker/* .

git add .
git commit -m "Deploy VirtualFit AI FASHN VTON v1.5 ZeroGPU worker"
git push
```

### Step 3: Connect VirtualFit AI Backend
In your local `backend/.env` file:
```env
TRYON_PROVIDER=zerogpu
ZEROGPU_API_URL=https://<your-username>-virtualfit-tryon-worker.hf.space
# If the Space is private, also configure your free Hugging Face token:
HF_TOKEN=hf_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

---

## 3. Worker API Endpoints

### 1. Health Check (`api_name="health"`)
- **Method**: GET / POST
- **Response**:
  ```json
  {
    "status": "healthy",
    "service": "VirtualFit-ZeroGPU",
    "model": "FASHN VTON v1.5",
    "device": "ZeroGPU (CUDA)"
  }
  ```

### 2. Try-On Inference (`api_name="tryon"`)
- **Inputs**:
  - `person_image`: Image (JPEG/PNG/WebP)
  - `garment_image`: Image (JPEG/PNG/WebP)
  - `category`: Dropdown (`"tops"`, `"bottoms"`, `"one-pieces"`)
  - `num_timesteps`: Slider (default: `30`)
- **Output**:
  - `result_image`: Image (JPEG/PNG generated try-on result)

