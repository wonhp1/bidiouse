#!/usr/bin/env python3
"""
split_subtitles_by_cuts.py — 통합 자막 mov를 cut별 mov로 분할.

EDL의 cut 16개 timeline 좌표 범위에 맞춰 자막 mov를 N개로 stream copy 분할.
ProRes 4444는 intra-frame 코덱이라 stream copy 가능 (~10초).

Usage:
    python split_subtitles_by_cuts.py footage/edit/edl.json hyperframes/renders/subtitles.mov \
      -o hyperframes/renders/cuts
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("edl", type=Path)
    ap.add_argument("subtitles_mov", type=Path)
    ap.add_argument("-o", "--output-dir", type=Path, required=True)
    args = ap.parse_args()

    if not args.edl.exists():
        sys.exit(f"EDL 없음: {args.edl}")
    if not args.subtitles_mov.exists():
        sys.exit(f"자막 mov 없음: {args.subtitles_mov}")

    args.output_dir.mkdir(parents=True, exist_ok=True)

    edl = json.loads(args.edl.read_text(encoding="utf-8"))
    cuts = edl["cuts"]

    cursor = 0.0
    for i, c in enumerate(cuts, start=1):
        dur = c["out"] - c["in"]
        s, e = cursor, cursor + dur
        out = args.output_dir / f"subtitles_{i:02d}.mov"
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-hide_banner",
                "-loglevel",
                "error",
                "-ss",
                f"{s:.4f}",
                "-to",
                f"{e:.4f}",
                "-i",
                str(args.subtitles_mov),
                "-c",
                "copy",
                str(out),
            ],
            check=True,
        )
        cursor += dur

    total = sum(
        (args.output_dir / f"subtitles_{i+1:02d}.mov").stat().st_size
        for i in range(len(cuts))
    )
    print(f"✓ {len(cuts)} mov → {args.output_dir} ({total / 1024 / 1024:.0f} MB)")


if __name__ == "__main__":
    main()
