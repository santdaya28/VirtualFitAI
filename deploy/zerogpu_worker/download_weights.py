"""
Helper script to download official FASHN VTON v1.5 weights to the worker weights directory.
"""
import os
import sys
from pathlib import Path

def main():
    target_dir = Path(os.getenv("FASHN_WEIGHTS_DIR", "./weights")).resolve()
    target_dir.mkdir(parents=True, exist_ok=True)
    target_file = target_dir / "model.safetensors"

    if target_file.exists():
        print(f"Weights already present at: {target_file}")
        return

    print(f"Downloading FASHN VTON v1.5 weights into {target_dir}...")
    try:
        from huggingface_hub import hf_hub_download
        downloaded = hf_hub_download(
            repo_id="fashn-ai/fashn-vton-1.5",
            filename="model.safetensors",
            local_dir=str(target_dir),
            local_dir_use_symlinks=False,
        )
        print(f"Successfully downloaded: {downloaded}")
    except Exception as exc:
        print(f"Failed to download from huggingface_hub: {exc}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()

