#!/bin/sh
set -eu
PORT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PORT_DIR"
export HOME="$PORT_DIR"
export LD_LIBRARY_PATH="$PORT_DIR/lib:/config/lib:/customer/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
# Audio backend/ownership is game-specific. No audio backend or system tuning is implied here.
exec ./game_executable > "$PORT_DIR/game.log" 2>&1
