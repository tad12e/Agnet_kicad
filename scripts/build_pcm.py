#!/usr/bin/env python3
"""Build script for KiCad Plugin and Content Manager (PCM) package."""

import os
import shutil
import zipfile
import hashlib
import json

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DIST_DIR = os.path.join(REPO_ROOT, "dist")
PLUGIN_SRC = os.path.join(REPO_ROOT, "plugin")
KICAD_AGENT_SRC = os.path.join(REPO_ROOT, "src", "kicad_agent")
METADATA_SRC = os.path.join(PLUGIN_SRC, "metadata.json")
ICON_SRC = os.path.join(PLUGIN_SRC, "resources", "icon.png")


def build_pcm_package():
    os.makedirs(DIST_DIR, exist_ok=True)
    zip_name = "kicad-ai-copilot-v1.0.0.zip"
    zip_path = os.path.join(DIST_DIR, zip_name)

    if os.path.exists(zip_path):
        os.remove(zip_path)

    print(f"Building KiCad PCM package: {zip_path}")

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        # 1. metadata.json at root
        if os.path.exists(METADATA_SRC):
            zf.write(METADATA_SRC, "metadata.json")
            print("  + metadata.json")

        # 2. resources/icon.png
        if os.path.exists(ICON_SRC):
            zf.write(ICON_SRC, "resources/icon.png")
            print("  + resources/icon.png")

        # 3. plugins/*.py
        for fname in os.listdir(PLUGIN_SRC):
            fpath = os.path.join(PLUGIN_SRC, fname)
            if os.path.isfile(fpath) and fname.endswith(".py"):
                arcname = f"plugins/{fname}"
                zf.write(fpath, arcname)
                print(f"  + {arcname}")

        # 4. plugins/resources/icon.png
        if os.path.exists(ICON_SRC):
            zf.write(ICON_SRC, "plugins/resources/icon.png")
            print("  + plugins/resources/icon.png")

        # 5. plugins/kicad_agent/ (standalone bundled engine)
        for root, dirs, files in os.walk(KICAD_AGENT_SRC):
            dirs[:] = [d for d in dirs if d != "__pycache__"]
            for file in files:
                if file.endswith((".py", ".json", ".md")):
                    full_p = os.path.join(root, file)
                    rel_p = os.path.relpath(full_p, os.path.join(REPO_ROOT, "src"))
                    arcname = f"plugins/{rel_p.replace(os.sep, '/')}"
                    zf.write(full_p, arcname)

        print("  + plugins/kicad_agent (bundled engine)")

    # Compute SHA256
    with open(zip_path, "rb") as f:
        sha256 = hashlib.sha256(f.read()).hexdigest()
    size_bytes = os.path.getsize(zip_path)

    print(f"\nPackage created successfully:")
    print(f"  File: {zip_path}")
    print(f"  Size: {size_bytes / 1024:.1f} KB")
    print(f"  SHA256: {sha256}")
    return zip_path


if __name__ == "__main__":
    build_pcm_package()
