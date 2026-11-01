#!/bin/sh
# OnionOS Standalone Port Launcher
# Deployed to: /mnt/SDCARD/Roms/PORTS/Games/<GameDir>/launch.sh
# Invoked via: /mnt/SDCARD/Roms/PORTS/Shortcuts/<Category>/<GameName>.port

PORT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PORT_DIR"

# 1. Performance Tuning: Set CPU governor to performance (1.2 GHz)
if [ -f /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor ]; then
    echo performance > /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor
fi

# 2. Environment paths
export HOME="$PORT_DIR"
export LD_LIBRARY_PATH="$PORT_DIR/lib:/customer/lib:$LD_LIBRARY_PATH"
export MONO_PATH="$PORT_DIR/lib/mono:$PORT_DIR"

# 3. Audio setup: OnionOS uses audioserver over /dev/dsp via libpadsp
# If using dynamic linking with OSS:
# export LD_PRELOAD="/customer/lib/libpadsp.so"

# 4. Optional: Keep SSH/WiFi alive during QA
# touch /mnt/SDCARD/.tmp_update/config/.keepServicesAlive

# 5. Run executable with log capture
./game_executable > "$PORT_DIR/game.log" 2>&1

# 6. Post-exit cleanup
sync
