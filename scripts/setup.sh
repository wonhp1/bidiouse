#!/usr/bin/env bash
# 비디오유즈 파이프라인 셋업 스크립트
#
# 무엇을 하나:
#   1. video-use를 ~/Developer/video-use 에 clone (없으면)
#   2. video-use uv venv 동기화 + edge-tts 추가 (Mode B 내레이션용)
#   3. 프로젝트 로컬에 .claude/skills/video-use 심볼릭 생성
#   4. footage/, hyperframes/ 디렉토리 정리
#   5. 도구 동작 확인 (ffmpeg, hyperframes transcribe, edge-tts, batch_tts)
#
# 멱등(idempotent) — 여러 번 실행해도 안전.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VIDEO_USE_DIR="${VIDEO_USE_DIR:-$HOME/Developer/video-use}"

c_green=$'\033[0;32m'
c_yellow=$'\033[0;33m'
c_red=$'\033[0;31m'
c_reset=$'\033[0m'

ok()    { echo "${c_green}✓${c_reset} $*"; }
warn()  { echo "${c_yellow}!${c_reset} $*"; }
fail()  { echo "${c_red}✗${c_reset} $*" >&2; exit 1; }
step()  { echo; echo "── $* ──"; }

require() { command -v "$1" >/dev/null 2>&1 || fail "필수 도구 없음: $1"; }

# ─────────────────────────────────────────────────────────────
step "0. 사전 요구사항 확인"
# ─────────────────────────────────────────────────────────────
require git
require uv
require node
require npx
require ffmpeg

NODE_MAJOR=$(node -p "process.versions.node.split('.')[0]")
[ "$NODE_MAJOR" -ge 22 ] || fail "Node 22+ 필요 (현재 $(node -v)). nvm/volta로 업그레이드 필요"
ok "git, uv, node $(node -v), ffmpeg $(ffmpeg -version | head -1 | awk '{print $3}')"

# ─────────────────────────────────────────────────────────────
step "1. video-use clone / 업데이트"
# ─────────────────────────────────────────────────────────────
if [ ! -d "$VIDEO_USE_DIR/.git" ]; then
  mkdir -p "$(dirname "$VIDEO_USE_DIR")"
  git clone https://github.com/browser-use/video-use "$VIDEO_USE_DIR"
  ok "clone 완료 → $VIDEO_USE_DIR"
else
  ok "이미 존재 → $VIDEO_USE_DIR"
fi

# ─────────────────────────────────────────────────────────────
step "2. video-use 의존성 (uv sync)"
# ─────────────────────────────────────────────────────────────
(cd "$VIDEO_USE_DIR" && uv sync) >/dev/null
ok "uv sync 완료"

# ─────────────────────────────────────────────────────────────
step "3. Edge TTS를 video-use venv에 추가 (Mode B 내레이션)"
# ─────────────────────────────────────────────────────────────
(cd "$VIDEO_USE_DIR" && \
  uv pip install -r "$REPO_ROOT/.claude/skills/motion-pipeline/helpers/requirements.txt" >/dev/null)
ok "edge-tts 설치 완료"

# ─────────────────────────────────────────────────────────────
step "4. .env 템플릿 (ElevenLabs Scribe 선택사항)"
# ─────────────────────────────────────────────────────────────
if [ ! -f "$VIDEO_USE_DIR/.env" ]; then
  cp "$VIDEO_USE_DIR/.env.example" "$VIDEO_USE_DIR/.env"
  warn "기본 워크플로우는 키 0개. Mode A에서 ElevenLabs Scribe가 필요한 경우만"
  warn "  $VIDEO_USE_DIR/.env 에 ELEVENLABS_API_KEY 입력"
else
  ok ".env 이미 존재"
fi

# ─────────────────────────────────────────────────────────────
step "5. 프로젝트 로컬 심볼릭 (.claude/skills/video-use)"
# ─────────────────────────────────────────────────────────────
mkdir -p "$REPO_ROOT/.claude/skills"
ln -sfn "$VIDEO_USE_DIR" "$REPO_ROOT/.claude/skills/video-use"
ok "$REPO_ROOT/.claude/skills/video-use → $VIDEO_USE_DIR"

# ─────────────────────────────────────────────────────────────
step "6. 디렉토리 구조 (footage/)"
# ─────────────────────────────────────────────────────────────
mkdir -p "$REPO_ROOT/footage"
[ -f "$REPO_ROOT/footage/.gitkeep" ] || touch "$REPO_ROOT/footage/.gitkeep"
ok "$REPO_ROOT/footage/"

# ─────────────────────────────────────────────────────────────
step "7. hyperframes (npx 베이스, lockfile만 점검)"
# ─────────────────────────────────────────────────────────────
if [ -d "$REPO_ROOT/hyperframes" ]; then
  (cd "$REPO_ROOT/hyperframes" && npm install >/dev/null 2>&1) || true
  ok "hyperframes 프로젝트 OK"
else
  warn "hyperframes/ 디렉토리 없음 — 'npx hyperframes init hyperframes ...'로 생성 필요"
fi

# ─────────────────────────────────────────────────────────────
step "8. 동작 검증"
# ─────────────────────────────────────────────────────────────
"$VIDEO_USE_DIR/.venv/bin/python" -c "import edge_tts" 2>/dev/null \
  && ok "edge-tts import OK" \
  || fail "edge-tts import 실패"

"$VIDEO_USE_DIR/.venv/bin/python" \
  "$REPO_ROOT/.claude/skills/motion-pipeline/helpers/batch_tts.py" --help >/dev/null \
  && ok "batch_tts.py 진입점 OK" \
  || fail "batch_tts.py 실행 실패"

"$VIDEO_USE_DIR/.venv/bin/python" \
  "$REPO_ROOT/.claude/skills/motion-pipeline/helpers/edl_to_fcpxml.py" --help >/dev/null \
  && ok "edl_to_fcpxml.py 진입점 OK" \
  || fail "edl_to_fcpxml.py 실행 실패"

# hyperframes transcribe는 첫 호출이 모델 다운로드라 시간 걸림. --help만 확인
npx --yes --offline hyperframes@latest --version >/dev/null 2>&1 \
  && ok "hyperframes CLI OK" \
  || warn "hyperframes CLI 첫 호출 시 인터넷 필요 (npx 캐시 미스)"

# ─────────────────────────────────────────────────────────────
step "셋업 완료"
# ─────────────────────────────────────────────────────────────
cat <<EOF

다음 단계:

  Mode B (스크립트 → 한국어 릴스/숏폼)
    Claude Code 안에서:
      "이 스크립트로 30초 한국어 릴스 만들어줘. SunHi 보이스로."

  Mode A (풋티지 편집)
    1) raw 영상을 footage/ 에 넣기
    2) Claude Code 안에서:
       "footage 영상으로 인터뷰 컷 편집해줘. 자막 + 로어써드."

자세한 사용법은 USAGE.md 참고.
EOF
