#!/usr/bin/env bash
# Universal BYOD Compilation & Packaging Template for Miyoo Mini Ports
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUILD_DIR="$SCRIPT_DIR/build"
OUTPUT_DIR="$SCRIPT_DIR/dist"

DATA_DIR="${1:-./game_data}"

echo "==========================================================="
echo "   Miyoo Mini Clean-Room Build & Packaging Pipeline        "
echo "==========================================================="

if [ ! -d "$DATA_DIR" ]; then
    echo "[!] Error: Game data directory '$DATA_DIR' not found."
    echo "    Usage: ./compile.sh <path_to_installed_game_data>"
    exit 1
fi

echo "[*] Step 1: Triaging input game data..."
python3 "$SCRIPT_DIR/scripts/triage_game.py" "$DATA_DIR"

echo "[*] Step 2: Extracting and packaging assets into linear pack..."
mkdir -p "$BUILD_DIR" "$OUTPUT_DIR"
python3 "$SCRIPT_DIR/scripts/pack_assets.py" --input "$DATA_DIR" --output "$OUTPUT_DIR/game.pack" --format indexed8

echo "[*] Step 3: Compiling native Cortex-A7 blitter core..."
if command -v arm-linux-gnueabihf-gcc >/dev/null 2>&1; then
    CC=arm-linux-gnueabihf-gcc
    CFLAGS="-O3 -march=armv7-a -mfpu=neon-vfpv4 -mfloat-abi=hard -fPIC -shared"
    echo "    Using ARM toolchain: $CC"
    $CC $CFLAGS "$SCRIPT_DIR/templates/native_core/miyoo_core.c" -o "$OUTPUT_DIR/libmiyoo_core.so" -lpthread
else
    echo "    [WARN] arm-linux-gnueabihf-gcc not found. Compiling desktop preview..."
    gcc -O3 -shared -fPIC -DMIYOO_DESKTOP "$SCRIPT_DIR/templates/native_core/miyoo_core.c" -o "$OUTPUT_DIR/libmiyoo_core.so" $(sdl2-config --cflags --libs) -lpthread
fi

echo "[*] Step 4: Staging OnionOS launcher..."
cp "$SCRIPT_DIR/templates/onionos/launch.sh" "$OUTPUT_DIR/launch.sh"
chmod +x "$OUTPUT_DIR/launch.sh"

echo "==========================================================="
echo "[+] Build complete! Output staged in: $OUTPUT_DIR"
echo "==========================================================="
