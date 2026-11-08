#!/usr/bin/env python3
"""Turn a dark-on-light logo (PNG/JPG) into a transparent PNG tinted with the brand color.

  tint_logo.py logo-black.png logo.png --color "#C9A55C" [--width 480] [--invert]

--invert: use when the source is a LIGHT logo on a DARK background.
Requires Pillow (pip install pillow).
"""
import argparse
import sys

try:
    from PIL import Image
except ImportError:
    print("يحتاج Pillow: pip install pillow", file=sys.stderr)
    sys.exit(2)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("out")
    ap.add_argument("--color", default="#C9A55C")
    ap.add_argument("--width", type=int, default=480)
    ap.add_argument("--invert", action="store_true")
    ap.add_argument("--crop", action="store_true", help="crop transparent margins (default keeps the source canvas)")
    a = ap.parse_args()

    c = a.color.lstrip("#")
    rgb = tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))
    im = Image.open(a.src).convert("RGBA")
    # flatten onto white so transparent areas count as "background"
    bg = Image.new("RGBA", im.size, (255, 255, 255, 255))
    bg.alpha_composite(im)
    gray = bg.convert("L")
    alpha = gray.point(lambda v: v if a.invert else 255 - v)
    out = Image.new("RGBA", im.size, rgb + (0,))
    out.putalpha(alpha)
    if a.crop:
        bbox = out.getbbox()
        if bbox:
            out = out.crop(bbox)
    r = a.width / out.width
    out = out.resize((a.width, max(1, int(out.height * r))), Image.LANCZOS)
    out.save(a.out)
    print("تم: %s (%dx%d)" % (a.out, out.width, out.height))


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    main()
