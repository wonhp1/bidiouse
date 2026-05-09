# 비디오유즈

두 모드 영상 파이프라인. **기본은 무료 / 로컬 / 키 0개.**

| 모드                    | 입력                   | 산출물                                   |
| ----------------------- | ---------------------- | ---------------------------------------- |
| **A — 풋티지 편집**     | `footage/` 의 raw 영상 | 트랜스크립트 기반 컷 + 자막 + 모션그래픽 |
| **B — 스크립트 → 영상** | 스크립트 .md/.txt      | Edge TTS 내레이션 + 모션그래픽 비주얼    |

두 모드 모두 **dual deliverable** — `footage/edit/final.mp4` + `footage/edit/timeline.fcpxml`(Final Cut Pro 임포트용).

## 빠른 시작

```bash
bash scripts/setup.sh
```

그다음 Claude Code에서 자연어로:

- **Mode B**: "이 스크립트로 30초 한국어 릴스 만들어줘. SunHi 보이스, 타이틀 카드 + 숫자 카운터로."
- **Mode A**: "footage 영상으로 인터뷰 컷 편집해줘. 자막 + 로어써드."

자세한 단계별 사용법은 [USAGE.md](USAGE.md).

## 사용 도구 (전부 무료/로컬이 기본)

| 도구                                                     | 역할                                                            | 비용 |
| -------------------------------------------------------- | --------------------------------------------------------------- | ---- |
| [video-use](https://github.com/browser-use/video-use)    | 트랜스크립트 기반 컷·자막·컬러 (Python/uv 스킬)                 | $0   |
| [hyperframes](https://github.com/heygen-com/hyperframes) | HTML→비디오 모션그래픽 + 내장 Whisper(`hyperframes transcribe`) | $0   |
| **Edge TTS**                                             | Mode B 내레이션 (`ko-KR-SunHiNeural` 등)                        | $0   |
| **ffmpeg**                                               | 무음 검출(`silencedetect`), 합성, 자막 번인                     | $0   |

선택사항: [ElevenLabs Scribe](ENV_KEYS.md) — 다중 화자 분리 / 한국어 필러 자동컷이 핵심일 때만.

## 디렉토리

```
.
├── .claude/skills/
│   ├── motion-pipeline/        ← 두 모드 오케스트레이션 (이 프로젝트의 핵심 스킬)
│   │   ├── SKILL.md
│   │   ├── helpers/            ← batch_tts, edl_to_fcpxml, concat_segments, ...
│   │   └── examples/edl.example.json
│   └── video-use → ~/Developer/video-use   (프로젝트 로컬 심볼릭, gitignore 됨)
├── footage/                    ← raw 영상(A) 또는 산출물(B). edit/ 하위는 자동 생성
├── hyperframes/                ← hyperframes 컴포지션 프로젝트 + .agents/skills/
├── scripts/setup.sh            ← 멱등 셋업 자동화
├── USAGE.md                    ← 모드별 단계별 사용법 + FAQ + 트러블슈팅
├── ENV_KEYS.md                 ← (선택) ElevenLabs 키 안내
└── README.md
```

## 도구 업데이트

```bash
# video-use 본체 업데이트
cd ~/Developer/video-use && git pull && uv sync

# git pull 후에는 setup.sh 다시 한번 (edge-tts venv에 복원됨)
bash scripts/setup.sh   # 이 repo 루트에서 실행

# hyperframes (npx 베이스라 항상 최신, 보일러플레이트만 수동)
cd hyperframes && npx hyperframes upgrade
```

## 라이선스 / 출처

- [browser-use/video-use](https://github.com/browser-use/video-use) — 외부 스킬, ~/Developer/video-use에 clone
- [heygen-com/hyperframes](https://github.com/heygen-com/hyperframes) — Apache 2.0
- 이 repo의 `motion-pipeline` 스킬과 helpers — 옆 프로젝트(`/영상편집 video-use`)의 검증된 video-pipeline을 이식
