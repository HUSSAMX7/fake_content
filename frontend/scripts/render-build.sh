#!/usr/bin/env bash
set -euo pipefail

export NPM_CONFIG_AUDIT=false
export NPM_CONFIG_FUND=false
export NODE_OPTIONS="${NODE_OPTIONS:---max-old-space-size=460}"
export NEXT_TELEMETRY_DISABLED=1

npm ci

if [[ -n "${XDG_CACHE_HOME:-}" && -d "${XDG_CACHE_HOME}/next" ]]; then
  mkdir -p .next
  cp -r "${XDG_CACHE_HOME}/next" .next/cache
fi

npm run build

if [[ -n "${XDG_CACHE_HOME:-}" && -d ".next/cache" ]]; then
  mkdir -p "${XDG_CACHE_HOME}"
  rm -rf "${XDG_CACHE_HOME}/next"
  cp -r .next/cache "${XDG_CACHE_HOME}/next"
fi
