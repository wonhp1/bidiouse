# 사용 방법

이 프로젝트는 **두 가지 모드**로 동작합니다. 둘 다 기본은 무료, 키 0개.

| 모드                         | 언제 쓰는가                                    | 입력                  |
| ---------------------------- | ---------------------------------------------- | --------------------- |
| **Mode A — 풋티지 편집**     | 이미 찍은 영상을 자르고 자막/모션그래픽 얹기   | `footage/`에 raw 영상 |
| **Mode B — 스크립트 → 영상** | 텍스트만으로 한국어 릴스/숏폼/설명 영상 만들기 | 스크립트 .md/.txt     |

---

## 처음 한 번만

```bash
bash scripts/setup.sh
```

이게 하는 일: video-use clone, uv sync, edge-tts 설치, 프로젝트 로컬 스킬 심볼릭, footage 디렉토리, 동작 검증. 멱등이라 여러 번 실행해도 안전.

---

## Mode B — 스크립트 → 영상 (가장 자주 쓸 것)

**한국어 릴스/숏폼/설명 영상 자동 생성. 풋티지 0, API 키 0, 비용 0.**

### Step 1 — 스크립트 작성

`footage/edit/segments.json` 또는 markdown 스크립트.

`segments.json` 예시:

```json
{
  "voice": "ko-KR-SunHiNeural",
  "rate": "+10%",
  "segments": [
    {
      "id": "intro",
      "text": "오늘은 한국에서 가장 인기있는 디저트 3가지를 소개합니다."
    },
    {
      "id": "item-1",
      "text": "첫 번째는 흑임자 소프트 아이스크림.",
      "rate": "+5%"
    },
    {
      "id": "item-2",
      "text": "두 번째는 호박 라떼. 따뜻하고 달콤합니다.",
      "pitch": "-2Hz"
    },
    {
      "id": "cta",
      "text": "구독하고 더 많은 영상을 받아보세요!"
    }
  ]
}
```

**보이스 선택지** (모두 무료, Microsoft Edge):

| 보이스                           | 성별 | 특징               |
| -------------------------------- | ---- | ------------------ |
| `ko-KR-SunHiNeural` (기본)       | F    | 친근한 한국어 여성 |
| `ko-KR-InJoonNeural`             | M    | 한국어 남성        |
| `ko-KR-HyunsuMultilingualNeural` | M    | 한+영 혼용 가능    |
| `en-US-AvaMultilingualNeural`    | F    | 한+영 자연스러움   |

톤 조절은 `rate` (+/-%)와 `pitch` (+/-Hz). Edge TTS는 자연어 스타일 디렉팅 미지원.

### Step 2 — Claude Code에서 자연어 요청

```
이 스크립트로 30초 한국어 릴스 만들어줘.
인트로는 큰 타이틀 카드, 각 아이템은 숫자 카운터 + 이모지로 강조해줘.
```

motion-pipeline 스킬이 자동 트리거되어 다음을 수행:

1. `segments.json` 검증
2. **Edge TTS 일괄 내레이션** — `footage/edit/narration/<id>.mp3` 생성
3. **hyperframes Whisper 단어 동기화** — 각 mp3를 `<id>.words.json`으로 트랜스크립션
4. **hyperframes 합성물 작성** — segment마다 `hyperframes/<id>/index.html` (GSAP/CSS 애니메이션, word-level timestamps에 맞춤)
5. **렌더** — 각 segment 합성물을 mov(알파)+mp4 두 포맷으로
6. **EDL 작성** — `footage/edit/edl.json`
7. **ffmpeg concat** — `footage/edit/final.mp4`
8. **EDL → FCPXML** — `footage/edit/timeline.fcpxml` (Final Cut Pro 임포트용)

### Step 3 — 산출물 확인

- `footage/edit/final.mp4` — 완성본
- `footage/edit/timeline.fcpxml` — FCP에서 추가 편집할 때 임포트
- `hyperframes/<id>/index.html` — 각 모션그래픽 소스 (재렌더 가능)

