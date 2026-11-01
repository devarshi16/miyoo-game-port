# Cross-Engine Miyoo Mini Porting Guide

This document details the architectural adaptations required when porting games from various game engines to the Miyoo Mini / Miyoo Mini Plus using the **Clean-Room Recompilation & Hardware Blit (CRRHB)** pattern.

---

## 1. Engine Comparison Overview

| Engine | Original Runtime | Miyoo Strategy | RAM Footprint | Porting Complexity |
| :--- | :--- | :--- | :--- | :--- |
| **Unity (Old 2D / 4.x - 2017)** | Mono + UnityEngine native C++ | Clean-room C# `UnityEngine` shim + `miyoo_core.c` + Mono ARMHF | 40-50 MB | High initial setup, repeatable across titles |
| **MonoGame / XNA / FNA** | .NET / C# + SDL2 / DirectX / OpenGL | Clean-room `FNA` / `Microsoft.Xna.Framework` shim + `miyoo_core.c` | 25-40 MB | **Lowest complexity** (Cleanest API separation) |
| **GameMaker Studio (1.4 / 2.x)** | YoYo C++ Runner + Bytecode (`data.win`) | Clean-room bytecode runner or GML decompilation to C++ | 20-35 MB | Moderate |
| **Godot 2D (3.x / 4.x)** | Godot C++ Core + GLES2 / GLES3 | Minimal headless ARMHF Godot build + `/dev/fb0` software rasterizer | 40-50 MB | High (Engine baseline RAM is large) |
| **Custom C / C++ 2D** | SDL / OpenGL / Custom | Direct compilation with `arm-linux-gnueabihf-gcc` + `miyoo_core.c` | 15-30 MB | Low to Moderate (depends on source access) |
| **Retro Software 3D (Quake, PS1-era)** | C/C++ Software Rasterizers | Multi-core horizontal screen split (Core 0 top, Core 1 bottom) | 20-40 MB | Moderate (Proven on TyrQuake, REDRIVER2, dethrace) |
| **Modern 3D (Unreal, Unity 2021+ 3D)** | Modern Vulkan/DX11/GLES3 Shaders | **INCOMPATIBLE** (No 3D GPU hardware) | >100 MB | Not feasible |

---

## 2. Retro Software 3D on Dual Cortex-A7 (Field Verified)

While modern GPU-accelerated 3D games are infeasible, **era-appropriate software 3D rasterizers** (Quake engine, Driver 2, Carmageddon) run remarkably well:
1. **Resolution Feasibility**: *TyrQuake* renders natively at **640×480 @ 60 FPS** (averaging 12.7–13.3 ms per frame). Fixed triangle setup and raster row setup dominate, so dropping below 320×240 offers minimal gain.
2. **Dual-Core Scaling**:
   - The second Cortex-A7 core yields ~1.45× scaling (not 2.0× due to shared L2 cache bandwidth).
   - Divide the display horizontally into top and bottom render bands.
   - Dynamically rebalance the horizontal split line each frame based on polygon density.
   - Pin render threads to cores (`pthread_setaffinity_np`) and ensure spin-waits yield (`sched_yield()`).
3. **Compiler Tuning**:
   - Compiling with `-O3 -fno-strict-aliasing -fsigned-char` + Profile-Guided Optimization (PGO) and Link-Time Optimization (LTO) yields a ~7% framerate boost over `-O2`.

---

## 3. MonoGame / XNA / FNA (e.g., Celeste, Fez, Stardew Valley 1.3)

### Why It Transfers Seamlessly (~95% identical to Unity workflow):
1. **Managed Runtime**: Like Unity, MonoGame runs on C# / Mono. The Miyoo Mini already has a working `mono-sgen` ARMHF runtime.
2. **Standardized Drawing API**: All drawing goes through `SpriteBatch.Draw(Texture2D, Vector2, Rectangle?, Color, float, Vector2, Vector2, SpriteEffects, float)`.
3. **No Heavy Engine Core**: Unlike Unity, MonoGame has no 200MB C++ engine blob. The entire engine is just `FNA.dll` or `Microsoft.Xna.Framework.dll`.

### Adaptation Steps:
1. **Asset Extraction**: Extract `.xnb` textures and sounds using REA or `xnbcli` into PNG and WAV files.
2. **Shim Implementation**: Write a clean-room `Microsoft.Xna.Framework.Graphics.SpriteBatch` class routing to `miyoo_draw_sprite()`.
3. **Asset Repack**: Run `pack_assets.py` to convert textures to 8-bit indexed palette format.

---

## 4. GameMaker Studio (e.g., Undertale, Hotline Miami, Downwell)

### Why It Transfers Well (~85%):
1. **Bytecode Container**: GameMaker packages everything into `data.win` (Windows) or `game.unx` (Linux).
2. **Standardized GML Instruction Set**: GameMaker games execute GML (GameMaker Language) opcodes or decompiled scripts.

### Adaptation Steps:
- **Strategy A (Bytecode Runner)**: Adapt an open-source lightweight GM runner (such as `gmloader`) compiled for ARM Cortex-A7, routing draw calls to `miyoo_draw_sprite()`.
- **Strategy B (Decompilation to Native C++)**: Use REA or `UndertaleModTool` to decompile scripts into clean C++ logic, then compile with `arm-linux-gnueabihf-gcc` directly against `miyoo_core.c`.

---

## 5. Godot Engine 2D (e.g., Brotato, Dome Keeper)

### Adaptation Steps:
1. **Custom Minimal Build**: Compile Godot from source with ARMHF flags, disabling unused 3D, physics, and navigation modules:
   ```bash
   scons platform=server target=release_debug tools=no module_bullet_enabled=no module_visual_script_enabled=no
   ```
2. **Software Rasterizer Backend**: Provide a custom `VisualServer` rasterizer that flips double-buffered pages into `/dev/fb0` using `miyoo_flip()`.
3. **Memory Clamping**: Downsample textures in `project.godot` or pre-process `.pck` assets to prevent loading uncompressed textures into the tight ~45 MB usable memory budget.
