#!/usr/bin/env python3
"""
build_subtitle_html.py — subtitles.json → hyperframes/index.html (4K caption clips).

자막 디자인(글래스모피즘 박스 + GSAP 모션그래픽)은 고정. 텍스트와 타이밍만 JSON에서 주입.

Usage:
    python build_subtitle_html.py footage/edit/subtitles.json -o hyperframes/index.html
"""

from __future__ import annotations

import argparse
import html
import json
import sys
from pathlib import Path

TEMPLATE = """<!doctype html>
<html lang="ko" data-resolution="landscape-4k">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=3840, height=2160" />
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.min.css" />
    <script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
    <style>
      * { margin: 0; padding: 0; box-sizing: border-box; }
      html, body {
        margin: 0;
        width: 3840px;
        height: 2160px;
        overflow: hidden;
        background: transparent;
        font-family: 'Pretendard', -apple-system, BlinkMacSystemFont, sans-serif;
      }
      #root { position: relative; width: 100%; height: 100%; }

      .caption {
        position: absolute;
        top: 50%;
        left: 50%;
        transform: translate(-50%, -50%);
        display: flex;
        align-items: center;
        justify-content: center;
        max-width: 3072px;
        width: max-content;
        pointer-events: none;
        will-change: opacity, transform, filter;
      }

      .caption-inner {
        position: relative;
        padding: 36px 88px 36px 110px;
        background: rgba(12, 14, 22, 0.72);
        backdrop-filter: blur(28px) saturate(140%);
        -webkit-backdrop-filter: blur(28px) saturate(140%);
        border: 1px solid rgba(255, 255, 255, 0.16);
        border-radius: 32px;
        box-shadow:
          0 24px 80px rgba(0, 0, 0, 0.55),
          0 2px 4px rgba(0, 0, 0, 0.35),
          inset 0 1px 0 rgba(255, 255, 255, 0.08);
        overflow: hidden;
        max-width: 3072px;
      }

      .caption-inner::after {
        content: '';
        position: absolute;
        top: 0; left: 0; right: 0;
        height: 1px;
        background: linear-gradient(90deg,
          rgba(255,255,255,0) 0%,
          rgba(255,255,255,0.4) 50%,
          rgba(255,255,255,0) 100%);
      }

      .caption-inner::before {
        content: '';
        position: absolute;
        left: 48px; top: 50%;
        width: 14px; height: 14px;
        margin-top: -7px;
        border-radius: 50%;
        background: radial-gradient(circle at 30% 30%, #ffffff 0%, #c9d4ff 60%, #6478ff 100%);
        box-shadow:
          0 0 24px rgba(180, 200, 255, 0.85),
          0 0 6px rgba(255, 255, 255, 1);
      }

      .caption-text {
        font-weight: 800;
        font-size: 92px;
        line-height: 1.22;
        letter-spacing: -0.025em;
        color: #ffffff;
        text-shadow: 0 2px 8px rgba(0, 0, 0, 0.6);
        white-space: nowrap;
        max-width: 2800px;
        overflow: hidden;
      }

      .caption-inner.wrap .caption-text {
        white-space: normal;
        text-align: center;
        max-width: 2800px;
      }
    </style>
  </head>
  <body>
    <div
      id="root"
      data-composition-id="subtitles"
      data-start="0"
      data-duration="__TOTAL_DURATION__"
      data-width="3840"
      data-height="2160"
    >
__CLIPS__
    </div>

    <script>
      document.querySelectorAll('.caption').forEach(function (el) {
        var inner = el.querySelector('.caption-inner');
        var text = inner.querySelector('.caption-text');
        if (text && text.textContent.length > 16) inner.classList.add('wrap');
      });

      window.__timelines = window.__timelines || {};
      var tl = gsap.timeline({ paused: true });

      document.querySelectorAll('.caption').forEach(function (el) {
        var start = parseFloat(el.dataset.start);
        var dur = parseFloat(el.dataset.duration);
        var inner = el.querySelector('.caption-inner');

        gsap.set(inner, { opacity: 0, scale: 0.94, y: 28, filter: 'blur(14px)' });

        tl.to(inner,
          { opacity: 1, scale: 1, y: 0, filter: 'blur(0px)', duration: 0.42, ease: 'expo.out' },
          start);

        var exitAt = start + Math.max(dur - 0.32, dur * 0.7);
        tl.to(inner,
          { opacity: 0, y: -22, filter: 'blur(7px)', duration: 0.3, ease: 'power1.in' },
          exitAt);
      });

      window.__timelines["subtitles"] = tl;
    </script>
  </body>
</html>
"""


def build(phrases: list[dict], total_duration: float) -> str:
    GAP = 0.04
    adjusted = []
    for i, p in enumerate(phrases):
        s, e = p["start"], p["end"]
        if i + 1 < len(phrases) and abs(phrases[i + 1]["start"] - e) < 0.001:
            e = max(s + 0.5, e - GAP)
        adjusted.append({"start": s, "end": e, "text": p["text"]})

    clips = []
    for i, p in enumerate(adjusted):
        s = p["start"]
        dur = max(p["end"] - p["start"], 0.8)
        text = html.escape(p["text"])
        clips.append(
            f'      <div class="clip caption" id="cap-{i+1}" data-start="{s:.3f}" data-duration="{dur:.3f}" data-track-index="0">\n'
            f'        <div class="caption-inner"><span class="caption-text">{text}</span></div>\n'
            f"      </div>"
        )
    clips_html = "\n".join(clips)

    return TEMPLATE.replace("__CLIPS__", clips_html).replace(
        "__TOTAL_DURATION__", f"{total_duration:.4f}"
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("subtitles_json", type=Path)
    ap.add_argument("-o", "--output", type=Path, required=True)
    ap.add_argument(
        "--duration",
        type=float,
        default=None,
        help="Total composition duration (sec). Default: max phrase end time.",
    )
    args = ap.parse_args()

    if not args.subtitles_json.exists():
        sys.exit(f"파일 없음: {args.subtitles_json}")

    phrases = json.loads(args.subtitles_json.read_text(encoding="utf-8"))
    if not phrases:
        sys.exit("자막 데이터가 비어있음")

    total = args.duration if args.duration else max(p["end"] for p in phrases)
    args.output.write_text(build(phrases, total), encoding="utf-8")
    print(f"✓ {len(phrases)} caption → {args.output} (duration {total:.2f}s)")


if __name__ == "__main__":
    main()
