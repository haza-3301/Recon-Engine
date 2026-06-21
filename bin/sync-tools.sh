#!/usr/bin/env bash
# Copy PD binaries into repo tools_bin/ (optional — prefer: python install.py install)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="${1:-${HEPH_TOOLS:-}}"
DST="$ROOT/tools_bin"
if [[ -z "$SRC" || ! -d "$SRC" ]]; then
  echo "Usage: HEPH_TOOLS=/path/to/bin $0" >&2
  echo "   or: $0 /path/to/bin" >&2
  exit 1
fi
mkdir -p "$DST"
for pair in "httpx:pd-httpx" "dnsx:dnsx"; do
  src_name="${pair%%:*}"
  dst_name="${pair##*:}"
  cp -f "$SRC/$src_name" "$DST/$dst_name"
  chmod +x "$DST/$dst_name"
  echo "✔ $SRC/$src_name → $DST/$dst_name"
done
