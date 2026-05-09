# 비디오유즈 — Claude Code 진입 컨텍스트

이 repo는 **두 모드 영상 파이프라인**입니다. 자세한 흐름은 [README.md](README.md), [USAGE.md](USAGE.md), [.claude/skills/motion-pipeline/SKILL.md](.claude/skills/motion-pipeline/SKILL.md)에 있습니다.

## 첫 진입 시 자동 점검

사용자가 작업을 요청하기 전에:

1. `~/Developer/video-use` 가 존재하지 않으면 → "셋업이 필요합니다. `bash scripts/setup.sh` 를 실행해 주세요" 안내.
2. `.claude/skills/video-use` 심볼릭이 깨졌으면 → setup.sh 재실행 권장.
3. `~/Developer/video-use/.venv/bin/python -c "import edge_tts"` 실패하면 → setup.sh 재실행.

setup.sh는 멱등이라 여러 번 실행해도 안전합니다.

## 두 모드 트리거

| 사용자 요청 패턴                                     | 모드  | 트리거                                        |
| ---------------------------------------------------- | ----- | --------------------------------------------- |
| "footage 영상 편집…" / 영상 파일이 `footage/`에 있음 | **A** | motion-pipeline 스킬 → video-use 흐름         |
| "이 스크립트로 영상 만들어줘" / 텍스트만 있음        | **B** | motion-pipeline 스킬 → Edge TTS + hyperframes |

## 핵심 컨벤션

- **풋티지 위치**: `footage/` (사용자가 다른 경로 지정 가능). 출력은 `<dir>/edit/`.
- **모션그래픽**: `hyperframes/<segment-id>/`에 segment마다 또는 컴포지션 단위로.
- **EDL이 정전(canonical)**: 모든 편집 결정은 `footage/edit/edl.json`에 기록. ffmpeg 합성과 FCPXML 둘 다 여기서 파생.
- **Dual deliverable**: `final.mp4` + `timeline.fcpxml` 두 산출물 항상 생성.
- **Hard Rules**: video-use SKILL.md의 12가지 규칙은 비협상. 자주 깨지는 것:
  - 자막은 필터 체인 마지막
  - per-segment extract → `-c copy` concat
  - 컷 경계마다 30ms `afade`
  - 오버레이는 `setpts=PTS-STARTPTS+T/TB`
  - word-level verbatim ASR만
  - 컷 전 사용자 평문 확인

## 비용

기본 워크플로우는 **API 키 0개, 비용 0**:

- hyperframes Whisper(`npx hyperframes transcribe`) — 로컬, 무료
- Edge TTS — Microsoft 공개, 무료
- ffmpeg — 로컬

ElevenLabs Scribe는 **다중 화자 분리 / 한국어 필러 자동컷이 핵심**일 때만 선택. `~/Developer/video-use/.env` 에 키 입력.

## 자주 묻는 패턴

### 사용자가 영상을 첨부하고 싶어할 때

이 repo는 채팅 첨부 기능이 없습니다. 다음 중 하나를 안내:

- `cp /path/to/video.mp4 footage/` 로 복사
- finder에서 `footage/` 폴더에 드래그
- 절대경로를 채팅에 알려주면 그 경로 그대로 처리

### 사용자가 스크립트를 채팅에 붙여넣을 때

`footage/edit/segments.json`을 자동 생성. 보이스/rate/pitch는 사용자 요청에 맞게 추론. 한국어가 기본은 `ko-KR-SunHiNeural`.

### 첫 transcribe가 멈춘 것처럼 보일 때

hyperframes Whisper large-v3 모델(~3GB) 첫 다운로드 중. 5–15분 정도 걸림. 진행 표시 없을 수 있음 — 사용자에게 미리 알려주기.

## 외부 의존 (받는 사람이 사전 설치 필요)

- macOS 권장 (M-series Apple Silicon이면 더 빠름). Linux도 동작.
- Node 22+, Python 3.10+, uv, ffmpeg, git
- Claude Code (또는 호환 에이전트)

부족하면 setup.sh 실행 시 step 0에서 `missing: <도구>` 에러로 알려줌.
