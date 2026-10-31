#!/usr/bin/env python3
"""
triage_game.py — Automated engine detection and Miyoo Mini Plus feasibility analysis.

Usage:
    python3 triage_game.py /path/to/game_directory

Analyzes target games against SigmaStar SSD202D hardware constraints:
- Dual Cortex-A7 @ 1.2 GHz
- 128 MB RAM (Target process budget: <= 60 MB)
- No 3D GPU / /dev/fb0 software blitter
"""

import os
import sys
import json
from pathlib import Path

# Size thresholds in Megabytes
RAM_BUDGET_MB = 65.0
WARN_TEXTURE_MB = 35.0
CRIT_TEXTURE_MB = 70.0

def scan_directory(root_dir):
    root = Path(root_dir)
    if not root.is_dir():
        print(f"Error: {root_dir} is not a valid directory.")
        sys.exit(1)

    total_bytes = 0
    ext_counts = {}
    ext_sizes = {}
    files_list = []

    for p in root.rglob("*"):
        if p.is_file():
            sz = p.stat().st_size
            total_bytes += sz
            ext = p.suffix.lower()
            ext_counts[ext] = ext_counts.get(ext, 0) + 1
            ext_sizes[ext] = ext_sizes.get(ext, 0) + sz
            files_list.append(p)

    return root, total_bytes, ext_counts, ext_sizes, files_list

def detect_engine(root, files_list, ext_counts):
    # Check for Unity
    has_managed = any(p.is_dir() and p.name.lower() in ("managed", "monomanaged") for p in root.rglob("*"))
    has_unity_player = any("unityplayer" in p.name.lower() or "unity" in p.name.lower() for p in files_list)
    has_unity_assets = any(p.name.lower().endswith((".assets", ".unity3d", ".sharedassets")) for p in files_list)
    has_csharp = any("assembly-csharp.dll" in p.name.lower() for p in files_list)
    if has_managed or has_csharp or (has_unity_player and has_unity_assets):
        return {
            "engine": "Unity",
            "managed": True,
            "has_csharp": has_csharp,
            "confidence": 0.95 if (has_managed and (has_unity_assets or has_csharp)) else 0.80,
            "notes": "Unity 2D title. Feasible via Clean-Room UnityEngine replacement + Mono runtime."
        }

    # Check for MonoGame / XNA / FNA
    has_xnb = ".xnb" in ext_counts
    has_xna_dll = any("microsoft.xna.framework" in p.name.lower() or "fna.dll" in p.name.lower() for p in files_list)
    if has_xnb or has_xna_dll:
        return {
            "engine": "MonoGame / XNA / FNA",
            "managed": True,
            "has_csharp": True,
            "confidence": 0.95 if (has_xnb and has_xna_dll) else 0.80,
            "notes": "XNA/MonoGame title. High feasibility: SpriteBatch calls map 1:1 to miyoo_core blitter."
        }

    # Check for GameMaker Studio
    has_data_win = any(p.name.lower() in ("data.win", "game.unx", "game.droid", "game.ios") for p in files_list)
    if has_data_win:
        return {
            "engine": "GameMaker Studio",
            "managed": False,
            "has_csharp": False,
            "confidence": 0.95,
            "notes": "GameMaker bytecode package detected. Feasible via custom runner or GML decompilation."
        }

    # Check for Godot
    has_pck = ".pck" in ext_counts
    has_godot_project = any(p.name.lower() in ("project.godot", "engine.cfg") for p in files_list)
    if has_pck or has_godot_project:
        return {
            "engine": "Godot Engine",
            "managed": False,
            "has_csharp": False,
            "confidence": 0.90,
            "notes": "Godot package detected. Feasible for 2D titles by building minimal ARMHF headless core with software rasterizer."
        }

    # Fallback to Custom C/C++ or native
    has_elf = any(p.suffix == "" and os.access(p, os.X_OK) for p in files_list)
    has_dll = ".dll" in ext_counts
    return {
        "engine": "Custom C/C++ or Unrecognized",
        "managed": has_dll and not has_elf,
        "has_csharp": False,
        "confidence": 0.50,
        "notes": "Decompile main binary via REA (Reverse Engineer Anything) to identify entry points and rendering pipeline."
    }

