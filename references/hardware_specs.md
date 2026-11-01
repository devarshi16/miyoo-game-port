# Miyoo Mini / Miyoo Mini Plus Hardware Reference

Comprehensive specifications and verified low-level kernel interfaces for the Miyoo Mini and Miyoo Mini Plus (OnionOS / SigmaStar SSD202D).

---

## 1. System Architecture & Memory Limits

- **SoC**: SigmaStar SSD202D
- **CPU**: Dual-core ARM Cortex-A7 @ 1.2 GHz
  - ISA: ARMv7-A (`armhf`)
  - Floating Point: VFPv4-d16
  - SIMD: ARM NEON
  - L1 Cache: 32 KB I-Cache + 32 KB D-Cache per core
  - L2 Cache: 256 KB Shared
- **RAM Limits (Field Verified)**:
  - Physical DDR3 SIP: 128 MB
  - **Usable User-Space Total (`MemTotal`)**: **~103 MB** (Kernel and SigmaStar hardware MMA buffers carve out ~25 MB).
  - **Free Memory Under MainUI**: **~5–15 MB** (Swap enabled).
  - **Target Process Budget**: **<= 40–50 MB** resident set size (RSS).

---

## 2. Display, Refresh Rate & Framebuffer (`/dev/fb0`)

- **Screen Resolution**: 640×480 IPS LCD (4:3 aspect ratio).
- **True Panel Refresh**: **59.67 Hz** (16.76 ms per frame).
  > [!WARNING]
  > The timing fields in `fb_var_screeninfo` and `/sys/class/graphics/fb0/modes` claim **75 Hz**. This is hardcoded kernel misinformation. Frame pacing must be locked to 59.67 Hz (16.76 ms).
- **Framebuffer Layout & Double Buffering**:
  - Virtual height is **960** (2 pages: $640 \times 960$, 32 bpp) or **1440** (3 pages under MainUI).
  - Active visible page is tracked at `/sys/class/graphics/fb0/pan`.
  - Double-buffering is controlled via `ioctl(fbfd, FBIOPAN_DISPLAY, &vinfo)` with `vinfo.yoffset = page * 480`.
  - Writing strictly to offset 0 causes visual tearing or draws to an invisible buffer.
- **Uncached Framebuffer Memory**:
  - The `/dev/fb0` memory mapping is **uncached**. Never read from it. Write to it with contiguous, burst stores only.
- **VSync Blocking**:
  - `FBIOPAN_DISPLAY` blocks until the next hardware refresh (~8 ms average).
  - Never call vsync/pan from two threads at once; both threads will enter kernel `D` state, pans will spike to ~1.5 s, and the device will hang.
- **Physical Mounting Quirk**:
  - The LCD panel is physically mounted upside down (180° rotated).
  - Traverse rows in reverse: $\text{dst\_y} = (h - 1 - y)$ and $\text{dst\_x} = (w - 1 - x)$.

---

## 3. Hardware 2D Engine (MI_GFX / libssgfx.so)

The SigmaStar SSD202D contains a dedicated 2D hardware bit-blit engine (`MI_GFX`):
- Library: `/customer/lib/libssgfx.so` or `/customer/lib/libmi_gfx.so`.
- Function: `MI_GFX_BitBlit()` performs hardware RGB565 $\to$ ARGB8888 conversion, $2\times$ scaling, and 180° rotation (`SstarBlitHVFlip`) in **~1.1 ms** with zero CPU consumption.
- Cleanup Requirement: On shutdown, applications using MMA/GFX must call `MI_GFX_WaitAllDone()`, unmap MMA buffers, call `MI_GFX_Close()`, and pan back to page 0. Failure to do so causes a black screen upon returning to MainUI.

---

## 4. Audio Subsystem (OnionOS audioserver & OSS)

- **Ownership**: On OnionOS, `/dev/mi_ao` is permanently owned by Onion's `/mnt/SDCARD/miyoo/app/audioserver`.
- **Audio Output Paths**:
  1. **OSS Compatibility**: Write 16-bit stereo PCM to `/dev/dsp` via `LD_PRELOAD=/customer/lib/libpadsp.so`.
  2. **Direct FIFO Protocol**: Static binaries can write directly to audioserver's named pipes:
     - PCM Stream: `/tmp/audio_fifo_server` (S16 stereo 48 kHz).
     - IOCTL Request/Response: `/tmp/audio_fifo_ioctl_req` and `/tmp/audio_fifo_ioctl_res`.
- **Crucial Rules**:
  - **Never kill `audioserver`**: Without it, `/dev/dsp` writes fail, MainUI seizes `mi_ao`, and audioserver cannot recover until a reboot.
  - **Handle `EINTR`**: All audio write loops must retry on `EINTR` (profiler signals will otherwise drop audio blocks).

---

## 5. Input Mapping (`/dev/input/event0`)

Button inputs are routed via Linux `evdev` GPIO keys:

| Button | Linux Keycode Name | Keycode Decimal | Recommended Bitmask |
| :--- | :--- | :---: | :--- |
| **D-Pad Up** | `KEY_UP` | 103 | `0x0001` |
| **D-Pad Down** | `KEY_DOWN` | 108 | `0x0002` |
| **D-Pad Left** | `KEY_LEFT` | 105 | `0x0004` |
| **D-Pad Right** | `KEY_RIGHT` | 106 | `0x0008` |
| **A** | `KEY_SPACE` | 57 | `0x0010` |
| **B** | `KEY_LEFTCTRL` | 29 | `0x0020` |
| **X** | `KEY_LEFTSHIFT` | **42** | `0x0040` |
| **Y** | `KEY_LEFTALT` | **56** | `0x0080` |
| **L1** | `KEY_E` | 18 | `0x0100` |
| **R1** | `KEY_T` | 20 | `0x0200` |
| **L2** | `KEY_TAB` | 15 | `0x0400` |
| **R2** | `KEY_BACKSPACE` | 14 | `0x0800` |
| **Start** | `KEY_ENTER` | 28 | `0x1000` |
| **Select** | `KEY_RIGHTCTRL` | 97 | `0x2000` |
| **Menu** | `KEY_ESC` | **1** | `0x4000` |
| **Power** | `KEY_POWER` | 116 | `0x8000` |

*Note: The input loop must use non-blocking `poll()` with a timeout. Calling `close()` on a blocking `read()` will hang `pthread_join()` during exit.*

---

## 6. Timers & Clocks

- **Timer Granularity**: The Linux 4.9 kernel on SSD202D does not have high-resolution POSIX timers. Both `nanosleep(100µs)` and `nanosleep(1ms)` take **~10 ms**.
- **Frame Pacing**: Compute elapsed delta times via `clock_gettime(CLOCK_MONOTONIC)`. Only sleep if remaining frame time is $> 10$ ms.

---

## 7. Toolchain & ABI Requirements

- **C Library**: glibc **2.28** (`libc-2.28.so`). Dynamic libraries (`.so`) must not require symbols above glibc 2.28.
- **Signed Chars**: Compile with `-fsigned-char` (ARM default is unsigned, which breaks x86 port logic).
- **Thread Local Storage**: Use `tls_model("local-exec")` for `__thread` variables in static binaries.
