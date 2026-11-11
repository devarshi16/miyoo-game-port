---
name: miyoo-game-port
description: Assess and develop game ports for Miyoo Mini and Mini Plus on OnionOS, including engine compatibility, asset conversion, native rendering, packaging and hardware validation. Use for an actual porting or port-audit task; this skill is scaffolding, not an automatic converter or a guarantee that a game is portable.
metadata:
  version: "1.4.0"
  platform: "miyoo-mini-plus"
  os: "onionos"
---

# Miyoo game port development

Preserve the user's game, device and output requirements. Distinguish engine signatures, working implementations, measured results and hypotheses. Existing source ports and compatible runtimes may be preferable to replacing an engine. REA is optional: use available binary/metadata tools rather than assuming a particular MCP is installed.

## Establish feasibility

Run `scripts/triage_game.py <game-directory>` as an inventory. It does not establish engine version, 2D/3D requirements, decoded asset memory, source availability or runtime cost. Packed assets remain unknown until inspected. Do not assign transferability percentages or declare feasibility from compressed file sizes.

Record exact game build fingerprints, engine/API requirements, required native dependencies and licensing/provenance. For Unity, distinguish Mono IL from IL2CPP; finding a Managed directory alone is insufficient. Shader, physics, UI, input, serialization and lifecycle semantics can be gameplay-critical even in a visually simple game. Consult [engine strategies](references/engine_matrix.md) for bounded research options.

Look for a compatible runtime before planning a native build. Minit shipped by patching an open GameMaker bytecode runner, with no native template, importer or engine rewrite. Pin the exact runner branch and commit, and sort its reported unknown functions into main-path gaps and platform stubs; a static grep of source or disassembly gave wrong answers there.

If a community port already exists, read its licence and fork it before starting over. Balatro was improved as a GPL-3.0 fork. Review it against desktop on the device with the owner, because an existing port can run while dropping fidelity: Balatro's had a substituted font, hidden shop sign, static background, missing scanlines and Xbox-coloured button prompts. Keep the stock clock as the default and report overclocked results separately.

## Probe the target

Read [hardware guidance](references/hardware_specs.md) before device integration. Inspect the actual Onion version, MemAvailable/swap, framebuffer fixed/variable info, pixel bitfields, active page, audio ownership, input mapping and dynamic ABI requirements. Historical measurements describe one workload/device, not universal limits.

The native template supports **320×240 RGBA rendering → 640×480, 32-bit framebuffer, 2× rotation/scaling**. It validates that mode, uses the reported stride and restores the original pan. It is a starting backend without an audio implementation, pack reader or game runtime. Other modes need an explicit backend; fail clearly rather than writing an assumed layout.

For a runtime with SDL support, probe `SDL_Init(VIDEO)` on the device before committing to a library. The audited sysroot's SDL2 has only a dummy video driver, while Onion's SDL 1.2 in `/customer/lib` worked and required no bundled library. Expect to check orientation on the first device run: the SDL 1.2 frame was upside down on a Mini Plus and needed 180° rotation in the backend.

Choose either Onion audio service/OSS integration or a deliberately managed direct-MI backend. Match initialization, ownership and cleanup. Do not blindly kill audioserver or blindly leave it running with a competing direct backend. Restore the platform on exit and test a subsequently launched application. Onion's volume overlay depends on MI_AO and audioserver state, so test the volume keys as well as sound. See [hardware guidance](references/hardware_specs.md) for a direct MI_AO configuration that fixed tearing in Minit.

## Implement and verify

1. Prototype one real game slice before broadening a compatibility claim. Stub generation supplies declarations and throwing placeholders, not working engine semantics. `scripts/gen_shim.py` and `scripts/api_surface.py` are Unity-oriented helpers; the generated throwing code uses `KNL.Log.Missing`, supplied by `templates/managed/StubLog.cs`. Both two-stage inspection helpers are included. Adapt the reference-assembly selection for another game/framework.
2. Extract owned data with a game/build-specific importer. `scripts/pack_assets.py` consumes **already extracted** images and generic files; it cannot unpack `.assets`, `.pck`, `.win`, `.xnb` or game DLLs. Indexed output preserves exact RGBA palettes up to 256 colors and falls back to RGBA32 above that. Do not silently discard partial alpha. Its MPAK format requires a reader in the game's runtime.
3. Separate developer cross-compilation from player setup. Make device versus desktop output explicit. The build template requires an existing ARM game executable; it does not generate one. `templates/build/compile.sh --desktop` builds only the preview core. For device staging, follow that script's usage and supply its required executable, names and extracted assets.
4. Keep source assets out of distributable archives. Validate required data/DLLs, source fingerprints, conversion counts, pack bounds and output checksums. Use fresh work directories and staged installation with rollback; preserve saves. Success means output validation passed, not merely a zero exit status from one subprocess.
5. Add focused behavioral regressions for reproduced failures. Unity-style adapters need tests for coroutine phases/cancellation, effective activation, hierarchy/component cache invalidation, input edges, game/unscaled/wall clocks, save round trips and orderly exit. A zero-exception boot or visually correct screenshot does not prove gameplay equivalence.
   For importer, font, camera, joint, and cache failures, consult [compatibility regressions](references/compatibility_regressions.md) before replacing original behavior with special cases.
