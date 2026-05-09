#!/usr/bin/env python3
"""
concat_segments.py — assemble all segment renders into final.mp4 + edl.json.

Reads:
  footage/edit/segments.json     (segment order)
  footage/edit/narration/manifest.json
  compositions/<id>/output.mp4   (rendered per segment)

Writes:
  footage/edit/edl.json
  footage/edit/concat-list.txt
  footage/edit/final.mp4
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
SEGMENTS = ROOT / "footage/edit/segments.json"
NARRATION = ROOT / "footage/edit/narration"
COMPOSITIONS = ROOT / "compositions"
EDIT_DIR = ROOT / "footage/edit"


def main() -> int:
    seg_data = json.loads(SEGMENTS.read_text(encoding="utf-8"))
    manifest = json.loads((NARRATION / "manifest.json").read_text(encoding="utf-8"))
    duration_by_id = {s["id"]: s["duration"] for s in manifest["segments"]}

    sources = []
    cuts = []
    rid = 0
    cursor = 0.0
    concat_lines = []
    missing = []

    for seg in seg_data["segments"]:
        seg_id = seg["id"]
        mp4 = COMPOSITIONS / seg_id / "output.mp4"
        if not mp4.exists():
            missing.append(seg_id)
            continue
        duration = duration_by_id.get(seg_id) or 0.0
        rid += 1
        sid = f"s{rid}"
        sources.append(
            {
                "id": sid,
                "path": str(mp4),
                "duration": duration,
                "name": seg_id,
                "has_audio": True,
            }
        )
        cuts.append(
            {
                "source_id": sid,
                "in": 0.0,
                "out": duration,
                "name": seg_id,
            }
        )
        concat_lines.append(f"file '{mp4}'")
        cursor += duration

    if missing:
        print(f"❌ missing renders: {missing}", file=sys.stderr)
        return 1

    # EDL
    edl = {
        "name": "Justin Bieber Saju Reels",
        "fps": 30,
        "width": 1080,
        "height": 1920,
        "sources": sources,
        "cuts": cuts,
        "overlays": [],
        "subtitles": [],
    }
    edl_path = EDIT_DIR / "edl.json"
    edl_path.write_text(json.dumps(edl, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✓ wrote {edl_path.relative_to(ROOT)}")

    # concat list
    concat_path = EDIT_DIR / "concat-list.txt"
    concat_path.write_text("\n".join(concat_lines) + "\n", encoding="utf-8")
    print(f"✓ wrote {concat_path.relative_to(ROOT)}  ({len(concat_lines)} segments)")

    # ffmpeg concat (lossless — all inputs share codec/fps/dimensions from hyperframes)
    final_mp4 = EDIT_DIR / "final.mp4"
    cmd = [
        "ffmpeg",
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(concat_path),
        "-c",
        "copy",
        str(final_mp4),
    ]
    print(f"\n▶ ffmpeg concat → {final_mp4.relative_to(ROOT)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"❌ ffmpeg failed:\n{result.stderr}", file=sys.stderr)
        return 1

    # Probe final
    probe = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration,size",
            "-of",
            "default=noprint_wrappers=1",
            str(final_mp4),
        ],
        capture_output=True,
        text=True,
    )
    print(f"✓ final.mp4 created")
    print(probe.stdout.strip())
    print(f"\n✅ {cursor:.1f}s ({cursor/60:.1f}min) of video assembled")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
