#!/usr/bin/env python3
"""Export every slide of a built carousel HTML to PNG using headless Chrome/Edge.

  export_slides.py carousel.html --out DIR [--scale 2] [--name "اسم الملف"] [--only 1,5]

Needs Chrome or Edge installed (set CHROME_PATH to override). Needs internet once so the
web font loads. Output: "<name> <n>.png" at (width*scale) x (height*scale).
"""
import argparse
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
from pathlib import Path


def find_browser():
    env = os.environ.get("CHROME_PATH")
    if env and Path(env).exists():
        return env
    cands = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    ]
    for c in cands:
        if Path(c).exists():
            return c
    for n in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "microsoft-edge", "chrome"):
        w = shutil.which(n)
        if w:
            return w
    return None


def png_size(p):
    with open(p, "rb") as f:
        head = f.read(24)
    if head[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    return struct.unpack(">II", head[16:24])


def meta(html, name, default=None):
    m = re.search(r'<meta name="%s" content="([^"]*)"' % re.escape(name), html)
    return m.group(1) if m else default


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("html")
    ap.add_argument("--out", required=True)
    ap.add_argument("--scale", type=float, default=2.0)
    ap.add_argument("--name", default=None)
    ap.add_argument("--only", default=None, help="comma list of slide numbers")
    a = ap.parse_args()

    src = Path(a.html).resolve()
    html = src.read_text(encoding="utf-8")
    count = int(meta(html, "slide-count", "0"))
    w, h = (int(x) for x in meta(html, "slide-size", "1080x1440").split("x"))
    if not count:
        print("ما لقيت meta slide-count: ابنِ الملف بـ build.py أول", file=sys.stderr)
        sys.exit(2)
    browser = find_browser()
    if not browser:
        print("ما لقيت Chrome أو Edge. ثبّت واحد أو حدد CHROME_PATH", file=sys.stderr)
        sys.exit(2)
    name = a.name
    if not name:
        t = re.search(r"<title>(.*?)</title>", html)
        name = (t.group(1) if t else "slide").replace("كاروسيل", "").strip() or "slide"
    only = {int(x) for x in a.only.split(",")} if a.only else set(range(1, count + 1))
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)

    tmp = Path(tempfile.mkdtemp(prefix="lc_export_"))
    page = tmp / "c.html"
    shutil.copyfile(src, page)  # ASCII path: avoids browser path issues
    ok = 0
    try:
        for i in range(1, count + 1):
            if i not in only:
                continue
            shot = tmp / ("%d.png" % i)
            cmd = [browser, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                   "--force-device-scale-factor=%g" % a.scale,
                   "--window-size=%d,%d" % (w, h),
                   "--virtual-time-budget=15000",
                   "--screenshot=%s" % shot,
                   page.as_uri() + "?slide=%d" % i]
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120)
            if not shot.exists():
                print("فشل تصدير الشريحة %d" % i, file=sys.stderr)
                continue
            sz = png_size(shot)
            exp = (int(w * a.scale), int(h * a.scale))
            if sz != exp:
                print("تحذير: الشريحة %d المقاس %s والمتوقع %s" % (i, sz, exp))
            final = out / ("%s %d.png" % (name, i))
            shutil.copyfile(shot, final)
            ok += 1
            print("✓ %s (%dx%d)" % (final.name, sz[0], sz[1]) if sz else "✓ %s" % final.name)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("تم تصدير %d من %d" % (ok, len(only)))
    sys.exit(0 if ok == len(only) else 1)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    main()
