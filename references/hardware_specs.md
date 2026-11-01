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

Onion's audio service can provide an OSS/FIFO route. A direct MI_AO port may deliberately use Onion's `KillAudioserver` path: observed Onion 4.3.1-1 includes `stop_audioserver.sh`, and its runtime restarts the service. Other firmware/workflows may differ. Choose and test one coherent ownership model; never combine a competing direct backend with an assumed live service. The native template has **no audio backend**. Use bounded blocking operations, retry EINTR where appropriate, and restore resources/settings on all exit paths. Verify MainUI audio and another application after exit.

## Packaging and QA

Use Onion's shortcut/category layout and verify GameExecutable/GameDataFile exist. SD FAT32 has no normal POSIX symlinks/permissions; transfer real files and pack bulk assets. The observed card used `dirsync`. Runtime HOME must be writable. Compatible dynamic libraries must stay within the target libc symbol ABI (the audited target used glibc 2.28); a recent host compiler may introduce newer requirements.

Do not casually change CPU governor, network-service retention flags, audio ownership or MainUI. If QA requires a reversible change, record and restore its prior state. Use isolated test ports/saves. Read the actual visible page and stride for screenshots; framebuffer reads belong outside performance-critical loops.

## Performance evidence

Measure managed/game logic, command collection, raster drawing, framebuffer conversion and blocking pan separately. Compare identical saves, scenes, input, CPU mode and audio settings; record actual wall-clock FPS with profiling disabled. A fixed simulation timestep is useful for controlled comparisons but does not establish real-time gameplay performance. Preserve the original physics frequency when optimizing, and identify any intentional simulation slowdown separately.

For software rendering, benchmark repeated palette shading, off-screen shading and vertical gradients before assuming final framebuffer blitting dominates. Cache only when every relevant shader parameter is in the key. Verify optimized pixels against scalar reference paths, including translucent palettes, recolor thresholds, flipped/clipped sprites and UI fades. A native frame replay is useful for separating renderer cost from game-logic cost; captures contain owned game pixels and must not be published.
