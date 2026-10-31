#!/bin/sh
# OnionOS Launcher Template for Miyoo Mini / Miyoo Mini Plus
# Place inside /mnt/SDCARD/Roms/PORTS/<GameName>/launch.sh

PORT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PORT_DIR"

# 1. Performance Tuning: Set CPU governor to performance (1.2 GHz)
if [ -f /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor ]; then
    echo performance > /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor
fi

# 2. Free RAM: Unload MainUI if device is memory-constrained (optional for 128MB budget)
# killall -9 MainUI

# 3. Environment paths
export HOME="$PORT_DIR"
export LD_LIBRARY_PATH="$PORT_DIR/lib:$LD_LIBRARY_PATH"
export MONO_PATH="$PORT_DIR/lib/mono:$PORT_DIR"

# 4. Clear screen buffer before start
cat /dev/zero > /dev/fb0 2>/dev/null

# 5. Run executable with log capture
./game_executable > "$PORT_DIR/game.log" 2>&1

# 6. Post-exit cleanup & restore
sync
