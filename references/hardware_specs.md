# Miyoo Mini / Miyoo Mini Plus Hardware Reference

Comprehensive specifications and low-level kernel interfaces for the Miyoo Mini and Miyoo Mini Plus handheld consoles.

---

## 1. System Architecture

- **SoC**: SigmaStar SSD202D
- **CPU**: Dual-core ARM Cortex-A7 @ 1.2 GHz
  - ISA: ARMv7-A (`armhf`)
  - Floating Point: VFPv4-d16
  - SIMD: ARM NEON
  - L1 Cache: 32 KB I-Cache + 32 KB D-Cache per core
  - L2 Cache: 256 KB Shared
- **RAM**: 128 MB DDR3 (Integrated SIP)
  - OS / Kernel allocation: ~35-45 MB
  - Usable user-space memory: ~60-80 MB max
  - Out-of-Memory (OOM) threshold: Triggered when allocations exceed ~85-90 MB

---

## 2. Display & Framebuffer (`/dev/fb0`)

- **Screen Resolution**: 640×480 pixels, 4:3 Aspect Ratio IPS LCD
- **Internal Driver Node**: `/dev/fb0`
- **Color Format**: 32-bit ARGB8888 (or 16-bit RGB565 depending on kernel mode)
- **Physical Mounting Quirk**:
  - The LCD panel on the Miyoo Mini / Plus is mounted upside-down (180° rotated).
  - To display properly without kernel rotation overhead, write rows backwards:
    $$\text{dst\_y} = (\text{height} - 1 - y)$$
    $$\text{dst\_x} = (\text{width} - 1 - x)$$
- **Upscaling Strategy**:
  - Software rendering 640×480 with per-pixel alpha blending at 60 FPS taxes Cortex-A7 memory bandwidth.
  - Recommended internal render target: **320×240** (or **320×180** 16:9 letterboxed).
  - Use NEON horizontal pixel duplication + vertical line-pair memory copies to double resolution with minimal CPU cost.

---

## 3. Audio Subsystem

- **Hardware**: SigmaStar Media Interface Audio Output (`MI_AO`) / ALSA
- **Sample Rate**: 44.1 kHz or 48.0 kHz 16-bit stereo PCM
- **Latency / Buffer**: Use double-buffered ring buffers (512 or 1024 samples per chunk).
- **Driver Caveat**: Avoid re-initializing ALSA or opening multiple sound streams simultaneously. Multiplex audio streams in software before pushing to `/dev/snd/pcmC0D0p` or SDL2 audio callback.

---

## 4. Input (`/dev/input/event0`)

Button inputs are routed via Linux `evdev` GPIO keys:

| Button | Linux Keycode Name | Keycode Decimal | Recommended Bitmask |
| :--- | :--- | :--- | :--- |
| **D-Pad Up** | `KEY_UP` | 103 | `0x0001` |
| **D-Pad Down** | `KEY_DOWN` | 108 | `0x0002` |
| **D-Pad Left** | `KEY_LEFT` | 105 | `0x0004` |
| **D-Pad Right** | `KEY_RIGHT` | 106 | `0x0008` |
| **A** | `KEY_SPACE` | 57 | `0x0010` |
| **B** | `KEY_LEFTCTRL` | 29 | `0x0020` |
| **X** | `KEY_LEFTALT` | 56 | `0x0040` |
| **Y** | `KEY_LEFTSHIFT` | 42 | `0x0080` |
| **L1** | `KEY_E` | 18 | `0x0100` |
| **R1** | `KEY_T` | 20 | `0x0200` |
| **L2** | `KEY_TAB` | 15 | `0x0400` |
| **R2** | `KEY_BACKSPACE` | 14 | `0x0800` |
| **Start** | `KEY_RETURN` | 28 | `0x1000` |
| **Select** | `KEY_RIGHTCTRL` | 97 | `0x2000` |
| **Menu** | `KEY_HOME` | 102 | `0x4000` |
