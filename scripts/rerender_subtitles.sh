#!/usr/bin/env bash
# 자막 재렌더 워크플로우 (옵션 1)
#
# 흐름:
#   1. footage/edit/subtitles.srt → subtitles.json (텍스트 갱신)
#   2. subtitles.json → hyperframes/index.html (caption clip 재생성)
#   3. lint + render → hyperframes/renders/subtitles.mov (4K alpha)
#   4. mov를 cut별로 분할 → hyperframes/renders/cuts/
#   5. EDL의 overlays 갱신
#   6. 양 NLE 파일 재생성 → timeline.fcpxml + timeline.xml
#
# 텍스트만 바꾸고 디자인은 그대로. SRT 시간 코드는 변경 가능 (자막 타이밍 조정용).
#
# 사용:
#   bash scripts/rerender_subtitles.sh
#
# 변경한 파일을 미리 확인 (lint만):
#   bash scripts/rerender_subtitles.sh --lint-only

set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="$HOME/Developer/video-use/.venv/bin/python"
LINT_ONLY=0
[ "${1:-}" = "--lint-only" ] && LINT_ONLY=1

step() { echo; echo "── $* ──"; }
ok() { echo "✓ $*"; }
fail() { echo "✗ $*" >&2; exit 1; }

[ -f "$REPO/footage/edit/edl.json" ] || fail "footage/edit/edl.json 없음. 컷편집 EDL이 있어야 함"

# SRT가 없으면 subtitles.json에서 자동 export (첫 사용 시)
if [ ! -f "$REPO/footage/edit/subtitles.srt" ]; then
  if [ -f "$REPO/footage/edit/subtitles.json" ]; then
    step "0. subtitles.srt 자동 export (subtitles.json → SRT)"
    "$VENV" "$REPO/.claude/skills/motion-pipeline/helpers/subtitles_to_srt.py" \
      export "$REPO/footage/edit/subtitles.json" \
      -o "$REPO/footage/edit/subtitles.srt"
    ok "footage/edit/subtitles.srt 생성됨 — 편집 후 다시 실행하세요"
    exit 0
  else
    fail "subtitles.srt 와 subtitles.json 둘 다 없음. 먼저 transcribe 필요"
  fi
fi

step "1. SRT → subtitles.json"
"$VENV" "$REPO/.claude/skills/motion-pipeline/helpers/subtitles_to_srt.py" \
  import "$REPO/footage/edit/subtitles.srt" \
  -o "$REPO/footage/edit/subtitles.json"

step "2. subtitles.json → hyperframes/index.html"
"$VENV" "$REPO/.claude/skills/motion-pipeline/helpers/build_subtitle_html.py" \
  "$REPO/footage/edit/subtitles.json" \
  -o "$REPO/hyperframes/index.html"

step "3. hyperframes lint + validate"
(cd "$REPO/hyperframes" && npx --yes hyperframes@0.5.5 lint 2>&1 | tail -3)

if [ "$LINT_ONLY" = "1" ]; then
  ok "lint-only 모드 — 렌더 건너뜀"
  exit 0
fi

step "4. 알파 mov 렌더 (4K, 5–15분 예상)"
mkdir -p "$REPO/hyperframes/renders"
(cd "$REPO/hyperframes" && \
  npx --yes hyperframes@0.5.5 render --format mov \
    -o renders/subtitles.mov --quality high)
ok "$(ls -lh "$REPO/hyperframes/renders/subtitles.mov" | awk '{print $5}') hyperframes/renders/subtitles.mov"

step "5. mov를 16개 cut 별로 분할"
"$VENV" "$REPO/.claude/skills/motion-pipeline/helpers/split_subtitles_by_cuts.py" \
  "$REPO/footage/edit/edl.json" \
  "$REPO/hyperframes/renders/subtitles.mov" \
  -o "$REPO/hyperframes/renders/cuts"

step "5. EDL overlays 갱신"
"$VENV" "$REPO/.claude/skills/motion-pipeline/helpers/update_edl_overlays.py" \
  "$REPO/footage/edit/edl.json" \
  "$REPO/hyperframes/renders/cuts"

step "6. 양 NLE 파일 재생성 (Final Cut Pro + Premiere Pro)"
bash "$REPO/scripts/export_nle_files.sh" "$REPO/footage/edit/edl.json" 2>&1 | grep -E "✓|✗"

echo
ok "완료. 두 NLE 파일이 갱신됨:"
echo "   • footage/edit/timeline.fcpxml — Final Cut Pro"
echo "   • footage/edit/timeline.xml    — Premiere Pro"
echo "  NLE에서 다시 import 하세요."
