#!/bin/bash
# odl_heap: run a python script in the cached production image — no network, tini as PID 1, this repo's app over /app.
# usage: drun.sh JTO SCRIPT [args...]   (JTO "-" = leave JAVA_TOOL_OPTIONS unset)
# The measurement (2026-10-02) ran on round07 at 5ca8b68, before ODL_JAVA_MAX_HEAP existed. Later code adds -Xmx from
# that setting (default 3g) — ODL_JAVA_MAX_HEAP is blanked here so JTO alone sets the heap, as in the measurement.
B="$(cd "$(dirname "$0")" && pwd)"
APP="$(cd "$B/../../app" && pwd)"
JTO="$1"; shift
EA=()
if [ "$JTO" != "-" ]; then EA=(-e "JAVA_TOOL_OPTIONS=$JTO"); fi
MSYS_NO_PATHCONV=1 exec docker run --rm --pull never --network none --init -w /app "${EA[@]}" \
  -e ODL_JAVA_MAX_HEAP= -e IS_DOCKER=true -e PYTHONUNBUFFERED=1 -e PYTHONPATH=/app \
  -v "$APP:/app:ro" -v "D:/SKOVIX/KCI/pdf:/pdf:ro" -v "$B:/w" \
  --entrypoint python landsoftdocker/nl-lib-fastapi:latest "$@"
