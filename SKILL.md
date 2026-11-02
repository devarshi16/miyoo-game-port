---
name: miyoo-game-port
description: Assess and develop game ports for Miyoo Mini and Mini Plus on OnionOS, including engine compatibility, asset conversion, native rendering, packaging and hardware validation. Use for an actual porting or port-audit task; this skill is scaffolding, not an automatic converter or a guarantee that a game is portable.
metadata:
  version: "1.2.2"
  platform: "miyoo-mini-plus"
  os: "onionos"
---

# Miyoo game port development

Preserve the user's game, device and output requirements. Distinguish engine signatures, working implementations, measured results and hypotheses. Existing source ports and compatible runtimes may be preferable to replacing an engine. REA is optional: use available binary/metadata tools rather than assuming a particular MCP is installed.

## Establish feasibility

Run `scripts/triage_game.py <game-directory>` as an inventory. It does not establish engine version, 2D/3D requirements, decoded asset memory, source availability or runtime cost. Packed assets remain unknown until inspected. Do not assign transferability percentages or declare feasibility from compressed file sizes.

Record exact game build fingerprints, engine/API requirements, required native dependencies and licensing/provenance. For Unity, distinguish Mono IL from IL2CPP; finding a Managed directory alone is insufficient. Shader, physics, UI, input, serialization and lifecycle semantics can be gameplay-critical even in a visually simple game. Consult [engine strategies](references/engine_matrix.md) for bounded research options.

## Probe the target

Read [hardware guidance](references/hardware_specs.md) before device integration. Inspect the actual Onion version, MemAvailable/swap, framebuffer fixed/variable info, pixel bitfields, active page, audio ownership, input mapping and dynamic ABI requirements. Historical measurements describe one workload/device, not universal limits.

The native template supports **320×240 RGBA rendering → 640×480, 32-bit framebuffer, 2× rotation/scaling**. It validates that mode, uses the reported stride and restores the original pan. It is a starting backend without an audio implementation, pack reader or game runtime. Other modes need an explicit backend; fail clearly rather than writing an assumed layout.

Choose either Onion audio service/OSS integration or a deliberately managed direct-MI backend. Match initialization, ownership and cleanup. Do not blindly kill audioserver or blindly leave it running with a competing direct backend. Restore the platform on exit and test a subsequently launched application.

## Implement and verify

1. Prototype one real game slice before broadening a compatibility claim. Stub generation supplies declarations and throwing placeholders, not working engine semantics. `scripts/gen_shim.py` and `scripts/api_surface.py` are Unity-oriented helpers; the generated throwing code uses `KNL.Log.Missing`, supplied by `templates/managed/StubLog.cs`. Both two-stage inspection helpers are included. Adapt the reference-assembly selection for another game/framework.
2. Extract owned data with a game/build-specific importer. `scripts/pack_assets.py` consumes **already extracted** images and generic files; it cannot unpack `.assets`, `.pck`, `.win`, `.xnb` or game DLLs. Indexed output preserves exact RGBA palettes up to 256 colors and falls back to RGBA32 above that. Do not silently discard partial alpha. Its MPAK format requires a reader in the game's runtime.
3. Separate developer cross-compilation from player setup. Make device versus desktop output explicit. The build template requires an existing ARM game executable; it does not generate one. `templates/build/compile.sh --desktop` builds only the preview core. For device staging, follow that script's usage and supply its required executable, names and extracted assets.
4. Keep source assets out of distributable archives. Validate required data/DLLs, source fingerprints, conversion counts, pack bounds and output checksums. Use fresh work directories and staged installation with rollback; preserve saves. Success means output validation passed, not merely a zero exit status from one subprocess.
5. Add focused behavioral regressions for reproduced failures. Unity-style adapters need tests for coroutine phases/cancellation, effective activation, hierarchy/component cache invalidation, input edges, game/unscaled/wall clocks, save round trips and orderly exit. A zero-exception boot or visually correct screenshot does not prove gameplay equivalence.
   For importer, font, camera, joint, and cache failures, consult [compatibility regressions](references/compatibility_regressions.md) before replacing original behavior with special cases.
6. Build a versioned candidate from a clean checkout, recording source commit, toolchain and dependency versions, hashes and third-party notices. Test the **extracted release package** using the player route, not only the developer's SD directory.

## Device QA and performance

Use an isolated test port and copied or fresh saves. Check the current state before launching; preserve services and settings used during QA and restore changes afterward. Standard Onion directory layout is `Roms/PORTS/Shortcuts/<Category>/<name>.port` plus `Roms/PORTS/Games/<dir>/`. A shortcut must reference real executable/data paths.

For screenshots, `scripts/raw_to_png.py` requires the actual dimensions, bit depth, stride and visible pan offset; rotate as appropriate. Reading a framebuffer for an occasional screenshot is different from reading uncached video memory in the render loop.

Measure logic, rasterization, copy/conversion, vsync, allocations, total RSS and swap separately with fixed input/workloads. MI_GFX may accelerate presentation, but does not automatically accelerate the software renderer. Compare stock clocks before considering optional tuning. Do not promise an FPS gain before a device benchmark.

On-device source compilation is a separate toolchain/resource question from first-run asset conversion. A PC converter's peak memory does not prove every importer is impossible. For copy-paste installation research, prototype incremental metadata, texture and audio conversion with a measured memory budget, progress reporting and recovery after interruption; report unimplemented steps honestly.

Before calling a release stable, verify tutorial/progression, menu navigation, upgrades, repeated save/load, long sessions and clean return to Onion with subsequent audio/video working. Keep untested items visible and avoid recommending purchases based only on a prototype.
