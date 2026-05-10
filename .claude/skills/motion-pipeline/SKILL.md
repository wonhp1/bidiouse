---
name: motion-pipeline
description: video-use(컷 편집·자막·컬러)와 hyperframes(HTML→비디오 모션그래픽)를 결합한 두 모드 파이프라인. Mode A는 raw 풋티지를 편집(트랜스크립트 기반 컷·컬러·자막), Mode B는 스크립트에서 영상을 생성(Edge TTS 내레이션 + hyperframes 모션그래픽, 풋티지 없음). 두 모드 모두 NLE 양쪽 export(timeline.fcpxml + timeline.xml — Final Cut Pro와 Premiere Pro 둘 다 호환) + final.mp4. 사용자가 "이 영상 편집해줘", "타이틀/로어써드 추가", "스크립트로 한국어 릴스/숏폼 만들기" 요청하면 트리거. 기본은 무료 워크플로우(hyperframes Whisper + Edge TTS), ElevenLabs Scribe는 선택사항(다중 화자 또는 한국어 필러 자동컷이 핵심일 때만).
---

# Motion Pipeline (video-use × hyperframes)

이 스킬은 두 도구를 결합한다:

- **video-use** — `.claude/skills/video-use` (`~/Developer/video-use`로 심볼릭). 트랜스크립트 기반 컷, ffmpeg 합성, 자막 번인. Hard Rules는 video-use의 [SKILL.md](../video-use/SKILL.md)에 있음 — 그게 진리다.
- **hyperframes** — `./hyperframes/`. HTML/CSS/GSAP/Lottie/Three.js 합성물 → 결정론적 mp4/mov 렌더. 추가로 `transcribe`(로컬 Whisper) 서브커맨드 내장.

video-use SKILL.md의 Hard Rules는 **무조건** 따른다. 이 파일은 두 도구의 결합 방식과 프로젝트 컨벤션만 다룬다.

## 두 운영 모드

| 모드                  | 트리거                  | 입력        | TTS                                           | ASR                                                             | 비용                     |
| --------------------- | ----------------------- | ----------- | --------------------------------------------- | --------------------------------------------------------------- | ------------------------ |
| **A — 풋티지 편집**   | `./footage/`에 raw 영상 | 비디오 파일 | n/a                                           | hyperframes Whisper(기본·무료) **또는** ElevenLabs Scribe(선택) | $0 / Scribe 시 ~$0.40/hr |
| **B — 스크립트→영상** | 스크립트 .md/.txt 지정  | 텍스트      | **Edge TTS** (무료, `ko-KR-SunHiNeural` 기본) | hyperframes Whisper (단어 동기화용)                             | **$0**                   |

## 책임 분담

| 영역                                      | 담당                                                             |
| ----------------------------------------- | ---------------------------------------------------------------- |
| 트랜스크립션 (Mode A)                     | **hyperframes Whisper(무료, 기본)** 또는 ElevenLabs Scribe(선택) |
| 내레이션 생성 (Mode B)                    | **Edge TTS** (무료, API 키 불필요)                               |
| 단어 단위 동기화 (Mode B)                 | `npx hyperframes transcribe` (Whisper 로컬)                      |
| 컷 결정 / EDL / 필러 제거 (Mode A)        | video-use                                                        |
| 무음 구간 컷 검출                         | **ffmpeg `silencedetect`** (ASR 무관, 완전 무료)                 |
| 컬러 / 오디오 페이드 / 자막 번인 / concat | video-use (ffmpeg)                                               |
| 모션그래픽 오버레이                       | hyperframes                                                      |
| 최종 합성                                 | video-use (ffmpeg가 hyperframes mp4/mov 오버레이)                |

## 프로젝트 컨벤션

- **풋티지 위치**: `./footage/` (사용자가 원하는 경로 지정 OK). 출력은 `<videos_dir>/edit/`.
- **hyperframes 합성물 위치**: `./hyperframes/<composition-name>/`. 새 컴포지션은 `cd hyperframes && npx hyperframes init <name>`.
- **오버레이 포맷**: ProRes 4444 .mov(알파 보존, FCP용) **+** mp4(ffmpeg 번인용) 둘 다 렌더.
- **Triple deliverable**: 매 실행마다 세 산출물.
  1. `./footage/edit/final.mp4` — 완성본 (자막 번인 + 컬러 합성)
  2. `./footage/edit/timeline.fcpxml` — Final Cut Pro 임포트용 (컷 + 자막 V2 overlay)
  3. `./footage/edit/timeline.xml` — Premiere Pro 임포트용 (FCP7 XML, 컷 + 자막 V2 overlay)

  EDL 작성 후 양 NLE 파일은 **단일 명령으로 동시 export**:

  ```bash
  bash scripts/export_nle_files.sh
  ```

