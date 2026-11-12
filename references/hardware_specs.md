# Miyoo Mini / Plus hardware integration

Baseline target: SigmaStar SSD202D, ARMv7 Cortex-A7, no programmable 3D GPU, firmware-specific 2D MI interfaces. Query the actual firmware and device rather than assuming every Onion installation has identical paths or state.

## Read-only reconnaissance

Over an already authorized SSH session, inspect `uname -a`, Onion's version, `/proc/meminfo`, `/proc/swaps`, mounted filesystems, running processes and `/sys/class/graphics/fb0/{virtual_size,bits_per_pixel,pan}`. Do not print unrelated configuration or credentials. The device commonly uses the `root` account; do not infer the username from a host alias.

A November 2026 Kingdom audit on one Onion 4.3.1-1 device observed MemTotal 103360 KiB, MemAvailable about 74180 KiB and 128 MiB unused swap with MainUI running. Other reports observed much less MemFree. MemFree is not MemAvailable; neither establishes a fixed per-process OOM threshold. Record RSS plus native/managed allocations and swap under the actual workload, leaving operating-system headroom.

Read `FBIOGET_FSCREENINFO` and `FBIOGET_VSCREENINFO`: use `line_length`, `smem_len`, virtual dimensions, offsets and color bitfields. Active pan may be a second or third page. Some applications select 16-bit modes. Validate or explicitly set/restore a supported mode before mapping/writing. The supplied core rejects modes other than 640×480, 32-bit with a 320×240 source and scale 2. It has scalar presentation, not a claimed NEON or MI_GFX implementation.

Community measurements report approximately 59.67 Hz and blocking pan behavior. Measure on the target. Keep one thread responsible for pan/vsync. MI_GFX can be investigated for final conversion/scaling/rotation using matching headers and buffer ownership; release MMA mappings/buffers and close the interfaces if used. No MI_GFX backend is included here.

## Input

Common evdev mapping: Up 103, Down 108, Left 105, Right 106, A SPACE/57, B LEFTCTRL/29, X LEFTSHIFT/42, Y LEFTALT/56, L1 E/18, R1 T/20, L2 TAB/15, R2 BACKSPACE/14, Start ENTER/28, Select RIGHTCTRL/97, Menu ESC/1, Power 116. Confirm on the target. The core uses atomics with a non-blocking fd and poll timeout; join before closing the fd. POWER events do not authorize implementing shutdown policy.

## Audio and exit

Onion's audio service can provide an OSS/FIFO route. A direct MI_AO port may deliberately use Onion's `KillAudioserver` path: observed Onion 4.3.1-1 includes `stop_audioserver.sh`. Read the actual launcher exit path; do not assume it restarts the service. Other firmware/workflows may differ. Choose and test one coherent ownership model; never combine a competing direct backend with an assumed live service. The native template has **no audio backend**. Use bounded blocking operations, retry EINTR where appropriate, and restore resources/settings on all exit paths. Verify MainUI audio and another application after exit. Pausing MainUI over SSH can retain its MI audio ownership even when audioserver is absent. A backend may then fail SetPubAttr and silently advance voices without audible output. Counted clip plays are not output verification. Check backend-open status and the restored process state, not merely whether a restart command was issued; use the normal frontend for audio QA. A controlled reboot of an idle, synced device can restore boot state after isolated QA, but does not by itself prove game sound.

## Packaging and QA

Use Onion's shortcut/category layout and verify GameExecutable/GameDataFile exist. SD FAT32 has no normal POSIX symlinks/permissions; transfer real files and pack bulk assets. The observed card used `dirsync`. Runtime HOME must be writable. Compatible dynamic libraries must stay within the target libc symbol ABI (the audited target used glibc 2.28); a recent host compiler may introduce newer requirements.

Do not casually change CPU governor, network-service retention flags, audio ownership or MainUI. If QA requires a reversible change, record and restore its prior state. Use isolated test ports/saves. Read the actual visible page and stride for screenshots; framebuffer reads belong outside performance-critical loops.

## Performance evidence

Measure managed/game logic, command collection, raster drawing, framebuffer conversion and blocking pan separately. Compare identical saves, scenes, input, CPU mode and audio settings; record actual wall-clock FPS with profiling disabled. A fixed simulation timestep is useful for controlled comparisons but does not establish real-time gameplay performance. Preserve the original physics frequency when optimizing, and identify any intentional simulation slowdown separately.

For software rendering, benchmark repeated palette shading, off-screen shading and vertical gradients before assuming final framebuffer blitting dominates. Cache only when every relevant shader parameter is in the key. Verify optimized pixels against scalar reference paths, including translucent palettes, recolor thresholds, flipped/clipped sprites and UI fades. A native frame replay is useful for separating renderer cost from game-logic cost; captures contain owned game pixels and must not be published.

Treat managed/native ABI changes as a single deployment unit. On unreliable Wi-Fi, an atomic rename of each individual DLL or shared library can still leave a mixed runtime if the transfer stops between files. Stage a complete isolated port, verify runtime hashes and copied save hashes, then replace the directory with rollback available. Bound SSH/SFTP timeouts and do not queue a launch after a failed transfer.

