#!/usr/bin/env python3
"""
build_compositions.py — generate one hyperframes composition per segment.

Reads:
  footage/edit/segments.json
  footage/edit/narration/manifest.json   (durations from batch_tts.py)
  footage/edit/narration/<id>.mp3        (audio files)
  compositions/_template/                (hyperframes scaffold for package.json/hyperframes.json)

Writes:
  compositions/<seg-id>/
    ├── index.html       (parameterized 1080x1920 9:16 vertical comp)
    ├── audio/<seg-id>.mp3
    ├── meta.json
    ├── package.json     (copied from _template)
    └── hyperframes.json (copied from _template)

Each composition is independently renderable via `npx hyperframes render`.
"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
SEGMENTS = ROOT / "footage/edit/segments.json"
NARRATION = ROOT / "footage/edit/narration"
COMPOSITIONS = ROOT / "compositions"
TEMPLATE = COMPOSITIONS / "_template"

THEMES = {
    "story": {
        "bg": "linear-gradient(180deg, #0a1628 0%, #1a2942 60%, #0f1a30 100%)",
        "text": "#f0f0f0",
        "accent": "#7a9cc6",
        "label_color": "#a3b8d4",
    },
    "bridge": {
        "bg": "radial-gradient(ellipse at 50% 60%, #1a0e08 0%, #050505 70%)",
        "text": "#e8c878",
        "accent": "#d4af37",
        "label_color": "#8a7340",
    },
    "saju": {
        "bg": "radial-gradient(ellipse at center, #2a1f0a 0%, #14100a 50%, #050505 100%)",
        "text": "#f5e6a8",
        "accent": "#d4af37",
        "label_color": "#d4af37",
    },
    "cta": {
        "bg": "linear-gradient(180deg, #0a1228 0%, #2a1810 50%, #6b4a1a 90%, #d4af37 100%)",
        "text": "#fff8e0",
        "accent": "#fff",
        "label_color": "#d4af37",
    },
}

SET_LABELS = {
    "1": "01 — BIRTH",
    "2": "02 — DISCOVERY",
    "3": "03 — SUCCESS",
    "4": "04 — EXPLOSION",
    "5": "05 — TURN",
    "6": "06 — HAILEY",
    "7": "07 — INVOICE",
    "8": "",
}

HANJA_BG = {
    "1-3-saju": "官 財",
    "2-3-saju": "食 印",
    "3-3-saju": "丙",
    "4-3-saju": "金 水",
    "5-3-saju": "偏 印",
    "6-3-saju": "戌",
    "7-3-saju": "金 水",
}


def get_theme(seg_id: str) -> str:
    if seg_id.endswith("-story"):
        return "story"
    if seg_id.endswith("-bridge"):
        return "bridge"
    if seg_id.endswith("-saju"):
        return "saju"
    if "cta" in seg_id:
        return "cta"
    return "story"


def split_into_chunks(text: str) -> list[str]:
    """Split text by sentence and em-dash boundaries; merge very short fragments."""
    parts = re.split(r"(?<=[.!?])\s+|\s+—\s+", text)
    parts = [p.strip(" —") for p in parts if p.strip()]
    merged = []
    for p in parts:
        if merged and len(p.split()) < 4:
            merged[-1] = merged[-1] + " — " + p
        else:
            merged.append(p)
    return merged


def compute_timings(chunks: list[str], duration: float) -> list[tuple[float, float]]:
    """Allocate chunk durations proportional to character count."""
    chars = [len(c) for c in chunks]
    total = sum(chars) or 1
    raw = [c / total * duration for c in chars]
    timings = []
    cursor = 0.0
    for d in raw:
        d = max(0.8, min(d, 8.0))
        timings.append((cursor, d))
        cursor += d
    actual = sum(d for _, d in timings)
    scale = duration / actual if actual else 1.0
    return [(s * scale, d * scale) for s, d in timings]


def html_escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def render_html(
    seg_id: str, text: str, duration: float, theme_key: str, set_label: str, hanja: str
) -> str:
    theme = THEMES[theme_key]
    chunks = split_into_chunks(text)
    timings = compute_timings(chunks, duration)

    captions_html: list[str] = []
    for i, (chunk, (start, dur)) in enumerate(zip(chunks, timings)):
        captions_html.append(
            f'      <div id="cap-{i}" class="caption clip" data-start="{start:.2f}" '
            f'data-duration="{dur:.2f}" data-track-index="{i+1}">'
            f"{html_escape(chunk)}</div>"
        )
    captions_block = "\n".join(captions_html)

    label_block = (
        f'      <div id="set-label" class="clip" data-start="0" '
        f'data-duration="{duration:.2f}" data-track-index="0">{set_label}</div>'
        if set_label
        else ""
    )

    hanja_block = (
        f'      <div id="hanja-bg" class="clip" data-start="0" '
        f'data-duration="{duration:.2f}" data-track-index="0">{html_escape(hanja)}</div>'
        if hanja
        else ""
    )

    watermark = (
        f'      <div id="watermark" class="clip" data-start="0" '
        f'data-duration="{duration:.2f}" data-track-index="99">saju.kax.ai.kr</div>'
    )

    # GSAP timeline — fade in at chunk start, fade out at chunk end, hard-kill after.
    tl_lines: list[str] = []
    for i, (start, dur) in enumerate(timings):
        tl_lines.append(
            f'      tl.fromTo("#cap-{i}", '
            f"{{opacity: 0, y: 30}}, "
            f"{{opacity: 1, y: 0, duration: 0.5, ease: 'power2.out'}}, {start:.2f});"
        )
        if dur > 0.6:
            exit_at = start + dur - 0.3
            tl_lines.append(
                f'      tl.to("#cap-{i}", '
                f"{{opacity: 0, duration: 0.3, ease: 'power2.in'}}, {exit_at:.2f});"
            )
            tl_lines.append(
                f'      tl.set("#cap-{i}", {{opacity: 0}}, {start + dur:.2f});'
            )
    if set_label:
        tl_lines.append(
            f'      tl.fromTo("#set-label", {{opacity: 0}}, '
            f"{{opacity: 0.8, duration: 0.8}}, 0);"
        )
    if hanja:
        tl_lines.append(
            f'      tl.fromTo("#hanja-bg", {{opacity: 0, scale: 0.92}}, '
            f"{{opacity: 0.08, scale: 1, duration: 1.2, ease: 'power1.out'}}, 0);"
        )

    timeline_js = "\n".join(tl_lines)

    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=1080, height=1920" />
    <script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@500;600&family=Inter:wght@400;500;600;700&family=Noto+Serif+KR:wght@500;700&display=swap" rel="stylesheet">
    <style>
      * {{ margin: 0; padding: 0; box-sizing: border-box; }}
      html, body {{
        width: 1080px; height: 1920px; overflow: hidden;
        background: {theme['bg']};
        font-family: 'Inter', system-ui, sans-serif;
        color: {theme['text']};
      }}
      #root {{ position: relative; width: 1080px; height: 1920px; }}
      #set-label {{
        position: absolute; top: 100px; left: 0; right: 0;
        text-align: center; font-size: 28px;
        color: {theme['label_color']};
        letter-spacing: 12px; font-weight: 700;
        text-transform: uppercase;
      }}
      #hanja-bg {{
        position: absolute; top: 50%; left: 50%;
        transform: translate(-50%, -50%);
        font-family: 'Noto Serif KR', 'Cormorant Garamond', serif;
        font-size: 720px; line-height: 1;
        color: {theme['accent']};
        pointer-events: none; white-space: nowrap;
        letter-spacing: 60px;
        text-shadow: 0 0 80px {theme['accent']}40;
      }}
      .caption {{
        position: absolute;
        top: 50%; left: 80px; right: 80px;
        transform: translateY(-50%);
        text-align: center;
        font-size: 60px; line-height: 1.45;
        font-weight: 500;
        text-shadow: 0 2px 24px rgba(0,0,0,0.6);
      }}
      #watermark {{
        position: absolute; bottom: 100px; left: 0; right: 0;
        text-align: center; font-size: 26px;
        color: {theme['accent']};
        opacity: 0.55; letter-spacing: 4px;
        font-weight: 600;
      }}
    </style>
  </head>
  <body>
    <div id="root" data-composition-id="main" data-start="0" data-duration="{duration:.2f}" data-width="1080" data-height="1920">
      <audio id="narration" class="clip" data-start="0" data-duration="{duration:.2f}" data-track-index="100" src="./audio/{seg_id}.mp3"></audio>
{label_block}
{hanja_block}
{captions_block}
{watermark}
    </div>
    <script>
      window.__timelines = window.__timelines || {{}};
      const tl = gsap.timeline({{ paused: true }});
{timeline_js}
      window.__timelines["main"] = tl;
    </script>
  </body>
</html>
"""


