#!/usr/bin/env python3
"""
edl_to_fcp7_xml.py — EDL → FCP7 XML (XMEML v5) for Adobe Premiere Pro.

Premiere가 표준으로 받는 형식. Final Cut Pro 7 XML이지만 Premiere도 잘 받음.
컷, 소스, 시퀀스 메타데이터를 포함. 자막은 별도 SRT로 처리 (Premiere Captions 패널에서 import).

Usage:
    python edl_to_fcp7_xml.py footage/edit/edl.json -o footage/edit/timeline.xml
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import unicodedata
from urllib.parse import quote
from xml.dom import minidom
from xml.etree import ElementTree as ET

NTSC_FPS = {
    23976: (24, "TRUE"),
    23980: (24, "TRUE"),
    24000: (24, "FALSE"),
    25000: (25, "FALSE"),
    29970: (30, "TRUE"),
    29976: (30, "TRUE"),
    30000: (30, "FALSE"),
    50000: (50, "FALSE"),
    59940: (60, "TRUE"),
    60000: (60, "FALSE"),
}


def parse_fps(edl: dict) -> tuple[int, str]:
    """EDL fps → (timebase int, ntsc 'TRUE'/'FALSE')."""
    if "fps_num" in edl and "fps_den" in edl:
        fps_f = float(edl["fps_num"]) / float(edl["fps_den"])
    else:
        fps = edl.get("fps", 30)
        if isinstance(fps, (list, tuple)) and len(fps) == 2:
            fps_f = float(fps[0]) / float(fps[1])
        else:
            fps_f = float(fps)
    key = int(round(fps_f * 1000))
    if key in NTSC_FPS:
        return NTSC_FPS[key]
    return int(round(fps_f)), "FALSE"


def file_url(path: str) -> str:
    """macOS NFD → NFC 정규화 후 percent-encode (한글 경로 호환)."""
    abs_path = os.path.abspath(os.path.expanduser(path))
    nfc_path = unicodedata.normalize("NFC", abs_path)
    return "file://localhost" + quote(nfc_path, safe="/:")


def to_frames(seconds: float, fps: int) -> int:
    return int(round(float(seconds) * fps))


def add_rate(parent: ET.Element, timebase: int, ntsc: str) -> None:
    rate = ET.SubElement(parent, "rate")
    ET.SubElement(rate, "timebase").text = str(timebase)
    ET.SubElement(rate, "ntsc").text = ntsc


def build_xmeml(edl: dict) -> ET.Element:
    timebase, ntsc = parse_fps(edl)
    width = int(edl.get("width", 1920))
    height = int(edl.get("height", 1080))
    project_name = edl.get("name", "video-use project")

    cuts = edl.get("cuts", [])
    sources = edl.get("sources", [])
    if not sources:
        raise ValueError("EDL에 sources 없음")

    # source assets
    src_map = {}  # source_id → file element
    for src in sources:
        src_map[src["id"]] = src

    total_frames = (
        sum(to_frames(c["out"] - c["in"], timebase) for c in cuts) if cuts else 0
    )

    root = ET.Element("xmeml", version="5")
    sequence = ET.SubElement(root, "sequence", id="sequence-1")
    ET.SubElement(sequence, "name").text = project_name
    ET.SubElement(sequence, "duration").text = str(total_frames)
    add_rate(sequence, timebase, ntsc)

    # timecode
    timecode = ET.SubElement(sequence, "timecode")
    add_rate(timecode, timebase, ntsc)
    ET.SubElement(timecode, "string").text = "00:00:00:00"
    ET.SubElement(timecode, "frame").text = "0"
    ET.SubElement(timecode, "displayformat").text = "NDF" if ntsc == "FALSE" else "DF"

    # media → video/audio
    media = ET.SubElement(sequence, "media")
    video = ET.SubElement(media, "video")

    # video format
    vformat = ET.SubElement(video, "format")
    samplecharacteristics = ET.SubElement(vformat, "samplecharacteristics")
    add_rate(samplecharacteristics, timebase, ntsc)
    ET.SubElement(samplecharacteristics, "width").text = str(width)
    ET.SubElement(samplecharacteristics, "height").text = str(height)
    ET.SubElement(samplecharacteristics, "anamorphic").text = "FALSE"
    ET.SubElement(samplecharacteristics, "pixelaspectratio").text = "square"
    ET.SubElement(samplecharacteristics, "fielddominance").text = "none"
    ET.SubElement(samplecharacteristics, "colordepth").text = "24"

    # video track 1
    vtrack = ET.SubElement(video, "track")
    cursor_frames = 0
    declared_files = set()  # 같은 file은 한 번만 declare
    for i, cut in enumerate(cuts, start=1):
        src = src_map[cut["source_id"]]
        in_f = to_frames(cut["in"], timebase)
        out_f = to_frames(cut["out"], timebase)
        dur = out_f - in_f
        if dur <= 0:
            continue

        clipitem = ET.SubElement(vtrack, "clipitem", id=f"clipitem-{i}")
        ET.SubElement(clipitem, "name").text = cut.get("name", f"cut{i}")
        ET.SubElement(clipitem, "duration").text = str(
            to_frames(src.get("duration", 3600), timebase)
        )
        add_rate(clipitem, timebase, ntsc)
        ET.SubElement(clipitem, "start").text = str(cursor_frames)
        ET.SubElement(clipitem, "end").text = str(cursor_frames + dur)
        ET.SubElement(clipitem, "in").text = str(in_f)
        ET.SubElement(clipitem, "out").text = str(out_f)

        file_id = f"file-{src['id']}"
        if src["id"] not in declared_files:
            file_el = ET.SubElement(clipitem, "file", id=file_id)
            ET.SubElement(file_el, "name").text = src.get(
                "name", os.path.splitext(os.path.basename(src["path"]))[0]
            )
            ET.SubElement(file_el, "pathurl").text = file_url(src["path"])
            ET.SubElement(file_el, "duration").text = str(
                to_frames(src.get("duration", 3600), timebase)
            )
            add_rate(file_el, timebase, ntsc)
            file_media = ET.SubElement(file_el, "media")
            file_video = ET.SubElement(file_media, "video")
            vsc = ET.SubElement(file_video, "samplecharacteristics")
            add_rate(vsc, timebase, ntsc)
            ET.SubElement(vsc, "width").text = str(width)
            ET.SubElement(vsc, "height").text = str(height)
            if src.get("has_audio", True):
                file_audio = ET.SubElement(file_media, "audio")
                ET.SubElement(file_audio, "channelcount").text = "2"
            declared_files.add(src["id"])
        else:
            ET.SubElement(clipitem, "file", id=file_id)

        # link audio
        if src.get("has_audio", True):
            link_v = ET.SubElement(clipitem, "link")
            ET.SubElement(link_v, "linkclipref").text = f"clipitem-{i}"
            ET.SubElement(link_v, "mediatype").text = "video"
            ET.SubElement(link_v, "trackindex").text = "1"
            ET.SubElement(link_v, "clipindex").text = str(i)
            link_a = ET.SubElement(clipitem, "link")
            ET.SubElement(link_a, "linkclipref").text = f"audio-clipitem-{i}"
            ET.SubElement(link_a, "mediatype").text = "audio"
            ET.SubElement(link_a, "trackindex").text = "1"
            ET.SubElement(link_a, "clipindex").text = str(i)

        cursor_frames += dur

    # audio track 1 (mirror of video, if any source has audio)
    audio = ET.SubElement(media, "audio")
    if any(src_map[c["source_id"]].get("has_audio", True) for c in cuts):
        atrack = ET.SubElement(audio, "track")
        cursor_frames = 0
        for i, cut in enumerate(cuts, start=1):
            src = src_map[cut["source_id"]]
            if not src.get("has_audio", True):
                continue
            in_f = to_frames(cut["in"], timebase)
            out_f = to_frames(cut["out"], timebase)
            dur = out_f - in_f
            if dur <= 0:
                continue
            aclip = ET.SubElement(atrack, "clipitem", id=f"audio-clipitem-{i}")
            ET.SubElement(aclip, "name").text = cut.get("name", f"cut{i}")
            ET.SubElement(aclip, "duration").text = str(
                to_frames(src.get("duration", 3600), timebase)
            )
            add_rate(aclip, timebase, ntsc)
            ET.SubElement(aclip, "start").text = str(cursor_frames)
            ET.SubElement(aclip, "end").text = str(cursor_frames + dur)
            ET.SubElement(aclip, "in").text = str(in_f)
            ET.SubElement(aclip, "out").text = str(out_f)
            ET.SubElement(aclip, "file", id=f"file-{src['id']}")
            cursor_frames += dur

    # video track 2 — overlays (자막 mov 등 V2 lane)
    overlays = edl.get("overlays", [])
    if overlays:
        vtrack2 = ET.SubElement(video, "track")
        for j, ov in enumerate(overlays, start=1):
            ov_start_f = to_frames(ov["start"], timebase)
            ov_dur_f = to_frames(ov["duration"], timebase)
            if ov_dur_f <= 0:
                continue
            ov_clip = ET.SubElement(vtrack2, "clipitem", id=f"overlay-clipitem-{j}")
            ET.SubElement(ov_clip, "name").text = ov.get("name", f"overlay{j}")
            ET.SubElement(ov_clip, "duration").text = str(ov_dur_f)
            add_rate(ov_clip, timebase, ntsc)
            ET.SubElement(ov_clip, "start").text = str(ov_start_f)
            ET.SubElement(ov_clip, "end").text = str(ov_start_f + ov_dur_f)
            ET.SubElement(ov_clip, "in").text = "0"
            ET.SubElement(ov_clip, "out").text = str(ov_dur_f)
            ET.SubElement(ov_clip, "alphatype").text = "straight"

            ov_file_id = f"file-overlay-{j}"
            file_el = ET.SubElement(ov_clip, "file", id=ov_file_id)
            ET.SubElement(file_el, "name").text = ov.get("name", f"overlay{j}")
            ET.SubElement(file_el, "pathurl").text = file_url(ov["path"])
            ET.SubElement(file_el, "duration").text = str(ov_dur_f)
            add_rate(file_el, timebase, ntsc)
            file_media = ET.SubElement(file_el, "media")
            file_video = ET.SubElement(file_media, "video")
            vsc = ET.SubElement(file_video, "samplecharacteristics")
            add_rate(vsc, timebase, ntsc)
            ET.SubElement(vsc, "width").text = str(width)
            ET.SubElement(vsc, "height").text = str(height)

    return root


def main() -> None:
    ap = argparse.ArgumentParser(description="EDL JSON → FCP7 XML (Premiere 호환)")
    ap.add_argument("edl", help="EDL JSON 파일 경로")
    ap.add_argument("-o", "--output", required=True, help="출력 XML 파일")
    args = ap.parse_args()

    with open(args.edl, encoding="utf-8") as f:
        edl = json.load(f)

    root = build_xmeml(edl)

    # pretty print
    rough = ET.tostring(root, encoding="utf-8")
    pretty = (
        minidom.parseString(rough)
        .toprettyxml(indent="  ", encoding="utf-8")
        .decode("utf-8")
    )
    # FCP7 XML DOCTYPE 추가
    lines = pretty.splitlines()
    if lines and lines[0].startswith("<?xml"):
        out = lines[0] + "\n<!DOCTYPE xmeml>\n" + "\n".join(lines[1:])
    else:
        out = '<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE xmeml>\n' + pretty

    with open(args.output, "w", encoding="utf-8") as f:
        f.write(out)
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
