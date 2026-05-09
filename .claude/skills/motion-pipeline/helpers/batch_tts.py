#!/usr/bin/env python3
"""
batch_tts.py — generate Korean (or any language) narration for a multi-segment
script using Microsoft Edge TTS, in parallel. Free, no API key required.

Reads a JSON segments file, runs edge-tts per segment concurrently, writes mp3s
to an output directory. Designed for the video-pipeline skill's Mode B (script →
video) flow.

Usage:
    python batch_tts.py segments.json -o footage/edit/narration/

segments.json schema:
{
  "voice":   "ko-KR-SunHiNeural",        # default voice if segment doesn't override
  "rate":    "+0%",                       # default rate
  "pitch":   "+0Hz",                      # default pitch
  "segments": [
    {
      "id": "set1-story",
      "text": "1994년 봄, 캐나다 온타리오의 작은 도시...",
      "voice": "ko-KR-SunHiNeural",       # optional override
      "rate":  "+0%",                     # optional override (e.g. "+15%" for brisk)
      "pitch": "-2Hz"                     # optional override (e.g. lower for Bridge)
    },
    ...
  ]
}

Korean voices (Edge TTS): ko-KR-SunHiNeural (F), ko-KR-InJoonNeural (M),
ko-KR-HyunsuMultilingualNeural (M, multilingual).

English/multilingual voices that handle Korean+English well:
en-US-AvaMultilingualNeural, en-US-AndrewMultilingualNeural,
en-US-EmmaMultilingualNeural, en-US-BrianMultilingualNeural.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

import edge_tts


async def synth(seg: dict, defaults: dict, out_dir: Path) -> tuple[str, Path, float]:
    """Synthesize one segment to mp3. Returns (id, path, duration_seconds)."""
    voice = seg.get("voice", defaults.get("voice", "ko-KR-SunHiNeural"))
    rate = seg.get("rate", defaults.get("rate", "+0%"))
    pitch = seg.get("pitch", defaults.get("pitch", "+0Hz"))
    sid = seg["id"]
    text = seg["text"].strip()

    out_path = out_dir / f"{sid}.mp3"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    communicator = edge_tts.Communicate(text, voice=voice, rate=rate, pitch=pitch)
    await communicator.save(str(out_path))

    # Probe duration via ffprobe; fall back to file-size estimate if missing.
    duration = await _probe_duration(out_path)
    return sid, out_path, duration


async def _probe_duration(path: Path) -> float:
    proc = await asyncio.create_subprocess_exec(
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(path),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
    )
    out, _ = await proc.communicate()
    try:
        return float(out.decode().strip())
    except ValueError:
        return 0.0


async def main_async(spec_path: Path, out_dir: Path, concurrency: int) -> int:
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    segments = spec.get("segments") or []
    if not segments:
        print("error: no segments in spec", file=sys.stderr)
        return 1

    defaults = {
        "voice": spec.get("voice"),
        "rate": spec.get("rate"),
        "pitch": spec.get("pitch"),
    }
    defaults = {k: v for k, v in defaults.items() if v}

    sem = asyncio.Semaphore(concurrency)

    async def bound(seg):
        async with sem:
            try:
                sid, path, dur = await synth(seg, defaults, out_dir)
                print(f"  ✓ {sid:24s} {dur:6.2f}s  →  {path}", file=sys.stderr)
                return {"id": sid, "path": str(path), "duration": dur}
            except Exception as e:
                print(f"  ✗ {seg.get('id', '?'):24s}  FAILED: {e}", file=sys.stderr)
                return {"id": seg.get("id"), "error": str(e)}

    print(
        f"generating {len(segments)} segments to {out_dir} (concurrency={concurrency})",
        file=sys.stderr,
    )
    results = await asyncio.gather(*(bound(s) for s in segments))

    manifest = out_dir / "manifest.json"
    manifest.write_text(
        json.dumps({"segments": results}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    failed = [r for r in results if "error" in r]
    print(f"\nwrote manifest: {manifest}", file=sys.stderr)
    if failed:
        print(f"⚠ {len(failed)} segment(s) failed", file=sys.stderr)
        return 2
    total = sum(r["duration"] for r in results)
    print(
        f"✅ {len(results)} segments, total {total:.1f}s ({total/60:.1f}min)",
        file=sys.stderr,
    )
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("spec", type=Path, help="path to segments JSON")
    ap.add_argument(
        "-o", "--output", type=Path, required=True, help="output directory for mp3s"
    )
    ap.add_argument(
        "-c", "--concurrency", type=int, default=8, help="max concurrent TTS calls"
    )
    args = ap.parse_args()

    return asyncio.run(main_async(args.spec, args.output, args.concurrency))


if __name__ == "__main__":
    raise SystemExit(main())