### 수동 명령어 (필요 시)

```bash
# 내레이션만 따로 생성
~/Developer/video-use/.venv/bin/python \
  .claude/skills/motion-pipeline/helpers/batch_tts.py \
  footage/edit/segments.json -o footage/edit/narration/

# 단어 동기화만 따로
for f in footage/edit/narration/*.mp3; do
  npx hyperframes transcribe "$f" --json --language ko --model large-v3 \
    > "${f%.mp3}.words.json"
done

# EDL → FCPXML 변환만
~/Developer/video-use/.venv/bin/python \
  .claude/skills/motion-pipeline/helpers/edl_to_fcpxml.py \
  footage/edit/edl.json -o footage/edit/timeline.fcpxml
```

---

## Mode A — 풋티지 편집

**raw 영상을 컷·자막·모션그래픽으로 다듬기.**

### Step 1 — 영상 배치

```bash
cp /path/to/raw/*.mp4 footage/
```

여러 take를 넣어도 됨. video-use가 알아서 정리.

### Step 2 — Claude Code에서 자연어 요청

```
footage 영상으로 인터뷰 영상 만들어줘.
무음 자동 컷, 자막 번인, 게스트 이름 로어써드 추가.
```

motion-pipeline 스킬이 자동 수행:

1. **트랜스크립션** — `npx hyperframes transcribe <video> --language ko --model large-v3` (무료 로컬 Whisper)
   - ElevenLabs Scribe 사용 시: `~/Developer/video-use/.env`의 `ELEVENLABS_API_KEY` 채우면 자동 폴백
2. **takes_packed.md 생성** — video-use가 트랜스크립트를 phrase 단위로 정리
3. **컷 전략 평문 제시 → 사용자 승인 대기** ⚠️ **이 단계가 핵심.** 자동 진행 안 함.
4. **자동 컷 검출** (사용자 승인 후):
   - 무음 컷: ffmpeg `silencedetect=noise=-30dB:d=0.5`
   - 필러 컷: 한국어 사전(`음/어/그/뭐/이제/근데`) + 영어 사전. ⚠️ **Whisper는 한국어 필러를 자주 누락**해서 매칭률 낮음. 핵심 기능이면 ElevenLabs Scribe 권장.
5. **단어 경계 스냅** — 컷 edge가 단어 안에 떨어지지 않도록 정렬 (Hard Rule 6/7)
6. **모션그래픽 병렬 렌더** — 로어써드/타이틀/트랜지션을 hyperframes 컴포지션으로 sub-agent 병렬 작업
7. **ffmpeg 합성** — segment 추출 → 오버레이 → `-c copy` concat → 30ms afade → 컬러 → **자막은 마지막에 번인** → `final.mp4`
8. **EDL → FCPXML**
9. 자기평가 루프 (최대 3회 fix+재렌더)

### 수동 명령어 (필요 시)

```bash
# 트랜스크립션만 (무료)
npx hyperframes transcribe footage/clip1.mp4 --json --language ko --model large-v3

# 트랜스크립션 (ElevenLabs Scribe — 다중 화자 분리 / 한국어 필러 보존)
~/Developer/video-use/.venv/bin/python \
  ~/Developer/video-use/helpers/transcribe.py footage/clip1.mp4

# 무음 검출만
ffmpeg -nostdin -hide_banner -i footage/clip1.mp4 \
  -af silencedetect=noise=-30dB:d=0.5 -f null -
```

---

## 모션그래픽 컴포지션 직접 작업

`hyperframes/<name>/`에 컴포지션이 들어감. 각 디렉토리는 독립 hyperframes 프로젝트.

```bash
# 새 컴포지션 만들기
cd hyperframes
npx hyperframes init lower-third --example blank --tailwind --resolution 1080p

# 미리보기 (브라우저 라이브 리로드)
cd hyperframes/lower-third
npm run dev

# 검증 (lint + validate + inspect)
npm run check

# 렌더 — mp4
npm run render

# 렌더 — mov 알파(Final Cut Pro용)
npx hyperframes render --format mov --codec prores4444 -o output/lower-third.mov

# 레지스트리 블록 추가 (50+ 사전 제작 컴포넌트)
npx hyperframes catalog
npx hyperframes add lower-third
```

