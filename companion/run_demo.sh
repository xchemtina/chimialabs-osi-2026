#!/bin/sh
set -eu
cd "$(dirname "$0")"
if [ -d "$PWD/adapter/.cargo-home/registry" ]; then
  export CARGO_HOME="${CARGO_HOME:-$PWD/adapter/.cargo-home}"
fi
export CARGO_TARGET_DIR="${CARGO_TARGET_DIR:-$PWD/adapter/target}"
cargo run --offline --locked --manifest-path adapter/Cargo.toml -- "$@"
