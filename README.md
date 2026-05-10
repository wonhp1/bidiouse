# 비디오유즈 ([bidiouse](https://github.com/wonhp1/bidiouse))

두 모드 영상 파이프라인. **기본은 무료 / 로컬 / 키 0개.**

> Repo: https://github.com/wonhp1/bidiouse
> License: [MIT](LICENSE)

| 모드                    | 입력                   | 산출물                                   |
| ----------------------- | ---------------------- | ---------------------------------------- |
| **A — 풋티지 편집**     | `footage/` 의 raw 영상 | 트랜스크립트 기반 컷 + 자막 + 모션그래픽 |
| **B — 스크립트 → 영상** | 스크립트 .md/.txt      | Edge TTS 내레이션 + 모션그래픽 비주얼    |

두 모드 모두 **triple deliverable** — `footage/edit/`에 다음 세 파일 생성:

- `final.mp4` — 자막 번인된 완성본
- `timeline.fcpxml` — **Final Cut Pro** 임포트용 (컷 + 인포그래픽 자막 V2 overlay + caption track)
- `timeline.xml` — **Premiere Pro** 임포트용 (FCP7 XML, 컷 + 인포그래픽 자막 V2 overlay)
- (보조) `subtitles.srt` — Premiere Captions 패널 import용, 또는 어디서든 사용 가능

**자막 텍스트 수정**도 명령 한 줄로 자동화 — SRT 편집 → `bash scripts/rerender_subtitles.sh` → 양 NLE 파일 동시 갱신.

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

## AI 에이전트 호환성

| 에이전트                   | 자동 트리거 (자연어 요청)                                            | 수동 명령 실행                    |
| -------------------------- | -------------------------------------------------------------------- | --------------------------------- |
| **Claude Code**            | ✅ `CLAUDE.md` + `.claude/skills/motion-pipeline/SKILL.md` 자동 인식 | ✅                                |
| **Codex / Cursor / Aider** | △ `AGENTS.md` (= CLAUDE.md 심볼릭) 자동 인식                         | ✅                                |
| **Gemini CLI**             | △ AGENTS.md 일부 인식, 명시적 안내 권장                              | ✅                                |
| **그 외**                  | ❌ 명시적 안내 필요                                                  | ✅ — bash/python 명령어 실행 가능 |

핵심 인프라(`scripts/*.sh`, `helpers/*.py`)는 어떤 에이전트든 호출 가능. 자세한 호환성 안내는 [AGENTS.md](AGENTS.md).

## 디렉토리

```
.
├── .claude/skills/
│   ├── motion-pipeline/        ← 두 모드 오케스트레이션 (이 프로젝트의 핵심 스킬)
│   │   ├── SKILL.md
│   │   ├── helpers/            ← edl_to_fcpxml, edl_to_fcp7_xml, batch_tts,
│   │   │                          subtitles_to_srt, build_subtitle_html,
│   │   │                          split_subtitles_by_cuts, update_edl_overlays, ...
│   │   └── examples/edl.example.json
│   └── video-use → ~/Developer/video-use   (프로젝트 로컬 심볼릭, gitignore 됨)
├── footage/                    ← raw 영상(A) 또는 산출물(B). edit/ 하위는 자동 생성
├── hyperframes/                ← hyperframes 컴포지션 프로젝트 + .agents/skills/
├── scripts/
│   ├── setup.sh                ← 멱등 셋업 자동화
│   ├── export_nle_files.sh     ← EDL → FCPXML + Premiere XML 동시 export
│   └── rerender_subtitles.sh   ← SRT 수정 → 자막 mov 재렌더 + 양 NLE 갱신
├── USAGE.md                    ← 모드별 단계별 사용법 + 자막 편집 + FAQ + 트러블슈팅
├── ENV_KEYS.md                 ← (선택) ElevenLabs 키 안내
├── CLAUDE.md                   ← Claude Code 진입 컨텍스트 (자동 인식)
├── AGENTS.md → CLAUDE.md       ← Codex/Gemini CLI/Cursor 등 호환 (심볼릭)
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

이 repo: [MIT](LICENSE) — 자유롭게 사용/수정/재배포 가능 (라이선스 문구만 보존).

외부 의존 (setup.sh가 받는 사람 환경에 직접 설치):

- [browser-use/video-use](https://github.com/browser-use/video-use) — `~/Developer/video-use`에 clone되는 외부 스킬
- [heygen-com/hyperframes](https://github.com/heygen-com/hyperframes) — Apache 2.0
- [Microsoft Edge TTS](https://github.com/rany2/edge-tts) — GPL-3.0 (Python 클라이언트)
- [ffmpeg](https://ffmpeg.org/) — LGPL/GPL (시스템 설치)
