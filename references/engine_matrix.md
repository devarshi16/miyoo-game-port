# Cross-Engine Miyoo Mini Porting Guide

This document details the architectural adaptations required when porting games from various game engines to the Miyoo Mini / Miyoo Mini Plus using the **Clean-Room Recompilation & Hardware Blit (CRRHB)** pattern.

---

## 1. Engine Comparison Overview

| Engine | Original Runtime | Miyoo Strategy | RAM Footprint | Porting Complexity |
| :--- | :--- | :--- | :--- | :--- |
| **Unity (Old 2D / 4.x - 2017)** | Mono + UnityEngine native C++ | Clean-room C# `UnityEngine` shim + `miyoo_core.c` + Mono ARMHF | 40-55 MB | High initial setup, repeatable across titles |
| **MonoGame / XNA / FNA** | .NET / C# + SDL2 / DirectX / OpenGL | Clean-room `FNA` / `Microsoft.Xna.Framework` shim + `miyoo_core.c` | 25-45 MB | **Lowest complexity** (Cleanest API separation) |
| **GameMaker Studio (1.4 / 2.x)** | YoYo C++ Runner + Bytecode (`data.win`) | Clean-room bytecode runner or GML decompilation to C++ | 20-40 MB | Moderate |
| **Godot 2D (3.x / 4.x)** | Godot C++ Core + GLES2 / GLES3 | Minimal headless ARMHF Godot build + `/dev/fb0` software rasterizer | 45-65 MB | High (Engine baseline RAM is large) |
| **Custom C / C++ 2D** | SDL / OpenGL / Custom | Direct compilation with `arm-linux-gnueabihf-gcc` + `miyoo_core.c` | 15-35 MB | Low to Moderate (depends on source access) |

---

## 2. MonoGame / XNA / FNA (e.g., Celeste, Fez, Stardew Valley 1.3)

### Why It Transfers Seamlessly (~95% identical to Unity workflow):
1. **Managed Runtime**: Like Unity, MonoGame runs on C# / Mono. The Miyoo Mini already has a working `mono-sgen` ARMHF runtime.
2. **Standardized Drawing API**: All drawing goes through `SpriteBatch.Draw(Texture2D, Vector2, Rectangle?, Color, float, Vector2, Vector2, SpriteEffects, float)`.
3. **No Heavy Engine Core**: Unlike Unity, MonoGame has no 200MB C++ engine blob. The entire engine is just `FNA.dll` or `Microsoft.Xna.Framework.dll`.

### Adaptation Steps:
1. **Asset Extraction**: Extract `.xnb` textures and sounds using REA or `xnbcli` into PNG and WAV files.
2. **Shim Implementation**: Write a clean-room `Microsoft.Xna.Framework.Graphics.SpriteBatch` class:
   ```csharp
   public void Draw(Texture2D texture, Vector2 position, Rectangle? sourceRectangle, Color color) {
       miyoo_draw_sprite(texture.Id, (int)position.X, (int)position.Y, 
                         sourceRectangle?.X ?? 0, sourceRectangle?.Y ?? 0,
                         sourceRectangle?.Width ?? texture.Width,
                         sourceRectangle?.Height ?? texture.Height,
                         color.PackedValue, false, false);
   }
   ```
3. **Asset Repack**: Run `pack_assets.py` to convert textures to 8-bit indexed palette format.

---

## 3. GameMaker Studio (e.g., Undertale, Hotline Miami, Downwell)

### Why It Transfers Well (~85%):
1. **Bytecode Container**: GameMaker packages everything into `data.win` (Windows) or `game.unx` (Linux).
2. **Standardized GML Instruction Set**: GameMaker games execute GML (GameMaker Language) opcodes or decompiled scripts.

### Adaptation Steps:
- **Strategy A (Bytecode Runner)**: Adapt an open-source lightweight GM runner (such as `gmloader` or custom bytecode virtual machine) compiled for ARM Cortex-A7. Instead of delegating to OpenGL ES, patch the draw calls (`draw_sprite`, `draw_surface`) to invoke `miyoo_draw_sprite()`.
- **Strategy B (Decompilation & Native C++ Recompilation)**: Use REA or `UndertaleModTool` to decompile scripts into clean C++ logic, then compile with `arm-linux-gnueabihf-gcc` directly against `miyoo_core.c`.

---

## 4. Godot Engine 2D (e.g., Brotato, Dome Keeper)

### Challenges on Miyoo Mini:
1. **No OpenGL ES 2.0/3.0 GPU**: Godot's standard rendering backend requires OpenGL.
2. **Binary & Memory Overhead**: Standard Godot export templates carry 3D physics, navigation, and audio modules that consume 40MB+ of RAM before game logic loads.

### Adaptation Steps:
1. **Custom Minimal Build**: Compile Godot from source with ARMHF flags, disabling unused subsystems:
   ```bash
   scons platform=server target=release_debug tools=no module_bullet_enabled=no module_visual_script_enabled=no
   ```
2. **Software Rasterizer Backend**: Provide a custom `VisualServer` rasterizer implementation that renders canvas items into a 320×240 memory buffer and flushes to `/dev/fb0` using `miyoo_flip()`.
3. **Memory Clamping**: Downsample textures in `project.godot` or pre-process `.pck` assets to prevent loading uncompressed 4K textures into the 128MB RAM space.

---

## 5. Custom C / C++ 2D Engines

### Why It Is Highly Feasible (~90-95%):
1. Native source or decompiled functions can be directly recompiled for Cortex-A7.
2. Memory is strictly deterministic and does not suffer from managed garbage collector stalls.

### Adaptation Steps:
1. Locate the platform video output function (e.g. `SDL_RenderPresent`, `glFlush`, or `SwapBuffers`).
2. Replace it with `miyoo_flip()`.
3. Map mouse or keyboard input arrays to `miyoo_get_input()`.
