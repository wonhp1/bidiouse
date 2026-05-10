#!/usr/bin/env bash
# EDL → 양 NLE 파일 동시 export
#
# 어느 모드(A: 풋티지 편집 / B: 스크립트→영상)를 돌렸든 EDL이 만들어진 후 마지막 단계.
# 같은 EDL을 두 NLE가 받는 형식으로 내보낸다.
#
#   footage/edit/timeline.fcpxml  ← Final Cut Pro
#   footage/edit/timeline.xml     ← Premiere Pro (FCP7 XML)
#
# 자막 인포그래픽 mov가 EDL의 overlays에 등록되어 있으면 양 NLE 파일 모두에
# V2 lane(connected clip / V2 track) 형태로 자동 포함된다.
#
# 사용:
#   bash scripts/export_nle_files.sh                   # 기본 footage/edit/edl.json
#   bash scripts/export_nle_files.sh path/to/edl.json  # 다른 EDL 지정

set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="$HOME/Developer/video-use/.venv/bin/python"
HELPERS="$REPO/.claude/skills/motion-pipeline/helpers"

EDL="${1:-$REPO/footage/edit/edl.json}"
EDIT_DIR="$(dirname "$EDL")"

ok()   { printf '\033[0;32m✓\033[0m %s\n' "$*"; }
fail() { printf '\033[0;31m✗\033[0m %s\n' "$*" >&2; exit 1; }

[ -f "$EDL" ] || fail "EDL 없음: $EDL"

echo "── EDL → 양 NLE 파일 export ──"
echo "  EDL:      $EDL"
echo "  output:   $EDIT_DIR/{timeline.fcpxml, timeline.xml}"
echo

"$VENV" "$HELPERS/edl_to_fcpxml.py" "$EDL" -o "$EDIT_DIR/timeline.fcpxml" \
  && ok "$EDIT_DIR/timeline.fcpxml (Final Cut Pro)" \
  || fail "FCPXML 생성 실패"

"$VENV" "$HELPERS/edl_to_fcp7_xml.py" "$EDL" -o "$EDIT_DIR/timeline.xml" \
  && ok "$EDIT_DIR/timeline.xml (Premiere Pro, FCP7 XML)" \
  || fail "FCP7 XML 생성 실패"

echo
echo "다음 단계:"
echo "  • Final Cut Pro: timeline.fcpxml 임포트 → 컷 + 자막 overlay 자동 포함"
echo "  • Premiere Pro:  timeline.xml 임포트  → 컷 + 자막 overlay 자동 포함"
echo "                    필요시 Captions 패널에서 subtitles.srt 별도 import"
