#!/usr/bin/env python3
"""Automatic layout check for a built carousel (headless Chrome/Edge, Python 3 stdlib only).

  check_deck.py carousel.html

Renders every slide in the browser and measures: text running over the gold footer line,
text touching the logo, elements outside the frame, text wider than its box, the smallest
font (must be >= 38px) and the name/handle row touching the line or the frame.
Exit code 0 = clean, 1 = issues found, 2 = could not run.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from export_slides import find_browser  # noqa: E402


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    html = Path(sys.argv[1]).resolve()
    if not html.exists():
        print("الملف غير موجود: %s" % html)
        sys.exit(2)
    browser = find_browser()
    if not browser:
        print("ما لقيت Chrome أو Edge. حدد CHROME_PATH")
        sys.exit(2)
    cmd = [browser, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--window-size=1080,1440",
           "--virtual-time-budget=15000", "--dump-dom", html.as_uri() + "?check=1"]
    r = subprocess.run(cmd, capture_output=True, timeout=180)
    dom = r.stdout.decode("utf-8", "replace")
    m = re.search(r'<pre id="__check">(.*?)</pre>', dom, re.S)
    if not m:
        print("ما طلعت نتيجة الفحص (الصفحة ما حمّلت أو الخط ما اشتغل)")
        sys.exit(2)
    import html as h
    data = json.loads(h.unescape(m.group(1)))
    bad = 0
    for s in data:
        if s["issues"]:
            bad += len(s["issues"])
            print("شريحة %d:" % s["slide"])
            for i in s["issues"]:
                print("  - " + i)
    mf = min((s["metrics"].get("minFont", 999) for s in data), default=0)
    print("فحص %d شريحة | أصغر خط %spx | مشاكل: %d" % (len(data), mf, bad))
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    main()