6. Build a versioned candidate from a clean checkout, recording source commit, toolchain and dependency versions, hashes and third-party notices. Test the **extracted release package** using the player route, not only the developer's SD directory.
7. For a runner that reads the owner's files directly, prefer a bring-your-own-data ZIP: runner, launcher, shortcut and an empty data folder, with no importer. Point the shortcut's `GameDataFile` at the shipped launcher so it can start and report missing files. Make the packaging script refuse any owned file in the archive. Check third-party test fixtures too, since upstream sources can carry their own game data.
8. For a copyleft runner, ship the licence, pinned commit and complete patched source. Regenerate the patch at packaging time: a staged patch and player note went stale during Minit's development. Rebuild from that source and compare hashes with the shipped binary. Compiled-in paths and cached library lookups can change the bytes, so record the build folder and pin the library paths.
9. Publishing a repository or release is the owner's decision. Ask for it directly, and have the exact commands ready in case the agent's permissions block it. Keep captures with game audio out of the repository and release.

## Device QA and performance

Build debug output into the device build early, because a person is often the only observer of a running game. SSH can be unavailable while a Ports launch runs, and a run started over SSH with MainUI up can stall or lose audio, so it is not a substitute. Deploy at the Onion menu, ask the person to test a named behavior, then read logs after exit. Useful outputs are the last presented frame, room or scene changes with positions, and slow frames with their step time. Per-frame logging itself can cause FPS and sound dips: 430,000 renderer lines did in Minit, so remove it before judging performance.

When the owner allows on-device testing, a scripted run is possible without them: pause MainUI with `killall -STOP MainUI`, run the port's own launcher with autoplay or replay variables and a separate save folder, then `killall -CONT MainUI`. Writing a `cmd_to_run.sh` and killing MainUI did not launch the port on Onion 4.3.1. Replays can inject real button events by writing `input_event` records to `/dev/input/event0`, which exercises the kernel and evdev reader too. See [hardware guidance](references/hardware_specs.md) for slow Wi-Fi transfers and raster profiling.

Never stop MainUI or audioserver by process name during probing. `pkill -f` on audioserver left audio down until a power cycle. Use Onion's own launch path or a power cycle. Probe for the device's address rather than trusting saved notes, and tell the person when Wi-Fi is the blocker instead of reporting a device result you did not get.

Show progress through every long startup stage, because a black screen reads as a crash. Find each stall on the device before adding it to the bar. Map every button deliberately against the game's own prompts, and decide what Menu does early: replaying a game's own save-and-quit path is cheap, but it is not a suspend and must be described that way.

Use an isolated test port and copied or fresh saves. Check the current state before launching; preserve services and settings used during QA and restore changes afterward. Standard Onion directory layout is `Roms/PORTS/Shortcuts/<Category>/<name>.port` plus `Roms/PORTS/Games/<dir>/`. A shortcut must reference real executable/data paths.

For screenshots, `scripts/raw_to_png.py` requires the actual dimensions, bit depth, stride and visible pan offset; rotate as appropriate. Reading a framebuffer for an occasional screenshot is different from reading uncached video memory in the render loop.

Measure logic, rasterization, copy/conversion, vsync, allocations, total RSS and swap separately with fixed input/workloads. MI_GFX may accelerate presentation, but does not automatically accelerate the software renderer. Compare stock clocks before considering optional tuning. Do not promise an FPS gain before a device benchmark.

Create isolated combat fixtures using the original spawn and attack paths when late-game performance is the problem. Record actual spawned counts and season state. Compare deterministic combat outcomes as well as FPS, then run ordinary real-time timing separately. See [compatibility regressions](references/compatibility_regressions.md) for query and importer checks learned from device failures.

On-device source compilation is a separate toolchain/resource question from first-run asset conversion. A PC converter's peak memory does not prove every importer is impossible. For copy-paste installation research, prototype incremental metadata, texture and audio conversion with a measured memory budget, progress reporting and recovery after interruption; report unimplemented steps honestly.

Before calling a release stable, verify tutorial/progression, menu navigation, upgrades, repeated save/load, long sessions and clean return to Onion with subsequent audio/video working. Keep untested items visible and avoid recommending purchases based only on a prototype.