For mapped display memory, benchmark write order as well as conversion arithmetic. A cached scanline followed by contiguous row copies can avoid interleaved stores to two uncached rows. Preserve bitfields, rotation, integer scaling and padded stride, and compare every output byte on host and ARM. A faster copy microbenchmark alone does not establish a sustained game FPS improvement; blocking pan and managed work can remain limiting.

Before cutting visuals, verify both rendered cost and simulation work. A compatibility port may compute particles that its renderer never draws. Bypass only the verified cosmetic calculation, retain emitter initialization and clocks, and restore full work for callbacks/events/tracking consumers. Simplify reflected water with an opaque fill across the same region so stale pixels or blank strips cannot appear. Compare screenshots outside the intended effect region and verify day/night and weather readability, then measure real device FPS with profiling disabled.

For dense decorative clouds/fog, inspect the original controller and external consumers before changing authored budgets. Apply a verified named-controller budget before initial spawning; retain material initialization and weather updates, and confirm zero-budget pools are actually empty. For opaque water fills, earlier hidden sprite pixels can be clipped only when later coverage is proven; restore full bounds for foreground/HUD work and compare complete command lists byte-for-byte. Small HUD text can cost more in managed/native calls than in pixels: reuse a tiny atlas and draw one quad per glyph, checking exact output and stable texture memory across count changes.

A progress/indexing prototype can fit even when the old desktop converter does not. Measure its exact stage (hashing/indexing versus payload decoding), peak RSS and output parity on hardware; do not extrapolate a complete importer time or memory bound from index results.

## Video and audio through a runtime

Findings from the Minit port on one Mini Plus. Confirm them on the target.

The Mini sysroot's SDL2 2.0.16 has only the `dummy` video driver, so `SDL_Init(VIDEO)` fails with "No available video device". The steward-fu SDL2 needs a 22 MB GLES library, which the Kingdom port rejected for memory. Onion's SDL 1.2 in `/customer/lib` opens 320x240 and carries its own MI display, GFX and audio drivers. Its frame was upside down, and a 15-bit lookup table rotating RGB555 by 180° in the backend was sufficient. It also prints a line per frame, so send stdout to `/dev/null`. Runtimes without a working GL path need their software renderer tested as a separate target.

SDL 1.2 audio with `KillAudioserver=1` tore and left the volume keys dead, showing small unresponsive lines on the left of the screen. Keymon works through `/dev/mi_ao` and checks for `audioserver`. A direct MI_AO thread stopped the tearing, confirmed by ear on the device: 22050 Hz, stereo, 16-bit, 6 frames of 1024, blocking `MI_AO_SendFrame`, with a logged fallback to SDL if MI_AO fails to open. Link `-lmi_ao -lmi_sys` from the MI library folder with `--unresolved-symbols=ignore-in-shared-libs`, and preload `/config/lib/libcam_os_wrapper.so` in the launcher. Check the volume bar separately on each port.

Stopping audioserver with `pkill -9 -f app/audioserver` broke restart with `MI_AO_SetPubAttr ... 0xa0052009`, because another process held MI_AO. Only a power cycle recovered it.

The prebuilt compiler can be called directly with `--sysroot` through a CMake toolchain file when a toolchain wrapper points at a missing `/opt/prebuilt`.

## Findings from the Balatro fork

Findings from one Mini Plus on Onion 4.3.1-1. Confirm them on the target.

- **Transfers:** Wi-Fi ran at about 13 KB/s, so a 4 MB runtime took minutes. Send it gzipped (`gzip -9 -c | ssh ... gunzip > new && mv`), and install large one-off data through the SD card in the PC.
- **Toolchain without Docker:** the upstream build made static LuaJIT in an ARMv7 container. Zig 0.16 built it instead (`HOST_CC="zig cc -target x86-linux-musl"`, `CC="zig cc -target arm-linux-musleabihf -mcpu=cortex_a7"`). Clang emits `__floatdidf`-style helpers that GCC's `libgcc.a` did not resolve in the final link order, so a GCC-compiled shim forwarding to `__aeabi_*` went into the LuaJIT archive.
- **Screenshots:** read `/sys/class/graphics/fb0/pan`, take that 640x480 page of `/dev/fb0` (stride 2560, BGRA), and rotate it 180°.
- **Raster profiling:** a SIGPROF timer on the render thread, bucketing program counters and symbolising them with `nm` from the unstripped build, found a procedural background redraw taking about 70 ms. A fixed-point span fill cut it, and a half-resolution cache with a 2x upscale on copy cut it to a quarter again.
- **Free effects:** darkening alternate rows inside the NEON framebuffer copy on the presenter thread added scanlines without touching the render thread.
- **Frame-rate-dependent timing:** Balatro caps its smoothed dt at 0.1 s, so held D-pad repeat (0.3 s, then 0.1 s) ran about 3 times slower at 5 fps. Feeding held directions wall-clock time restored desktop timing. Check other dt-capped timers the same way.
- **Governor:** the performance governor and selective LuaJIT JIT scopes made no measurable difference in that workload. Measure before assuming either helps.
- **Button glyphs:** the Mini's face buttons follow SNES colours (A red, B yellow, X blue, Y green). Games usually show Xbox colours, so recolour or remap the glyph atlas.