def build_one(seg: dict, duration: float) -> Path:
    seg_id = seg["id"]
    text = seg["text"]
    theme = get_theme(seg_id)
    set_num = seg_id.split("-")[0]
    set_label = SET_LABELS.get(set_num, "")
    hanja = HANJA_BG.get(seg_id, "")

    comp_dir = COMPOSITIONS / seg_id
    audio_dir = comp_dir / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)

    # Copy audio
    src_audio = NARRATION / f"{seg_id}.mp3"
    dst_audio = audio_dir / f"{seg_id}.mp3"
    if src_audio.exists():
        shutil.copy(src_audio, dst_audio)
    else:
        raise FileNotFoundError(f"missing audio: {src_audio}")

    # Generate HTML
    html = render_html(seg_id, text, duration, theme, set_label, hanja)
    (comp_dir / "index.html").write_text(html, encoding="utf-8")

    # Metadata
    (comp_dir / "meta.json").write_text(
        json.dumps({"id": seg_id, "name": seg_id}, indent=2), encoding="utf-8"
    )

    # Copy template files for renderability
    for fname in ("package.json", "hyperframes.json"):
        src = TEMPLATE / fname
        dst = comp_dir / fname
        if src.exists():
            shutil.copy(src, dst)

    return comp_dir


def main() -> int:
    seg_data = json.loads(SEGMENTS.read_text(encoding="utf-8"))
    manifest = json.loads((NARRATION / "manifest.json").read_text(encoding="utf-8"))
    duration_by_id = {s["id"]: s["duration"] for s in manifest["segments"]}

    print(f"building {len(seg_data['segments'])} compositions in {COMPOSITIONS}")
    for seg in seg_data["segments"]:
        seg_id = seg["id"]
        if seg_id not in duration_by_id:
            print(f"  ⚠ {seg_id}: no audio in manifest, skipping")
            continue
        comp_dir = build_one(seg, duration_by_id[seg_id])
        theme = get_theme(seg_id)
        print(
            f"  ✓ {seg_id:18s}  {theme:6s}  {duration_by_id[seg_id]:5.1f}s  →  {comp_dir.relative_to(ROOT)}"
        )
    print(f"\n✅ done. Render with: cd compositions/<id> && npx hyperframes render")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
