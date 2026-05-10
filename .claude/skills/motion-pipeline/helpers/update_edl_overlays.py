#!/usr/bin/env python3
"""
update_edl_overlays.py — EDL의 overlays를 cut별 자막 mov 16개로 갱신.

split_subtitles_by_cuts.py가 만든 cut별 mov 디렉토리를 받아서 EDL의 overlays 항목을
재구성한다. lane=1 (V2)에 cut과 1:1 attach.

Usage:
    python update_edl_overlays.py footage/edit/edl.json hyperframes/renders/cuts
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("edl", type=Path)
    ap.add_argument("cuts_dir", type=Path)
    args = ap.parse_args()

    if not args.edl.exists():
        sys.exit(f"EDL 없음: {args.edl}")
    if not args.cuts_dir.exists():
        sys.exit(f"cuts 디렉토리 없음: {args.cuts_dir}")

    edl = json.loads(args.edl.read_text(encoding="utf-8"))
    cuts = edl["cuts"]

    overlays = []
    cursor = 0.0
    for i, c in enumerate(cuts, start=1):
        dur = c["out"] - c["in"]
        mov = (args.cuts_dir / f"subtitles_{i:02d}.mov").resolve()
        if not mov.exists():
            sys.exit(f"자막 mov 없음: {mov}")
        overlays.append(
            {
                "path": str(mov),
                "start": round(cursor, 4),
                "duration": round(dur, 4),
                "lane": 1,
                "name": f"subs-{i:02d}",
                "has_audio": False,
            }
        )
        cursor += dur

    edl["overlays"] = overlays
    args.edl.write_text(json.dumps(edl, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✓ EDL overlays = {len(overlays)}개 (cut과 1:1 attach)")


if __name__ == "__main__":
    main()
