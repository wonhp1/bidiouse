# 환경변수 / API 키

## 기본은 키 0개

이 프로젝트의 기본 워크플로우는 외부 API 키가 필요하지 않습니다.

| 도구                                                   | 키 필요? | 비고                                      |
| ------------------------------------------------------ | -------- | ----------------------------------------- |
| **hyperframes Whisper** (`npx hyperframes transcribe`) | ❌       | 로컬 onnxruntime, large-v3까지 무료       |
| **Edge TTS** (Mode B 내레이션)                         | ❌       | Microsoft 공개 서비스, 한국어 보이스 4종+ |
| **ffmpeg** (무음 검출, 합성, 자막)                     | ❌       | 로컬                                      |
| **hyperframes** (모션그래픽 렌더)                      | ❌       | 로컬 Puppeteer + ffmpeg                   |

## 선택사항: ElevenLabs Scribe

다음 둘 중 하나가 **핵심 가치**일 때만 설정하세요:

1. **다중 화자 인터뷰의 자동 화자 분리** — hyperframes Whisper는 화자 분리 미지원. 인터뷰/대담/팟캐스트면 차이가 큽니다.
2. **한국어 필러 자동컷** — Whisper(large-v3 포함)는 한국어 "음/어/그" 같은 짧은 disfluency를 자주 누락합니다. Scribe는 verbatim 모드로 보존합니다. 영상에서 필러 컷이 빈번한 핵심 기능이면 Scribe 우위.

위 두 경우가 아니면 무료 기본 셋업으로 충분합니다.

### 발급

1. https://elevenlabs.io/app/settings/api-keys 에서 발급
2. **무료 티어 한도** — 발급 후 본인 계정 페이지에서 월 STT 할당량 확인. (티어 정책은 자주 바뀌므로 본 문서에 수치 명시 X)

### 설정 위치

`~/Developer/video-use/.env`:

```
ELEVENLABS_API_KEY=sk_...
```

### 확인

```bash
grep -E '^ELEVENLABS_API_KEY=.+' ~/Developer/video-use/.env && echo OK || echo "키 없음 — Whisper 폴백"
```

키가 없거나 비어있으면 Mode A는 자동으로 `npx hyperframes transcribe` (로컬 Whisper)로 폴백됩니다.

## 보안

- `.env` 파일은 `.gitignore`에 포함되어 있습니다 (commit 안 됨).
- 키를 git/로그/PR에 노출하지 마세요.
- 다른 환경에서 setup 시 `bash scripts/setup.sh`가 `.env.example` → `.env` 템플릿만 만들고, 실제 키는 사용자가 직접 입력해야 합니다.
