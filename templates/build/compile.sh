#!/usr/bin/env bash
# Stage an already implemented game; this template does not generate a game runtime.
set -euo pipefail
SKILL_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
OUT="${MIYOO_OUTPUT:-$SKILL_ROOT/dist}"
if [ "${1:-}" = --desktop ]; then
    mkdir -p "$OUT/desktop"
    gcc -O2 -shared -fPIC -DMIYOO_DESKTOP "$SKILL_ROOT/templates/native_core/miyoo_core.c" \
        -o "$OUT/desktop/libmiyoo_core.so" $(pkg-config --cflags --libs sdl2) -lpthread
    echo "Desktop core only: $OUT/desktop/libmiyoo_core.so (no game runtime built)"
    exit 0
fi
if [ "$#" -ne 5 ]; then
    echo "Usage: $0 <extracted-assets> <existing-ARM-executable> <GameName> <GameDir> <Category>" >&2
    echo "Or: $0 --desktop (preview core only)" >&2
    exit 1
fi
ASSETS="$1"; EXE="$2"; NAME="$3"; DIR="$4"; CATEGORY="$5"
for value in "$DIR" "$CATEGORY"; do
    [[ "$value" =~ ^[A-Za-z0-9_-]+$ ]] || { echo "GameDir/category must be simple folder names" >&2; exit 1; }
done
[[ "$NAME" =~ ^[A-Za-z0-9' '_-]+$ ]] || { echo "GameName contains unsupported shortcut characters" >&2; exit 1; }
[ -d "$ASSETS" ] && [ -f "$EXE" ] || { echo "Missing extracted assets or game executable" >&2; exit 1; }
python3 - "$EXE" <<'PYELF'
import struct,sys
with open(sys.argv[1],'rb') as f: h=f.read(52)
if len(h)!=52 or h[:6]!=b'\x7fELF\x01\x01': raise SystemExit('Expected ELF32 little-endian ARM executable')
kind,machine=struct.unpack_from('<HH',h,16)
entry,phoff=struct.unpack_from('<II',h,24)
phsize,phnum=struct.unpack_from('<HH',h,42)
flags=struct.unpack_from('<I',h,36)[0]
if kind not in (2,3) or machine!=40 or not entry or not phoff or phsize!=32 or not phnum:
    raise SystemExit('Input is not a loadable ARM executable; object files and desktop fallback are unsupported')
if not flags & 0x400: raise SystemExit('Expected ARM hard-float ABI; verify against the target loader')
with open(sys.argv[1],'rb') as f:
    f.seek(phoff); table=f.read(phsize*phnum)
if len(table)!=phsize*phnum or not any(struct.unpack_from('<I',table,i*phsize)[0]==1 for i in range(phnum)):
    raise SystemExit('ARM executable has no loadable segments')
PYELF
CC="${MIYOO_CC:-arm-linux-gnueabihf-gcc}"
command -v "$CC" >/dev/null || { echo "Missing ARM compiler: $CC" >&2; exit 1; }
STAGE="$(mktemp -d)"; trap 'rm -rf "$STAGE"' EXIT
GAME="$STAGE/Roms/PORTS/Games/$DIR"
mkdir -p "$GAME/lib" "$STAGE/Roms/PORTS/Shortcuts/$CATEGORY"
python3 "$SKILL_ROOT/scripts/pack_assets.py" --input "$ASSETS" --output "$GAME/game.pack"
"$CC" -O2 -march=armv7-a -mfpu=neon-vfpv4 -mfloat-abi=hard -fsigned-char -fPIC -shared \
    "$SKILL_ROOT/templates/native_core/miyoo_core.c" -o "$GAME/lib/libmiyoo_core.so" -lpthread
python3 - "$EXE" "$GAME/lib/libmiyoo_core.so" <<'PY'
import re,subprocess,sys
for path in sys.argv[1:]:
    text=subprocess.check_output(['readelf','--version-info',path],text=True)
    versions=[tuple(map(int,m.split('.'))) for m in re.findall(r'GLIBC_(\d+\.\d+(?:\.\d+)?)',text)]
    if any(v>(2,28) for v in versions): raise SystemExit('ABI newer than glibc 2.28: '+path)
PY
cp "$EXE" "$GAME/game_executable"
cp "$SKILL_ROOT/templates/onionos/launch.sh" "$GAME/launch.sh"
cat > "$STAGE/Roms/PORTS/Shortcuts/$CATEGORY/$NAME.port" <<EOF
#!/bin/sh
/mnt/SDCARD/Emu/PORTS/launch_standalone.sh "$NAME" "$DIR" "launch.sh" "" "game.pack" "0" "0"
EOF
chmod +x "$GAME/launch.sh" "$GAME/game_executable" "$STAGE/Roms/PORTS/Shortcuts/$CATEGORY/$NAME.port"
mkdir -p "$OUT"
cp -r "$STAGE/Roms" "$OUT/"
echo "Staged candidate: $OUT/Roms. Requires the supplied game to implement its MPAK reader and platform integration."
