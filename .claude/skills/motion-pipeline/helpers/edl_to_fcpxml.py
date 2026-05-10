#!/usr/bin/env python3
"""
edl_to_fcpxml.py — convert a video-use EDL JSON into FCPXML 1.10 for Final Cut Pro.

Reads an EDL describing source clips, cut decisions, motion-graphic overlays,
and subtitles, and emits an FCPXML that imports into FCP with the timeline
already assembled (V1 cuts, V2 overlays, caption track for subtitles).

Run AFTER video-use has authored the cut and BEFORE / IN ADDITION TO the final
ffmpeg composite. The user receives both `final.mp4` (ready to ship) and
`timeline.fcpxml` (editable in FCP from a polished starting point).

Usage:
    python edl_to_fcpxml.py edl.json -o timeline.fcpxml [--srt subs.srt]

EDL schema:
{
  "name": "My Project",
  "fps": 30,
  "width": 1920,
  "height": 1080,
  "sources": [
    {"id": "s1", "path": "/abs/path/clip1.mov", "duration": 120.5,
     "name": "clip1", "has_audio": true}
  ],
  "cuts": [
    {"source_id": "s1", "in": 12.34, "out": 18.56, "name": "intro"}
  ],
  "overlays": [
    {"path": "/abs/path/lower-third.mov", "start": 5.0, "duration": 3.0,
     "lane": 1, "has_audio": false, "name": "lower-third"}
  ],
  "subtitles": [
    {"start": 0.5, "end": 2.0, "text": "Hello world"}
  ]
}
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import unicodedata
from fractions import Fraction
from urllib.parse import quote
from xml.dom import minidom
from xml.etree import ElementTree as ET

NTSC_FPS = {
    # int(round(fps_float * 1000)) → (num, den)
    23976: (24000, 1001),
    23980: (24000, 1001),
    29970: (30000, 1001),
    29976: (30000, 1001),
    59940: (60000, 1001),
}


def parse_fps(edl: dict) -> tuple[int, int]:
    """EDL에서 fps_num/fps_den 또는 fps(int|float|list)를 받아 (num, den) 반환."""
    if "fps_num" in edl and "fps_den" in edl:
        return int(edl["fps_num"]), int(edl["fps_den"])
    fps = edl.get("fps", 30)
    if isinstance(fps, (list, tuple)) and len(fps) == 2:
        return int(fps[0]), int(fps[1])
    fps_f = float(fps)
    key = int(round(fps_f * 1000))
    if key in NTSC_FPS:
        return NTSC_FPS[key]
    return int(round(fps_f)), 1


def t(seconds: float, fps_num: int, fps_den: int) -> str:
    """Frame-align seconds → FCPXML 'N/Ds' rational. NTSC(29.97 등) 정확 처리."""
    frames = round(float(seconds) * fps_num / fps_den)
    if frames == 0:
        return "0s"
    f = Fraction(frames * fps_den, fps_num)
    return (
        f"{f.numerator}s" if f.denominator == 1 else f"{f.numerator}/{f.denominator}s"
    )


def frame_duration(fps_num: int, fps_den: int) -> str:
    """frameDuration = 1초 / fps = fps_den / fps_num."""
    f = Fraction(fps_den, fps_num)
    return (
        f"{f.numerator}s" if f.denominator == 1 else f"{f.numerator}/{f.denominator}s"
    )


def format_name(height: int, fps_num: int, fps_den: int) -> str:
    """FCP 표기: 1080p30, 2160p2997 등."""
    fps_f = fps_num / fps_den
    if fps_den == 1:
        return f"FFVideoFormat{height}p{int(round(fps_f))}"
    return f"FFVideoFormat{height}p{int(round(fps_f * 100))}"


def file_url(path: str) -> str:
    """Build file:// URL. macOS는 한글 path를 NFD로 저장하지만
    Final Cut Pro의 XML 파서는 NFC를 기대한다 — normalize 후 percent-encode."""
    abs_path = os.path.abspath(os.path.expanduser(path))
    nfc_path = unicodedata.normalize("NFC", abs_path)
    return "file://" + quote(nfc_path, safe="/:")


def srt_time(seconds: float) -> str:
    h = int(seconds // 3600)
    seconds -= h * 3600
    m = int(seconds // 60)
    seconds -= m * 60
    s = int(seconds)
    ms = round((seconds - s) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def build_fcpxml(edl: dict) -> ET.Element:
    fps_num, fps_den = parse_fps(edl)
    width = int(edl.get("width", 1920))
    height = int(edl.get("height", 1080))
    project_name = edl.get("name", "video-use project")

    root = ET.Element("fcpxml", version="1.10")
    resources = ET.SubElement(root, "resources")

    # ---- format ----
    ET.SubElement(
        resources,
        "format",
        id="r1",
        name=format_name(height, fps_num, fps_den),
        frameDuration=frame_duration(fps_num, fps_den),
        width=str(width),
        height=str(height),
        colorSpace="1-1-1 (Rec. 709)",
    )

    rid = 1
    src_ref: dict[str, str] = {}
    src_has_audio: dict[str, bool] = {}

    # ---- source assets ----
    for src in edl.get("sources", []):
        rid += 1
        ref = f"r{rid}"
        src_ref[src["id"]] = ref
        has_audio = bool(src.get("has_audio", True))
        src_has_audio[src["id"]] = has_audio
        attrs = {
            "id": ref,
            "name": src.get("name", os.path.splitext(os.path.basename(src["path"]))[0]),
            "start": "0s",
            "duration": t(src.get("duration", 3600), fps_num, fps_den),
            "hasVideo": "1",
            "format": "r1",
            "hasAudio": "1" if has_audio else "0",
        }
        if has_audio:
            attrs.update(
                {"audioSources": "1", "audioChannels": "2", "audioRate": "48000"}
            )
        asset = ET.SubElement(resources, "asset", **attrs)
        ET.SubElement(
            asset, "media-rep", kind="original-media", src=file_url(src["path"])
        )

    # ---- overlay assets ----
    overlay_refs: list[str] = []
    overlay_has_audio: list[bool] = []
    for ov in edl.get("overlays", []):
        rid += 1
        ref = f"r{rid}"
        overlay_refs.append(ref)
        ov_audio = bool(ov.get("has_audio", False))
        overlay_has_audio.append(ov_audio)
        attrs = {
            "id": ref,
            "name": ov.get("name", os.path.splitext(os.path.basename(ov["path"]))[0]),
            "start": "0s",
            "duration": t(ov["duration"], fps_num, fps_den),
            "hasVideo": "1",
            "format": "r1",
            "hasAudio": "1" if ov_audio else "0",
        }
        if ov_audio:
            attrs.update(
                {"audioSources": "1", "audioChannels": "2", "audioRate": "48000"}
            )
        asset = ET.SubElement(resources, "asset", **attrs)
        ET.SubElement(
            asset, "media-rep", kind="original-media", src=file_url(ov["path"])
        )

    # ---- library / event / project / sequence / spine ----
    library = ET.SubElement(root, "library")
    event = ET.SubElement(library, "event", name="video-use")
    project = ET.SubElement(event, "project", name=project_name)

    cuts = edl.get("cuts", [])
    overlays = edl.get("overlays", [])
    subs = edl.get("subtitles", [])

    total_dur = sum(float(c["out"]) - float(c["in"]) for c in cuts) if cuts else 0.0
    sequence = ET.SubElement(
        project,
        "sequence",
        format="r1",
        duration=t(total_dur, fps_num, fps_den),
        tcStart="0s",
        tcFormat="NDF",
        audioLayout="stereo",
        audioRate="48k",
    )
    spine = ET.SubElement(sequence, "spine")

    # ---- cuts on the spine ----
    cut_windows: list[tuple[float, float, ET.Element]] = (
        []
    )  # (timeline_start, timeline_end, elem)
    cursor = 0.0
    for i, cut in enumerate(cuts):
        in_t = float(cut["in"])
        out_t = float(cut["out"])
        dur = out_t - in_t
        if dur <= 0:
            continue
        clip = ET.SubElement(
            spine,
            "asset-clip",
            ref=src_ref[cut["source_id"]],
            offset=t(cursor, fps_num, fps_den),
            name=cut.get("name", f"cut{i+1}"),
            start=t(in_t, fps_num, fps_den),
            duration=t(dur, fps_num, fps_den),
            format="r1",
            tcFormat="NDF",
        )
        cut_windows.append((cursor, cursor + dur, clip))
        cursor += dur

    def find_host(ts: float) -> tuple[ET.Element, float] | None:
        """Find the cut clip that covers timeline timestamp `ts`. Returns
        (host_clip_elem, local_offset_inside_source) or None."""
        for win_start, win_end, elem in cut_windows:
            if win_start <= ts < win_end:
                # Translate timeline ts → source-local time.
                # The host clip plays source[start .. start+dur]; offset along the
                # source matches (ts - win_start). Connected clip `offset` is in
                # the SOURCE's timeline (frame-locked to start), so:
                source_start = float(elem.get("start").replace("s", "").split("/")[0])
                # Reconstruct exact start as float:
                start_str = elem.get("start")
                if "/" in start_str:
                    n, d = start_str[:-1].split("/")
                    source_start = float(n) / float(d)
                else:
                    source_start = float(start_str[:-1])
                local = source_start + (ts - win_start)
                return elem, local
        return None

    # ---- overlays as connected clips on lane >= 1 ----
    for j, ov in enumerate(overlays):
        ov_start = float(ov["start"])
        ov_dur = float(ov["duration"])
        host = find_host(ov_start)
        if host is None:
            continue  # overlay falls outside any cut; skip
        host_elem, local_offset = host
        ET.SubElement(
            host_elem,
            "asset-clip",
            ref=overlay_refs[j],
            lane=str(ov.get("lane", 1)),
            offset=t(local_offset, fps_num, fps_den),
            name=ov.get("name", f"overlay{j+1}"),
            start="0s",
            duration=t(ov_dur, fps_num, fps_den),
            format="r1",
            enabled="1",
        )

    # ---- subtitles as captions on a negative lane ----
    # Each caption attaches to the cut that contains its start time so the
    # caption's offset is computed against the correct host's source-local time.
    for k, sub in enumerate(subs):
        cap_start = float(sub["start"])
        cap_dur = float(sub["end"]) - cap_start
        if cap_dur <= 0:
            continue
        host = find_host(cap_start)
        if host is None:
            continue  # caption falls outside any cut
        host_elem, local_offset = host
        caption = ET.SubElement(
            host_elem,
            "caption",
            lane="-1",
            offset=t(local_offset, fps_num, fps_den),
            name="Caption",
            duration=t(cap_dur, fps_num, fps_den),
            role="iTT?captionFormat=ITT.ko",
        )
        style_id = f"ts{k+1}"
        text_el = ET.SubElement(caption, "text")
        ts_el = ET.SubElement(text_el, "text-style", ref=style_id)
        ts_el.text = sub["text"]
        style_def = ET.SubElement(caption, "text-style-def", id=style_id)
        ET.SubElement(
            style_def,
            "text-style",
            font=".AppleSystemUIFont",
            fontSize="13",
            fontColor="1 1 1 1",
            backgroundColor="0 0 0 1",
            alignment="center",
        )

    return root


def write_srt(subs: list[dict], out_path: str) -> None:
    with open(out_path, "w", encoding="utf-8") as f:
        for i, s in enumerate(subs, 1):
            f.write(
                f"{i}\n{srt_time(float(s['start']))} --> {srt_time(float(s['end']))}\n{s['text']}\n\n"
            )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("edl", help="path to edl.json")
    ap.add_argument(
        "-o", "--output", default=None, help="FCPXML output path (default: stdout)"
    )
    ap.add_argument(
        "--srt", default=None, help="also write subtitles as SRT to this path"
    )
    args = ap.parse_args()

    with open(args.edl, encoding="utf-8") as f:
        edl = json.load(f)

    root = build_fcpxml(edl)
    rough = ET.tostring(root, encoding="utf-8")
    pretty = (
        minidom.parseString(rough)
        .toprettyxml(indent="  ", encoding="UTF-8")
        .decode("utf-8")
    )
    pretty = pretty.replace(
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE fcpxml>',
    )

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(pretty)
        print(f"wrote {args.output}", file=sys.stderr)
    else:
        sys.stdout.write(pretty)

    if args.srt:
        subs = edl.get("subtitles", [])
        if subs:
            write_srt(subs, args.srt)
            print(f"wrote {args.srt}", file=sys.stderr)
        else:
            print("no subtitles in EDL — skipping SRT", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
