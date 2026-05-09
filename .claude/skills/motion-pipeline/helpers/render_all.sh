#!/usr/bin/env bash
# render_all.sh — render all segment compositions in parallel.
# Output goes to compositions/<id>/output.mp4 (predictable path for EDL).
#
# Usage:  ./render_all.sh [parallelism]
#         default parallelism = 4

set -u
cd "$(dirname "$0")/../../../.."  # → project root

PARALLEL="${1:-4}"
COMPOSITIONS=(compositions/*/)
SEGMENTS=()
for d in "${COMPOSITIONS[@]}"; do
  name="$(basename "$d")"
  [[ "$name" == _template ]] && continue
  SEGMENTS+=("$name")
done

echo "rendering ${#SEGMENTS[@]} compositions, parallelism=$PARALLEL"
mkdir -p logs

render_one() {
  local id="$1"
  local logfile="logs/render-${id}.log"
  local started=$(date +%s)
  cd "compositions/${id}" || return 1
  if npx hyperframes render -o "output.mp4" > "../../${logfile}" 2>&1; then
    local elapsed=$(( $(date +%s) - started ))
    local size=$(ls -lh output.mp4 2>/dev/null | awk '{print $5}')
    printf "  ✓ %-18s  %4ds  %s\n" "$id" "$elapsed" "${size:-?}"
  else
    printf "  ✗ %-18s  FAILED  (see %s)\n" "$id" "${logfile}"
  fi
}

export -f render_one
printf '%s\n' "${SEGMENTS[@]}" | xargs -I {} -P "$PARALLEL" bash -c 'render_one "$@"' _ {}

echo "✅ all renders complete"
ls -la compositions/*/output.mp4 2>/dev/null | wc -l | xargs -I {} echo "  {} mp4 files produced"