def analyze_feasibility(total_bytes, ext_sizes, engine_info):
    img_exts = {".png", ".jpg", ".jpeg", ".tga", ".bmp", ".dds", ".pvr", ".ktx"}
    audio_exts = {".wav", ".ogg", ".mp3", ".flac", ".bank", ".fsb"}
    
    img_size_mb = sum(ext_sizes.get(e, 0) for e in img_exts) / (1024 * 1024)
    audio_size_mb = sum(ext_sizes.get(e, 0) for e in audio_exts) / (1024 * 1024)
    total_size_mb = total_bytes / (1024 * 1024)

    # Estimate uncompressed texture footprint (assuming average 4x expansion for compressed/PNG to RGBA32)
    est_uncompressed_tex_mb = img_size_mb * 3.5

    feasibility = "HIGH"
    recommendations = []

    if est_uncompressed_tex_mb > CRIT_TEXTURE_MB:
        feasibility = "CHALLENGING (Requires Aggressive Downsampling)"
        recommendations.append(f"Texture footprint (~{est_uncompressed_tex_mb:.1f} MB) exceeds device RAM safe budget ({RAM_BUDGET_MB} MB).")
        recommendations.append("Action: Must convert textures to 8-bit indexed palette (RGBA palette + indexed buffer) via pack_assets.py.")
    elif est_uncompressed_tex_mb > WARN_TEXTURE_MB:
        feasibility = "MODERATE"
        recommendations.append(f"Texture footprint (~{est_uncompressed_tex_mb:.1f} MB) is near memory threshold.")
        recommendations.append("Action: Pack into 16-bit RGB565 / RGBA4444 or downscale oversized sprite sheets.")
    else:
        recommendations.append("Texture memory footprint fits comfortably within 128 MB RAM constraints.")

    if audio_size_mb > 30.0:
        recommendations.append(f"Audio footprint ({audio_size_mb:.1f} MB) is high. Stream sound effects and music from disk; do not preload into RAM.")
    else:
        recommendations.append("Audio footprint is acceptable for disk streaming.")

    if engine_info["engine"] == "Unity":
        recommendations.append("Unity Workflow: Use REA to extract IL assembly delta, run gen_shim.py, and link to miyoo_core.c.")
    elif engine_info["engine"] == "MonoGame / XNA / FNA":
        recommendations.append("MonoGame Workflow: Extract XNB files to PNG/WAV, provide lightweight XNA shim routing to miyoo_core.c.")
    elif engine_info["engine"] == "GameMaker Studio":
        recommendations.append("GameMaker Workflow: Use UndertaleModTool or REA to dump bytecode and textures, connect to miyoo_core.c blitter.")
    elif engine_info["engine"] == "Godot Engine":
        recommendations.append("Godot Workflow: Extract .pck, verify 2D only (no 3D nodes), compile custom godot-server binary with /dev/fb0 rasterizer.")

    return {
        "feasibility": feasibility,
        "total_size_mb": round(total_size_mb, 2),
        "texture_size_mb": round(img_size_mb, 2),
        "est_uncompressed_tex_mb": round(est_uncompressed_tex_mb, 2),
        "audio_size_mb": round(audio_size_mb, 2),
        "recommendations": recommendations
    }

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 triage_game.py <game_folder>")
        sys.exit(1)

    target_dir = sys.argv[1]
    print(f"[*] Triaging target game directory: {target_dir}...")
    root, total_bytes, ext_counts, ext_sizes, files_list = scan_directory(target_dir)
    engine_info = detect_engine(root, files_list, ext_counts)
    report = analyze_feasibility(total_bytes, ext_sizes, engine_info)

    print("\n=======================================================")
    print("      MIYOO MINI PLUS PORT FEASIBILITY REPORT         ")
    print("=======================================================")
    print(f"Engine Identified : {engine_info['engine']} (Confidence: {int(engine_info['confidence']*100)}%)")
    print(f"Notes             : {engine_info['notes']}")
    print(f"Total Disk Size   : {report['total_size_mb']} MB")
    print(f"Textures on Disk  : {report['texture_size_mb']} MB (~{report['est_uncompressed_tex_mb']} MB uncompressed)")
    print(f"Audio on Disk     : {report['audio_size_mb']} MB")
    print(f"Port Feasibility  : {report['feasibility']}")
    print("-------------------------------------------------------")
    print("Recommendations & Next Steps:")
    for r in report["recommendations"]:
        print(f"  • {r}")
    print("=======================================================\n")

if __name__ == "__main__":
    main()
