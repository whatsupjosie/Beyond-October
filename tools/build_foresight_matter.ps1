# Rebuild static\foresight_matter.wasm from static\foresight_matter.cpp (Windows PowerShell 5).
# Needs LLVM (clang and wasm-ld) on PATH:  winget install LLVM.LLVM
# The built .wasm is already shipped; you only need this after changing the C++.
$ErrorActionPreference = 'Stop'
$static = Join-Path $PSScriptRoot '..\static'
$src = Join-Path $static 'foresight_matter.cpp'
$obj = Join-Path $env:TEMP 'foresight_matter.o'
$out = Join-Path $static 'foresight_matter.wasm'
& clang --target=wasm32 -O3 -nostdlib -ffreestanding -fno-exceptions -fno-rtti -std=c++17 -c $src -o $obj
if ($LASTEXITCODE -ne 0) { throw 'clang failed' }
& wasm-ld --no-entry --export-dynamic --initial-memory=67108864 --max-memory=67108864 -o $out $obj
if ($LASTEXITCODE -ne 0) { throw 'wasm-ld failed' }
Write-Host "Built $out"
