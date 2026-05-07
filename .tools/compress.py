#!/usr/bin/env python3
"""
Compress media:
  - All custom .mp4 / .mov  →  .webm  (VP9, CRF 33, max-width 1280, no audio)
  - All custom .png / .jpeg →  .jpg   (quality 85, sips)
  - Skip transparent PNGs (keep them as PNG)
  - Skip framer/images/* (template assets — Framer already optimized these)
  - Skip files that are already .webm / .jpg
Then rewrite source-file references.
"""
import os, subprocess, shutil, re, json, sys
from pathlib import Path

ROOT      = Path("/Users/nrgyg/Downloads/doungens.framer.website")
FFMPEG    = "/Users/nrgyg/Library/Python/3.9/lib/python/site-packages/imageio_ffmpeg/binaries/ffmpeg-macos-aarch64-v7.1"
SIPS      = "/usr/bin/sips"

# Source files where we need to rewrite asset paths
TEXT_FILES = [
    ROOT / "index.html",
    ROOT / "assets" / "stoik.js",
    ROOT / "assets" / "stoik.css",
    ROOT / "assets" / "unicorn-footer.json",
    ROOT / "assets" / "unicorn-strand.json",
]

# Asset directories to scan (custom assets only — skip framer/)
ASSET_DIRS = [
    ROOT / "assets" / "hero-reels",
    ROOT / "assets" / "hero-shots",
    ROOT / "assets" / "projects",
    ROOT / "assets" / "testimonials",
]
SINGLE_FILES = [
    ROOT / "assets" / "footer-photo.jpg",
]

VIDEO_EXTS = {".mp4", ".mov", ".m4v"}
IMG_EXTS   = {".png", ".jpeg"}  # .jpg already in target format

renames = {}   # old_relative_path -> new_relative_path

def png_has_alpha(p: Path) -> bool:
    """sips check for alpha channel."""
    out = subprocess.run([SIPS, "-g", "hasAlpha", str(p)], capture_output=True, text=True)
    return "yes" in out.stdout.lower()

def convert_video(src: Path):
    dst = src.with_suffix(".webm")
    if dst.exists() and dst.stat().st_size > 0:
        return dst
    print(f"  [video] {src.relative_to(ROOT)} → .webm")
    cmd = [
        FFMPEG, "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(src),
        "-c:v", "libvpx-vp9",
        "-b:v", "0",
        "-crf", "33",
        "-row-mt", "1",
        "-deadline", "good",
        "-cpu-used", "4",
        "-pix_fmt", "yuv420p",
        "-vf", "scale='min(1280,iw)':-2",
        "-an",  # strip audio
        str(dst),
    ]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(f"    FAIL: {r.stderr[:300]}")
        if dst.exists(): dst.unlink()
        return None
    return dst

def convert_image(src: Path):
    if src.suffix.lower() == ".png" and png_has_alpha(src):
        print(f"  [skip alpha] {src.relative_to(ROOT)}")
        return None
    dst = src.with_suffix(".jpg")
    if dst == src:
        return None  # already .jpg
    if dst.exists() and dst.stat().st_size > 0:
        return dst
    print(f"  [image] {src.relative_to(ROOT)} → .jpg")
    # sips: convert + jpegQuality 85 (sips uses 0-100? actually 0-1 with -s formatOptions)
    cmd = [
        SIPS, "-s", "format", "jpeg", "-s", "formatOptions", "85",
        str(src), "--out", str(dst),
    ]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(f"    FAIL: {r.stderr[:300]}")
        if dst.exists(): dst.unlink()
        return None
    return dst

def collect_files():
    files = []
    for d in ASSET_DIRS:
        for p in d.rglob("*"):
            if p.is_file() and (p.suffix.lower() in VIDEO_EXTS or p.suffix.lower() in IMG_EXTS):
                files.append(p)
    for p in SINGLE_FILES:
        if p.exists() and (p.suffix.lower() in VIDEO_EXTS or p.suffix.lower() in IMG_EXTS):
            files.append(p)
    return files

def main():
    print("=== Compressing media ===")
    files = collect_files()
    print(f"Found {len(files)} candidate files")
    for src in files:
        if src.suffix.lower() in VIDEO_EXTS:
            dst = convert_video(src)
        else:
            dst = convert_image(src)
        if dst and dst != src:
            old_rel = str(src.relative_to(ROOT))
            new_rel = str(dst.relative_to(ROOT))
            renames[old_rel] = new_rel

    print(f"\n=== Rewriting {len(renames)} references in source files ===")
    for f in TEXT_FILES:
        if not f.exists():
            continue
        s = f.read_text(encoding="utf-8")
        before = s
        for old, new in renames.items():
            # full path
            s = s.replace(old, new)
            # also handle old basenames (just in case anywhere uses them)
        if s != before:
            f.write_text(s, encoding="utf-8")
            print(f"  updated: {f.relative_to(ROOT)}")

    print(f"\n=== Removing originals (only those that converted successfully) ===")
    removed = 0
    for old in renames:
        old_p = ROOT / old
        if old_p.exists() and old_p != ROOT / renames[old]:
            old_p.unlink()
            removed += 1
    print(f"  removed {removed} original files")

    # Save renames for reference
    (ROOT / ".tools" / "renames.json").write_text(json.dumps(renames, indent=2))
    print("\nDone.")

if __name__ == "__main__":
    main()
