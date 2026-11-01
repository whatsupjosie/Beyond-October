#!/bin/sh
# Rebuild static/foresight_matter.wasm from static/foresight_matter.cpp. Needs clang and wasm-ld.
set -e
cd "$(dirname "$0")/../static"
clang --target=wasm32 -O3 -nostdlib -ffreestanding -fno-exceptions -fno-rtti -std=c++17 -c foresight_matter.cpp -o /tmp/foresight_matter.o
wasm-ld --no-entry --export-dynamic --initial-memory=67108864 --max-memory=67108864 -o foresight_matter.wasm /tmp/foresight_matter.o
echo "Built static/foresight_matter.wasm"
