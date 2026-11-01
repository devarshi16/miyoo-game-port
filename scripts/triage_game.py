#!/usr/bin/env python3
"""
triage_game.py — Automated engine detection and Miyoo Mini Plus feasibility analysis.

Usage:
    python3 triage_game.py /path/to/game_directory

Analyzes target games against SigmaStar SSD202D hardware constraints:
- Dual Cortex-A7 @ 1.2 GHz
- 128 MB RAM (measure the actual working-set budget)
- No 3D GPU / /dev/fb0 software blitter
"""

import os
import sys
import json
from pathlib import Path

# Size thresholds in Megabytes


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
            "managed": has_csharp,
            "has_csharp": has_csharp,
            "confidence": 0.95 if (has_managed and (has_unity_assets or has_csharp)) else 0.80,
            "notes": "Unity indicators found. Mono/IL2CPP, engine version and 2D/3D requirements must be verified."
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
            "notes": "XNA/MonoGame indicators found. Verify framework version, content formats and native dependencies."
        }

    # Check for GameMaker Studio
    has_data_win = any(p.name.lower() in ("data.win", "game.unx", "game.droid", "game.ios") for p in files_list)
    if has_data_win:
        return {
            "engine": "GameMaker Studio",
            "managed": False,
            "has_csharp": False,
            "confidence": 0.95,
            "notes": "GameMaker package name detected. Verify VM/YYC, format version and compatible runtime availability."
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
            "notes": "Godot indicators found. A headless build alone does not supply a rendering backend."
        }

    # Fallback to Custom C/C++ or native
    def is_elf(p):
        try:
            with p.open("rb") as f: return f.read(4) == b"\x7fELF"
        except OSError: return False
    has_elf = any(is_elf(p) for p in files_list)
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

    # Inventory cannot see decoded textures or native dependencies inside game containers.
    return {
        "feasibility": "UNKNOWN (runtime, decoded assets and device measurements required)",
        "total_size_mb": round(total_size_mb, 2),
        "texture_size_mb": round(img_size_mb, 2),
        "audio_size_mb": round(audio_size_mb, 2),
        "recommendations": [
            "Loose image/audio sizes exclude data inside packed containers; zero means unmeasured, not zero runtime memory.",
            "Identify the exact engine version, IL versus native compilation, dependencies and exercised API.",
            "Inspect decoded assets and implement a small playable slice before estimating memory or FPS.",
            "Measure total RSS, native allocations and swap on the actual device; do not infer a fixed process limit from disk size.",
        ],
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
    print(f"Loose Images      : {report['texture_size_mb']} MB (packed/decoded footprint UNKNOWN)")
    print(f"Audio on Disk     : {report['audio_size_mb']} MB")
    print(f"Port Feasibility  : {report['feasibility']}")
    print("-------------------------------------------------------")
    print("Recommendations & Next Steps:")
    for r in report["recommendations"]:
        print(f"  • {r}")
    print("=======================================================\n")

if __name__ == "__main__":
    main()