`hyperframes/.agents/skills/`에 깔린 보조 스킬:

- `hyperframes` — 일반 가이드
- `gsap`, `animejs`, `waapi`, `css-animations` — 애니메이션 엔진
- `tailwind` — 스타일
- `lottie`, `three` — 특수
- `remotion-to-hyperframes`, `website-to-hyperframes` — 마이그레이션

Claude Code가 이 스킬들을 자동 활용하므로 사용자가 직접 호출할 필요는 없음.

---

## 자주 묻는 것

### Q. ElevenLabs 정말 안 써도 되나?

**네.** 무음 컷·자막·모션그래픽·내레이션 모두 무료 도구로 됩니다. ElevenLabs를 다시 쓸 가치는 두 경우:

- **다중 화자 인터뷰** — 자동 화자 분리 (hyperframes Whisper에는 없음)
- **한국어 필러 자동컷이 핵심** — Whisper가 "음/어"를 자주 누락

### Q. 한국어 영상이 메인인데 large-v3가 정확한가?

영어 대비 정확도는 약간 낮지만 영상 자막용으로 실용적. 사람이 또렷이 발음하는 일반 영상은 거의 문제 없음. 사투리/은어/전문용어가 많으면 후보정 필요할 수 있음.

### Q. 첫 transcribe가 너무 느려요

hyperframes가 Whisper large-v3 모델(약 3GB)을 처음 한 번 다운로드합니다. 이후 호출은 빠릅니다. M4 Pro에서 1시간 영상은 5–10분 정도.

### Q. FCPXML이 뭐고 왜 필요한가?

Final Cut Pro X가 임포트할 수 있는 타임라인 형식. `final.mp4`로 끝내도 되지만, FCP에서 추가 다듬기를 하고 싶으면 `timeline.fcpxml`을 임포트하면 컷·오버레이·자막이 모두 재현됨. 원본 클립 참조라 비파괴 편집 가능.

### Q. 모션그래픽이 마음에 안 들어요

`hyperframes/<segment-id>/index.html`을 직접 수정하면 됩니다. HTML/CSS/JS라 ChatGPT/Claude에게 "더 화려하게", "색을 빨강으로" 같은 자연어 요청도 통합니다. 수정 후 `npm run render`로 재렌더, EDL은 그대로 둬서 동일 위치/타이밍 유지.

### Q. 셋업 다시 하려면?

```bash
bash scripts/setup.sh
```

멱등이라 안전. video-use 업데이트(`cd ~/Developer/video-use && git pull`) 후에도 다시 실행하면 됩니다.

---

## 트러블슈팅

### `edge-tts` import 실패

```bash
bash scripts/setup.sh   # 이 repo 루트에서 실행 — venv에 edge-tts 복원
```

`git pull` 후에 venv가 초기화되면 자주 발생. setup.sh가 이걸 자동 처리.

### `npx hyperframes transcribe` 첫 호출 시 멈춤

모델 다운로드 중. 진행 표시가 없을 수 있으니 5–15분 기다려봅니다. 한 번 받으면 캐시.

### `ffmpeg silencedetect`가 결과를 안 줌

`-30dB`가 너무 엄격할 수 있음. `-40dB`로 낮춰보거나 `d=0.3`으로 짧은 무음도 허용.

### hyperframes 렌더가 메모리 부족

`hyperframes doctor` 실행. M4 Pro 24GB라도 다른 앱이 점유하면 부족. Chrome/IDE 닫고 재시도.

### 컷이 단어 중간에 떨어짐

video-use Hard Rule 6/7 (단어 경계 스냅)이 적용 안 됐을 수 있음. 트랜스크립트가 비어있거나 `.words.json`이 없으면 발생. 먼저 transcribe부터 재실행.
