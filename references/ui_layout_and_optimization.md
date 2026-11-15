# Small-screen UI proportions, controller ergonomics and memory optimization

Findings consolidated from the desktop-to-`640x480` port and user feedback iterations on [Slay the Spire](https://github.com/devarshi16/slay-the-spire-miyoo), built for a dual-core ARMv7 Cortex-A7 with ~101 MiB physical RAM (`103360 KiB MemTotal`) + 128 MiB swap and no programmable 3D GPU. Use these patterns as concrete engineering baselines for UI-heavy ports; measure every threshold on the target game.

## Display mode and proportional budgeting

Choose the framebuffer resolution according to the game's readability floor rather than forcing a single mode:

- **Pixel-art / low-res games:** `320x240` rendered in 32-bit RGBA and integer-upscaled 2x (180-deg rotated) to the `640x480` hardware framebuffer.
- **Text-heavy / card / strategy games:** native `640x480` (4:3) framebuffer (`isMobile=1`, `isFourByThree=1`, `isLetterbox=0`), projecting the game's logical camera (`1920x1080` or desktop coordinates) directly into `640x480` and keeping pointer/touch hooks mapped `1:1`.

On a 3.5-inch `640x480` panel, proportional uniform downscaling (`0.3333x`) breaks small UI text, tightens grids until labels collide, and shrinks card/item hitboxes. Re-budget layout constants by role rather than scaling everything linearly:

1. **Enforce a typography floor and selective density scaling:**
   - Clamp minimum bitmap/FreeType generation sizes before downscaling (`< 26.0 -> 26.0` in 1080p units yielded ~`8.7 px` readable glyphs on `640x480` in Slay the Spire).
   - When body copy in multi-column settings overflows onto dividers (`x=315..325`), scale the dense body pass selectively (`0.86x` in Preferences) instead of shrinking section headers or global text.
   - Brighten saturated status tints (`+` card upgrade green `(0.58, 1.00, 0.48)`) and draw a tight dark outline (`(0.02, 0.05, 0.01)` at `±0.65` offset) so colored titles stay legible over light card banners on an uncalibrated LCD.

2. **Size HUD containers around worst-case labels and badges:**
   - Give top bars enough vertical height (`TOPBAR_H=62.0`, `ICON_W=24.0`, `ICON_Y=450.0`, `NAME_Y=475.0`, `POTION_Y=462.0`) so health counters, gold, potions, icons, and shortcut glyphs stay enclosed inside the bar rather than bleeding underneath.
   - Tighten selection highlights (`HP 66x34`, `Gold 48x34`) to match actual glyph bounds and center enlarged shortcut badges (`1.25x` `SELECT`/`LB`/`START`) beneath their icons clear of adjacent counters (e.g., deck counts).

3. **Upscale interactive cards/grids while protecting margins:**
   - Boost base non-hovered card scales (`* 1.14`, capped at `0.94f`), preview cards (`0.96f`), and shop cards (`>= 0.90f`) so card rules and costs remain scannable without hovering every item.
   - Compute side-by-side preview card offsets dynamically from scaled widths (`0.5 * img_w * (parent_scale + preview_scale) + pad`) instead of hardcoding desktop gaps.
   - Pack two-row shops (`DRAW_START_X=28.0`, `TOP_ROW_Y=330.0`, `BOTTOM_ROW_Y=162.0`, `GOLD_OFF_Y=-78.0`, `PRICE_OFF_Y=-66.0`) so row-2 price tags sit cleanly above bottom-edge controller exit hints (`(B) Leave`).

4. **Widen, clamp, and de-collide tooltips:**
   - Narrow tooltips wrap into tall unreadable strips when scaled `0.333x`; widen tooltip boxes (`BOX_W=154.7`, `BODY_W=135.3`, `LINE_SPACING=13.5`), clamp them inside `[0, 640] x [0, 480]`, and track active side-preview bounds (`cardsToPreview`) per frame so keyword tooltips shift clear of card art instead of covering adjacent cards or text.

## Controller aesthetics and D-Pad completeness audit

Hardware tester feedback routinely catches UI mismatches that never appear in single-frame boot tests:

- **Match physical button colors and labels:** Miyoo face buttons follow SNES colors (`A` Red, `B` Yellow, `X` Blue, `Y` Green). Recolor uploaded Xbox-colored button glyphs in RGBA (`recolor_controller_button_rgba`: `A=(235,35,45)`, `B=(245,200,20)`, `X=(45,130,240)`, `Y=(45,205,65)` preserving low-chroma outlines/letters `chroma <= 16`) so prompt icons match the physical shell.
- **Audit shoulder vs trigger legends cleanly:** Verify on hardware evdev mappings whether physical `L1/R1` drive bumper (`LB`/`RB`) signals and `L2/R2` drive trigger (`LT`/`RT`) axes/buttons. Keep that legend consistent across top bars, Settings tabs, and Save/Quit popups.
- **Keep confirmation ribbons and button glyphs aligned:** In Yes/No dialogs (`ConfirmPopup`), center labels vertically inside their green (`Yes`) and red (`No`) banners and anchor `(Y)` / `(B)` icons directly beneath them (`x=256.7`/`383.3`, `y=150.1`, `scale=0.450`). When hooking draw functions to adjust prompt offsets, check for caller register clobbering or tail calls (`renderButtons -> renderControllerUi`).
- **Eliminate D-Pad dead-ends and cursor snaps across every screen state:**
  - Verify D-Pad entry/traversal into HUD bars (Potions, Relics, Map/Deck/Settings) not only in Combat, but also in special/event rooms (`?`), during mid-run map progression (`DungeonMapScreen`), and in Shops.
  - Clear lingering cursor hitboxes (`DungeonMapScreen+68` `mapNodeHb`) when switching into a relic/HUD sub-mode so per-frame update loops do not snap focus back to the map or grid.
  - Guard against empty middle enum sections when wrapping left/right across the top bar (skip empty `Section.MODS` arrays to prevent `IndexOutOfRangeException`).
  - Suppress phantom mouse/stick hover flags (`bg_hb->hovered` on sliders) so unused right-stick (`(R)`) indicators do not appear on a stickless handheld.
  - Use column-aware neighbor selection for 2D checkboxes/sliders rather than raw index stepping.
  - Confirm **every** confirm prompt (`GridCardSelectScreen`) and resource-exhausted screen (`ShopScreen` at `0` Gold) displays a visible `(B)` cancel/leave hint and handles `B` press (`OverlayMenu.cancelButton` -> `CancelButton::update`).

## Memory (`~101 MiB` RAM) and CPU optimization techniques

Heavy C#/JVM/libGDX or mobile-authored 2D games exhaust ~101 MiB physical RAM rapidly if desktop-sized textures, font atlases, GC heaps, or symbol tables stay resident:

1. **Virtual-dimension pre-downscaling (`"STSR"`):**
   - For tiled/packed atlases with normalized UVs in separate metadata (`.atlas`), decoding large GPU-compressed KTX/ETC2 pages offline or on first launch into a smaller payload (`>= 512px -> 1/4x`, `>= 256px -> 1/2x`, `< 256px -> 1x`) while **preserving original `pixelWidth`/`pixelHeight` in the header** avoids rewriting dozens of `.atlas` UV maps (across 85 `.atlas` files in Slay the Spire: `753.18 MB` raw at 1080p -> `47.07 MB` `"STSR"` RGBA8888).
   - Weight RGB averaging by alpha during box downscaling (`wsum = sum(alpha)`, `out_rgb = round(sum(rgb * alpha) / wsum)` when `wsum > 0`) to eliminate black halos along transparent sprite cutouts.

2. **Split texture storage precision (`RGBA32` vs `RGBA4444`):**
   - Keep small UI icons, fonts, and recolored controller buttons (`<= 256x256`) at full 32-bit `RGBA32` sharpness.
   - Store larger (`> 256px`) sprites, card art, and scene backgrounds in 16-bit `RGBA4444` (`933` textures totaled `30,433 kB` in Slay the Spire, avoiding an `89.5 MB` swap thrash / `SIGKILL`).

3. **Garbage collector, FreeType, and ELF page hygiene:**
   - When hosting Boehm GC / conservative collectors: call `GC_set_force_unmap_on_gcollect(1)`, raise `GC_set_free_space_divisor(16)`, wire explicit `java::nio::Buffer::_dispose` -> `GC_free`, and invoke `GC_gcollect_and_unmap()` + `malloc_trim(0)` at loading milestones.
   - Cap `FreeTypeFontGenerator.maxTextureSize` (`512 -> 256`) and alias unexercised multi-megabyte CJK TrueType font trees to a compact fallback font when running non-CJK locales (`~122 MB -> 18,504 kB` GC heap, font load `10,578 ms -> 460 ms`, dropping OOM to `VmRSS=69,724 kB`, `VmSwap=136 kB`).
   - When loading a huge shared library manually with `mmap`, apply `.rel.dyn`/`.rel.plt` relocations first and immediately call `madvise(..., MADV_DONTNEED)` on symbol/string/relocation pages (`18.8 MB` reclaimed before `.ARM.exidx`).

4. **Dual-core cache-sized band rasterization (`12x40`):**
   - For high-overdraw orthographic sprites (`187–500+` quads/frame) on dual Cortex-A7 cores without a GPU, partition the `640x480` framebuffer into horizontal bands sized to fit L2 cache (`12` bands x `40 px` rows ≈ `100 KB`/band at `640 * 40 * 4` bytes) and record draw commands per frame rather than rasterizing immediately.
   - Dispatch odd/even bands across 2 worker `pthread`s, discard prior draws behind opaque full-screen clears, take an opaque-texel fast path (`alpha >= 0xF000u`) skipping alpha math, and flush pending bands before mutating or deleting any referenced texture.
   - Wrapping existing draw routines with linker `-Wl,--wrap=*` keeps the optimization separable from core draw logic for clean differential testing and benchmarking.
