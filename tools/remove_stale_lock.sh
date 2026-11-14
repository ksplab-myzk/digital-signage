#!/bin/bash
set -eu

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOCK_FILE="$SCRIPT_DIR/../digital_signage.lock"
LOCK_FILE="$(cd "$(dirname "$LOCK_FILE")" && pwd)/$(basename "$LOCK_FILE")"

if [ -f "$LOCK_FILE" ]; then
    rm -- "$LOCK_FILE"
    printf '%s - Removed stale signage lock file: %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$LOCK_FILE"
else
    printf '%s - No signage lock file to remove: %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$LOCK_FILE"
fi