## Mode A — 풋티지 편집

1. 사용자가 `./footage/`에 클립을 넣는다.
2. **트랜스크립션**: 기본 `npx hyperframes transcribe <file> --json --language ko --model large-v3` 사용. ElevenLabs Scribe가 필요하면 `~/Developer/video-use/.env`의 `ELEVENLABS_API_KEY` 채우고 `~/Developer/video-use/.venv/bin/python ~/Developer/video-use/helpers/transcribe.py <file>`. **Whisper 출력을 Scribe 호환 JSON 형식(words[].{type,text,start,end,speaker_id})으로 어댑트해서** video-use helpers에 입력.
3. video-use가 `takes_packed.md`를 만들고 컷 전략을 평문으로 제시 → **사용자 승인 대기**.
4. 모션그래픽 오버레이를 병렬 sub-agent로 렌더 (아래 [모션그래픽](#모션그래픽-공통) 참조).
5. `./footage/edit/edl.json` 작성.
6. video-use가 segment-단위 ffmpeg extract → 오버레이 합성 → `-c copy` concat → 30ms 오디오 페이드 → 컬러 → **자막은 마지막**에 번인 → `final.mp4`.
7. EDL → 양 NLE 파일 export (`bash scripts/export_nle_files.sh`) → `timeline.fcpxml` + `timeline.xml`.
8. 자기평가 루프, 최대 3회 fix+재렌더.

### 무음 컷 (Mode A 핵심 — ASR 무관)

ffmpeg `silencedetect`만으로 처리. Whisper/ElevenLabs와 무관하게 동작:

```bash
ffmpeg -nostdin -hide_banner -i <audio> \
  -af silencedetect=noise=-30dB:d=0.5 \
  -f null -
```

stderr의 `silence_start: X.XXX` / `silence_end: Y.YYY | silence_duration: Z.ZZZ` 라인을 정규식 파싱 → `SilenceRange[]` → wordSnap으로 단어 경계 정렬 → CutSuggestion → 사용자 승인 → EDL의 keep-range로 변환.

### Source 영상 사전 점검 (Mode A FCPXML 산출 시 필수)

EDL → FCPXML 단계는 **세 가지 source 메타데이터에 민감**하다. Mode A 시작 시 자동 점검:

1. **NTSC frame rate** — `ffprobe -show_entries stream=r_frame_rate`. 30000/1001(29.97), 24000/1001(23.976), 60000/1001(59.94)면 EDL에 `fps_num`/`fps_den`을 명시 (helper의 `parse_fps`가 자동 인식하지만 명시가 안전).

2. **한글 경로** — macOS는 NFD로 저장. helper가 NFC로 자동 normalize하지만, FCP가 그래도 거부하면 영문 임시 경로로 사본:

   ```bash
   mkdir -p /tmp/bidiouse && cp footage/한글영상.MP4 /tmp/bidiouse/source.MP4
   # EDL의 sources[0].path를 /tmp/bidiouse/source.MP4로 갱신
   ```

3. **timecode 메타데이터** — DJI/GoPro/일부 카메라는 0이 아닌 timecode(`07:26:28;00` 등)를 박음. FCP가 source 좌표계로 해석하면 우리 0초 기준 EDL과 mismatch:
   ```bash
   ffprobe -v error -show_entries stream_tags=timecode \
     -of default=noprint_wrappers=1 footage/원본.MP4
   ```
   `00:00:00:00`이 아니면 strip:
   ```bash
   ffmpeg -y -i footage/원본.MP4 -c copy -map_metadata -1 \
     -timecode 00:00:00:00 /tmp/bidiouse/source.MP4
   # EDL path 갱신
   ```
   stream copy라 영상 픽셀은 무손실, 1분 내 완료.

이 세 점검을 EDL 작성 **전**에 한 번 돌리면 FCPXML 재시도 횟수가 크게 줄어든다.

## Mode B — 스크립트 → 영상 (한국어 릴스/숏폼 기본 흐름)

**풋티지 0, API 키 0.** Edge TTS 내레이션, Whisper 단어 타임스탬프, hyperframes 비주얼.

### 입력

`{id, text, voice?, rate?, pitch?}` 구조의 segments. 스크립트 .md/.txt를 segments.json으로 변환.

```json
{
  "voice": "ko-KR-SunHiNeural",
  "rate": "+15%",
  "segments": [
    { "id": "intro", "text": "안녕하세요, 오늘은..." },
    {
      "id": "body-1",
      "text": "첫 번째 포인트는...",
      "rate": "+5%",
      "pitch": "-3Hz"
    },
    { "id": "cta", "text": "더 알고 싶으면..." }
  ]
}
```

per-segment 오버라이드가 top-level 기본값보다 우선.

### 흐름

1. **스크립트 파싱** → `./footage/edit/segments.json`.
2. **Edge TTS 내레이션 일괄 생성** (병렬):
   ```bash
   ~/Developer/video-use/.venv/bin/python \
     .claude/skills/motion-pipeline/helpers/batch_tts.py \
     ./footage/edit/segments.json \
     -o ./footage/edit/narration/
   ```
   `<id>.mp3` per segment + `manifest.json`(측정된 길이) 출력.
3. **각 mp3를 단어 단위로 transcribe** (비주얼 동기화용):
   ```bash
   for f in footage/edit/narration/*.mp3; do
     npx hyperframes transcribe "$f" --json --language ko \
       --model large-v3 > "${f%.mp3}.words.json"
   done
   ```
4. **hyperframes 합성물 병렬 작성** — segment마다 또는 Set 단위로 하나씩. 각 sub-agent(Agent tool, `general-purpose`):
   - `cd hyperframes/<segment-id> && npx hyperframes init` (최초 1회)
   - `index.html`을 GSAP/CSS 애니메이션으로 작성 — **3단계의 word-level timestamps에 맞춰** 등장/소멸 타이밍 결정
   - 두 포맷 모두 렌더: `--format mov --codec prores4444 -o output/<id>.mov`(FCP 알파) + `-o output/<id>.mp4`(ffmpeg 번인용)
5. **`./footage/edit/edl.json`** 작성 — segment별 mp3가 source, hyperframes 렌더가 overlay(전체 segment 길이를 덮음).
6. **ffmpeg concat**으로 모든 segment 렌더 → `final.mp4`. 오디오는 내레이션 mp3들을 순서대로.
7. EDL → 양 NLE 파일 export (`bash scripts/export_nle_files.sh`) → `timeline.fcpxml` + `timeline.xml`.

### Edge TTS 보이스 치트시트 (한국어 우선)

| 보이스                           | 성별 | 노트                                          |
| -------------------------------- | ---- | --------------------------------------------- |
| `ko-KR-SunHiNeural`              | F    | **기본**. 한국어 여성, 친근/긍정              |
| `ko-KR-InJoonNeural`             | M    | 한국어 남성, 친근                             |
| `ko-KR-HyunsuMultilingualNeural` | M    | 한국어 남성 + 문장 중간 영어 발음 가능        |
| `en-US-AvaMultilingualNeural`    | F    | 한+영 자연스럽게. 외래어 많은 스크립트에 좋음 |
| `en-US-AndrewMultilingualNeural` | M    | 위와 동일, 남성                               |

톤 변화는 `--rate "+15%"`(빠르게/설명체), `--rate "-10%"`(느리게/사색조), `--pitch "-3Hz"`(낮게/Bridge용). Edge TTS는 자연어 스타일 디렉팅 미지원 → rate/pitch에 베이크.

## 자막 수정 워크플로우 (Mode A/B 모두 — 옵션 1 정착 흐름)

자막은 hyperframes 인포그래픽 mov(영상)이라 영상 내부 텍스트 직접 수정 불가. **단일 source of truth = `footage/edit/subtitles.srt`**, 명령 한 줄로 양 NLE 파일까지 자동 갱신.

### 사용자가 자막 수정을 요청할 때 자동 흐름

사용자 요청 패턴:

- "자막 텍스트 수정해줘"
- "5번 자막을 'XX'로 바꿔줘"
- "자막 'YY' 부분 다시 만들어줘"
- "자막에 오타 있어"

→ **이 워크플로우를 자동 트리거**:

```
1. footage/edit/subtitles.srt 가 있으면 그대로 사용,
   없으면 helpers/subtitles_to_srt.py 로 subtitles.json → SRT 먼저 export
2. 사용자 요청 반영 (SRT 수정)
3. bash scripts/rerender_subtitles.sh 실행
   → SRT → JSON → index.html → 4K alpha mov 렌더 (5–15분)
   → cut별 mov 분할 → EDL overlays 갱신
   → timeline.fcpxml + timeline.xml 동시 export
4. 완료 후 사용자에게 "NLE에서 timeline.{fcpxml|xml} 다시 import" 안내
```

검증만 빠르게 (렌더 안 함, 5초): `bash scripts/rerender_subtitles.sh --lint-only`

### 디자인 자체 변경 (CSS 수정)

자막 폰트/색/박스 스타일/모션을 바꾸려면 [helpers/build_subtitle_html.py](helpers/build_subtitle_html.py)의 `TEMPLATE` CSS를 수정. 매 재렌더 시 그 템플릿이 `hyperframes/index.html`을 덮어쓴다.

수정 후 동일하게 `bash scripts/rerender_subtitles.sh` — 새 디자인 적용된 mov가 양 NLE 파일에 자동 반영.

### Hard Rules (자막 워크플로우 한정)

1. **subtitles.srt가 single source of truth** — JSON / index.html / mov는 모두 SRT에서 파생. 사용자가 SRT만 편집한다.
2. **rerender_subtitles.sh가 진입점** — 개별 helper를 직접 호출하지 말고 항상 이 스크립트 사용 (6단계 + 양 NLE export 보장).
3. **변경마다 양 NLE 파일 갱신** — Mode 무관, 자막이 바뀌면 timeline.fcpxml + timeline.xml 모두 신선해야 한다.
4. **편집 영상과 자막은 미리 합성하지 않는다** — 항상 NLE 파일에 V1(영상)+V2(자막 mov) 청사진으로 두고 NLE가 import 시 합성.

## 공통 단계

### 모션그래픽 (공통)

각 오버레이/타이틀/로어써드:

- 병렬 sub-agent (Agent tool, `general-purpose`).
- `cd hyperframes/<name> && npx hyperframes init`(최초) → HTML+CSS+GSAP 작성 → 두 포맷 렌더:
  - `npx hyperframes render --format mov --codec prores4444 -o output/<name>.mov` (알파, FCP)
  - `npx hyperframes render -o output/<name>.mp4` (ffmpeg 번인)
- 사용 스킬: `hyperframes`(일반), `gsap`/`waapi`(애니메이션), `tailwind`(스타일), `lottie`/`three`(특수). 모두 `./hyperframes/.agents/skills/`에 깔려 있음.

### EDL → 양 NLE 파일 (FCP + Premiere)

매 iteration의 마지막 단계. **단일 명령으로 두 NLE 파일 동시 export**:

```bash
bash scripts/export_nle_files.sh
```

내부 동작:

```
edl.json  ─┬─→ edl_to_fcpxml.py    → footage/edit/timeline.fcpxml  (Final Cut Pro)
           └─→ edl_to_fcp7_xml.py  → footage/edit/timeline.xml     (Premiere Pro, FCP7 XML)
```

두 파일 모두 EDL의 cuts(V1) + overlays(V2 자막 mov) + sources를 동일하게 표현. 어느 NLE 사용자든 동일한 작업물 받음.

매 iteration마다 edl.json을 다시 emit하고 위 스크립트 재실행 — mp4와 양 NLE 파일이 항상 동기.

#### NLE별 임포트 가이드

| NLE               | 임포트                                  | 자막                                       |
| ----------------- | --------------------------------------- | ------------------------------------------ |
| **Final Cut Pro** | File → Import → XML → `timeline.fcpxml` | 자막 mov가 V2 connected clip으로 자동 포함 |
| **Premiere Pro**  | File → Import → `timeline.xml`          | 자막 mov가 V2 트랙으로 자동 포함           |

ProRes 4444 알파라 양 NLE 모두 자막 배경 자동 인식.

## EDL 스키마

`./footage/edit/edl.json` — 모든 편집 결정의 정전(canonical record). ffmpeg 합성과 FCPXML 둘 다 여기서 파생.

```json
{
  "name": "프로젝트명",
  "fps": 30,
  "width": 1920,
  "height": 1080,
  "sources": [
    {
      "id": "s1",
      "path": "/abs/clip1.mov",
      "duration": 120.5,
      "name": "take1",
      "has_audio": true
    }
  ],
  "cuts": [{ "source_id": "s1", "in": 12.34, "out": 18.56, "name": "intro" }],
  "overlays": [
    {
      "path": "/abs/lower-third.mov",
      "start": 5.0,
      "duration": 3.0,
      "lane": 1,
      "name": "lower-third"
    }
  ],
  "subtitles": [{ "start": 0.5, "end": 2.0, "text": "안녕하세요" }]
}
```

- `cuts[].in/out` — **소스** 클립 내부 타임스탬프
- `overlays[].start/duration` — **출력 타임라인** 타임스탬프 (cuts concat 후 기준)
- `subtitles[].start/end` — 출력 타임라인 타임스탬프
- 모든 path는 절대경로. 오버레이는 가능하면 ProRes 4444 .mov로 (FCP가 알파 받음).

워크된 예시: [examples/edl.example.json](examples/edl.example.json).

## Hard Rules (video-use에서 상속, 비협상)

[.claude/skills/video-use/SKILL.md](../video-use/SKILL.md)의 12 Hard Rules가 무조건. 자주 깨지는 것들:

- 자막은 필터 체인 **마지막** (모든 오버레이 다음)
- per-segment extract → `-c copy` concat (단일 패스 filtergraph 금지)
- 컷 경계마다 30ms `afade`
- 오버레이는 `setpts=PTS-STARTPTS+T/TB`
- word-level verbatim ASR만 (SRT/phrase 모드 금지)
- 컷 전 사용자 평문 확인

## CLI 치트시트

```bash
# hyperframes (Node 22+, Chrome, ffmpeg 필요)
npx hyperframes init <name>
cd hyperframes && npm run dev      # preview
npx hyperframes render             # mp4
npx hyperframes render --format mov --codec prores4444 -o output/<name>.mov  # FCP 알파
npx hyperframes transcribe <file> --json --language ko --model large-v3       # 로컬 Whisper
npx hyperframes add <block>        # 레지스트리 블록 (lower-third 등) 설치
npx hyperframes catalog            # 50+ 블록 브라우즈
npx hyperframes doctor             # 환경 체크

# Mode B — Edge TTS 일괄 내레이션 (무료, 키 불필요)
~/Developer/video-use/.venv/bin/python \
  .claude/skills/motion-pipeline/helpers/batch_tts.py segments.json -o narration/

# Mode A — ElevenLabs Scribe (옵션, .env에 ELEVENLABS_API_KEY 필요)
~/Developer/video-use/.venv/bin/python ~/Developer/video-use/helpers/transcribe.py <file>
~/Developer/video-use/.venv/bin/python ~/Developer/video-use/helpers/timeline_view.py <file>

# EDL → 양 NLE 파일 (양 모드, 단일 명령)
bash scripts/export_nle_files.sh
#   → footage/edit/timeline.fcpxml  (Final Cut Pro)
#   → footage/edit/timeline.xml     (Premiere Pro, FCP7 XML)

# 개별 helper 호출 (필요 시)
~/Developer/video-use/.venv/bin/python \
  .claude/skills/motion-pipeline/helpers/edl_to_fcpxml.py edl.json -o timeline.fcpxml
~/Developer/video-use/.venv/bin/python \
  .claude/skills/motion-pipeline/helpers/edl_to_fcp7_xml.py edl.json -o timeline.xml
```

## 환경변수

**Mode B는 키 0개.** Edge TTS와 hyperframes Whisper 모두 무료, 키 불필요.

`ELEVENLABS_API_KEY`는 **Mode A에서 Scribe를 명시적으로 선택할 때만** 필요. `~/Developer/video-use/.env`에 설정.

## 셋업 (이 repo는 이미 완료)

1. `brew install ffmpeg uv git-lfs yt-dlp`
2. `git clone https://github.com/browser-use/video-use ~/Developer/video-use`
3. `cd ~/Developer/video-use && uv sync`
4. `cd ~/Developer/video-use && uv pip install -r /path/to/repo/.claude/skills/motion-pipeline/helpers/requirements.txt` — edge-tts를 video-use venv에 추가
5. `ln -sfn ~/Developer/video-use .claude/skills/video-use` — 프로젝트 로컬 스킬 등록
6. `cd hyperframes && npm install` (npx 베이스라 의존성은 거의 없음, package-lock만 잡음)
7. (Optional, Mode A Scribe) `~/Developer/video-use/.env`에 `ELEVENLABS_API_KEY=...`

`git pull` 후 `~/Developer/video-use/`에서 step 4 재실행 — venv에 edge-tts 복원.
