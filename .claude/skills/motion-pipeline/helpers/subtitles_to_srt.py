#!/usr/bin/env python3
"""
subtitles_to_srt.py — subtitles.json ↔ SRT 양방향 변환.

자막 텍스트를 어디서든(Aegisub, Subtitle Edit, VS Code 등) 편집할 수 있도록
표준 SRT 형식으로 export하고, 편집된 SRT를 다시 JSON으로 import한다.

Usage:
    # JSON → SRT (export, 편집 시작)
    python subtitles_to_srt.py export footage/edit/subtitles.json -o footage/edit/subtitles.srt

    # SRT → JSON (편집 후 갱신)
    python subtitles_to_srt.py import footage/edit/subtitles.srt -o footage/edit/subtitles.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


def fmt_srt_time(seconds: float) -> str:
    h = int(seconds // 3600)
    seconds -= h * 3600
    m = int(seconds // 60)
    seconds -= m * 60
    s = int(seconds)
    ms = round((seconds - s) * 1000)
    if ms == 1000:
        ms = 0
        s += 1
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def parse_srt_time(t: str) -> float:
    m = re.match(r"(\d{2}):(\d{2}):(\d{2})[,.](\d{3})", t.strip())
    if not m:
        raise ValueError(f"잘못된 SRT 시간: {t}")
    h, mn, s, ms = [int(x) for x in m.groups()]
    return h * 3600 + mn * 60 + s + ms / 1000.0


def export_srt(json_path: Path, out_path: Path) -> None:
    phrases = json.loads(json_path.read_text(encoding="utf-8"))
    lines = []
    for i, p in enumerate(phrases, start=1):
        lines.append(str(i))
        lines.append(f"{fmt_srt_time(p['start'])} --> {fmt_srt_time(p['end'])}")
        lines.append(p["text"].strip())
        lines.append("")  # blank line
    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"✓ {len(phrases)} phrase → {out_path}")


def import_srt(srt_path: Path, out_path: Path) -> None:
    raw = srt_path.read_text(encoding="utf-8").strip()
    blocks = re.split(r"\n\s*\n", raw)
    phrases = []
    for block in blocks:
        lines = [l for l in block.strip().splitlines() if l.strip()]
        if len(lines) < 3:
            continue
        # line 0: index (무시), line 1: 시간, line 2+: 텍스트
        time_line = lines[1]
        m = re.match(r"(\S+)\s*-->\s*(\S+)", time_line)
        if not m:
            continue
        start, end = parse_srt_time(m.group(1)), parse_srt_time(m.group(2))
        text = " ".join(lines[2:]).strip()
        phrases.append({"start": start, "end": end, "text": text})
    out_path.write_text(
        json.dumps(phrases, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"✓ {len(phrases)} phrase → {out_path}")


def main() -> None:
    ap = argparse.ArgumentParser(description="subtitles.json ↔ SRT 변환")
    ap.add_argument(
        "mode",
        choices=["export", "import"],
        help="export(JSON→SRT) 또는 import(SRT→JSON)",
    )
    ap.add_argument("input", type=Path, help="입력 파일")
    ap.add_argument("-o", "--output", type=Path, required=True, help="출력 파일")
    args = ap.parse_args()

    if not args.input.exists():
        sys.exit(f"입력 파일 없음: {args.input}")

    if args.mode == "export":
        export_srt(args.input, args.output)
    else:
        import_srt(args.input, args.output)


if __name__ == "__main__":
    main()
