#!/usr/bin/env python3
"""legal-carousel build tool (Python 3, standard library only).

  build.py carousel  [--brand brand.json | --profile name] --deck deck.json --out carousel.html [--size 1080x1920]
  build.py dashboard [--brand brand.json | --profile name] --news news.json --out news.html [--date "8 نوفمبر 2026"]
  build.py doctor        (checks Python, Chrome/Edge, Pillow, PyMuPDF, the bundled font, kw-legislation)

carousel: fills templates/carousel.template.html with the brand + slides, then lints the
          slides against the brand's style rules. Exit code 0 even with warnings (read them!).
          Exit code 2 = a hard error (bad JSON, missing file).
dashboard: fills templates/dashboard.template.html with the brand + news items.
"""
import argparse
import base64
import json
import re
import sys
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TPL = ROOT / "templates"

# ---------- helpers ----------

def die(msg):
    print("خطأ: " + msg, file=sys.stderr)
    sys.exit(2)


def load_json(p):
    p = Path(p)
    if not p.exists():
        die("الملف غير موجود: %s" % p)
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        die("JSON غير صالح في %s: %s" % (p, e))


def embed_json(obj):
    s = json.dumps(obj, ensure_ascii=False)
    return s.replace("</", "<\\/").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")


def logo_b64(brand, brand_path):
    lp = brand.get("logo")
    if not lp:
        return ""
    p = Path(lp)
    if not p.is_absolute():
        p = Path(brand_path).resolve().parent / lp
    if not p.exists():
        print("تحذير: الشعار غير موجود: %s (الصفحة بتنبني بدون شعار)" % p)
        return ""
    return base64.b64encode(p.read_bytes()).decode("ascii")


def font_query(brand):
    return urllib.parse.quote_plus(brand.get("font", "Cairo"))


FONT_RANGES = {
    "arabic": "U+0600-06FF,U+0750-077F,U+0870-088E,U+0890-0891,U+0897-08E1,U+08E3-08FF,U+200C-200E,U+2010-2011,U+204F,U+2E41,U+FB50-FDFF,U+FE70-FE74,U+FE76-FEFC",
    "latin-ext": "U+0100-02BA,U+02BD-02C5,U+02C7-02CC,U+02CE-02D7,U+02DD-02FF,U+0304,U+0308,U+0329,U+1D00-1DBF,U+1E00-1E9F,U+1EF2-1EFF,U+2020,U+20A0-20AB,U+20AD-20C4,U+2113,U+2C60-2C7F,U+A720-A7FF",
    "latin": "U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+0304,U+0308,U+0329,U+2000-206F,U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215,U+FEFF,U+FFFD",
}


def font_head(brand):
    """Embed the bundled Cairo font (offline, deterministic). Other fonts load from Google Fonts."""
    name = brand.get("font", "Cairo")
    fdir = ROOT / "fonts"
    if name == "Cairo" and (fdir / "Cairo-arabic.woff2").exists():
        faces = []
        for sub in ("arabic", "latin-ext", "latin"):
            p = fdir / ("Cairo-%s.woff2" % sub)
            if p.exists():
                b64 = base64.b64encode(p.read_bytes()).decode("ascii")
                faces.append("@font-face{font-family:'Cairo';font-style:normal;font-weight:200 1000;font-display:block;"
                             "src:url(data:font/woff2;base64,%s) format('woff2');unicode-range:%s}" % (b64, FONT_RANGES[sub]))
        if faces:
            return "<style>" + "".join(faces) + "</style>"
    return ('<link rel="preconnect" href="https://fonts.googleapis.com">'
            '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
            '<link href="https://fonts.googleapis.com/css2?family=%s:wght@300;400;600;700;800;900&display=swap" rel="stylesheet">'
            % font_query(brand))


# ---------- lint ----------

TAG_RE = re.compile(r"<[^>]+>")
PUNCT = set(list(".,،:;؛«»()\"'!…-–—[]{}"))
ARABIC_INDIC = re.compile(r"[٠-٩]")


def iter_texts(slide):
    """Yield (field, text) for every visible string in a slide."""
    for k, v in slide.items():
        if k in ("type", "icon", "titleSize", "alt"):
            continue
        if isinstance(v, str):
            yield k, v
        elif isinstance(v, list):
            for item in v:
                if isinstance(item, str):
                    yield k, item
                elif isinstance(item, list):
                    for sub in item:
                        if isinstance(sub, str):
                            yield k, sub
                elif isinstance(item, dict):
                    for sub in item.values():
                        if isinstance(sub, str):
                            yield k, sub


def strip(t):
    t = TAG_RE.sub(" ", t)
    t = re.sub(r"(?<=\d)[.,](?=\d)", "", t)  # decimals like 3.5 are fine
    return t


def lint(deck, brand):
    style = brand.get("style", {})
    warns = []
    slides = deck.get("slides", [])
    n = len(slides)
    if n < 4 or n > 10:
        warns.append("عدد الشرائح %d: المفضل بين 6 و10 (10 هو حد النشر الآلي لانستقرام)" % n)
    types = [s.get("type") for s in slides]
    if not slides or types[0] != "cover":
        warns.append("الشريحة الأولى لازم تكون type=cover")
    if "save" not in types:
        warns.append("ما فيه شريحة save (احفظ البوست + رقم الاستشارات)")
    if "share" not in [s.get("type") for s in slides] and not any(s.get("icon") == "plane" for s in slides):
        warns.append("ما فيه شريحة مشاركة (icon=plane)")
    cover = slides[0] if slides else {}
    if cover.get("type") == "cover":
        h1 = cover.get("h1", [])
        if isinstance(h1, list) and len(h1) > 2:
            warns.append("عنوان الغلاف أكثر من سطرين")

    policy = style.get("punctuation", "question-only")
    word_map = style.get("wordMap", {})
    tags_num = style.get("tagNumbersOnly", True)
    allowed_tags = set(style.get("allowedTagWords", ["شاركها", "احفظها"]))

    for i, s in enumerate(slides, 1):
        for field, text in iter_texts(s):
            plain = strip(text)
            if policy == "question-only" and field not in ("tag",):
                bad = sorted({c for c in plain if c in PUNCT})
                if bad:
                    warns.append("شريحة %d (%s): علامات ترقيم ممنوعة %s في «%s»" % (i, field, " ".join(bad), plain.strip()[:40]))
            if ARABIC_INDIC.search(plain):
                warns.append("شريحة %d (%s): أرقام عربية-هندية، المطلوب أرقام غربية 1 2 3" % (i, field))
            for wrong, right in word_map.items():
                if re.search(r"(?<![\u0600-\u06FF])%s(?![\u0600-\u06FF])" % re.escape(wrong), plain):
                    warns.append("شريحة %d (%s): استخدم «%s» بدل «%s»" % (i, field, right, wrong))
        tag = s.get("tag", "")
        if tags_num and tag and not (tag.isdigit() or tag.startswith("#") or tag in allowed_tags):
            warns.append("شريحة %d: التاج «%s» لازم يكون رقم بس (أو كلمة مسموحة)" % (i, tag))
        if s.get("type") in ("point", "list", "chips", "steps"):
            title = strip(s.get("title", ""))
            if len(title) > 30 and not s.get("titleSize"):
                warns.append("شريحة %d: العنوان طويل (%d حرف)، قصّره أو حط titleSize أصغر" % (i, len(title)))
        if s.get("type") == "point":
            body = strip(s.get("body", ""))
            if len(body) > 150:
                warns.append("شريحة %d: النص طويل (%d حرف)، فكرة وحدة بالشريحة" % (i, len(body)))
    meta = deck.get("meta", {})
    if not meta.get("sources"):
        warns.append("ما فيه meta.sources (مصادر الخبر)")
    if not meta.get("notes"):
        warns.append("ما فيه meta.notes (نقاط التحقق قبل النشر)")
    return warns


# ---------- commands ----------

def brand_path(a):
    """--brand file, or --profile name (.legal-carousel/brands/<name>.json), or .legal-carousel/brand.json."""
    if getattr(a, "brand", None):
        return Path(a.brand)
    base = Path(getattr(a, "project", None) or ".") / ".legal-carousel"
    if getattr(a, "profile", None):
        return base / "brands" / (a.profile + ".json")
    return base / "brand.json"


def cmd_carousel(a):
    bp = brand_path(a)
    brand = load_json(bp)
    deck = load_json(a.deck)
    meta = deck.setdefault("meta", {})
    slides = deck.get("slides", [])
    if getattr(a, "size", None):
        try:
            w, h = (int(x) for x in a.size.lower().split("x"))
        except ValueError:
            die("--size لازم يكون مثل 1080x1920")
        brand["size"] = {"w": w, "h": h}
    size = brand.get("size", {"w": 1080, "h": 1440})
    tpl = (TPL / "carousel.template.html").read_text(encoding="utf-8")
    title = meta.get("title", "carousel")
    html = (tpl.replace("__BRAND_JSON__", embed_json(brand))
               .replace("__DECK_JSON__", embed_json(deck))
               .replace("__LOGO__", logo_b64(brand, bp))
               .replace("__FONT_HEAD__", font_head(brand))
               .replace("__TITLE__", "كاروسيل " + title)
               .replace("__COUNT__", str(len(slides)))
               .replace("__SIZE__", "%dx%d" % (size["w"], size["h"])))
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    print("تم البناء: %s (%d شريحة)" % (out, len(slides)))
    warns = lint(deck, brand)
    if warns:
        print("\nملاحظات الفحص (%d):" % len(warns))
        for w in warns:
            print(" - " + w)
    else:
        print("فحص القواعد: ما فيه ملاحظات ✓")


def cmd_dashboard(a):
    bp = brand_path(a)
    brand = load_json(bp)
    news = load_json(a.news)
    if isinstance(news, dict):
        news = news.get("items", [])
    ids = [n.get("id") for n in news]
    if len(ids) != len(set(ids)):
        die("فيه id مكرر بين الأخبار")
    miss = [n.get("id") for n in news if not all(k in n for k in ("id", "cat", "date", "title", "sum", "pts", "src"))]
    if miss:
        die("أخبار ناقصة حقول (id/cat/date/title/sum/pts/src): %s" % miss)
    for n in news:
        n.setdefault("fit", 1)
        n.setdefault("ver", "warn")
        n.setdefault("verTxt", "تحقق من المصدر قبل النشر")
        n.setdefault("angle", "")
        n.setdefault("pair", "")
    tpl = (TPL / "dashboard.template.html").read_text(encoding="utf-8")
    html = (tpl.replace("__BRAND_JSON__", embed_json(brand))
               .replace("__NEWS_JSON__", embed_json(news))
               .replace("__LOGO__", logo_b64(brand, bp))
               .replace("__FONT_HEAD__", font_head(brand))
               .replace("__DATE__", a.date or ""))
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    print("تم بناء الداشبورد: %s (%d خبر)" % (out, len(news)))


def cmd_doctor(a):
    """Check the machine: Python, browser, Pillow, PyMuPDF, bundled font, legislation plugin."""
    import glob
    import importlib
    import os
    import shutil
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from export_slides import find_browser
    rows = []

    def row(ok, name, fix=""):
        rows.append((ok, name, fix))

    row(sys.version_info >= (3, 8), "Python %d.%d" % sys.version_info[:2], "ثبّت Python 3.8 أو أحدث")
    b = find_browser()
    row(bool(b), "Chrome أو Edge" + (": " + b if b else ""), "ثبّت Chrome أو Edge (ضروري لتصدير PNG وفحص التصميم) أو حدد CHROME_PATH")
    try:
        importlib.import_module("PIL")
        row(True, "Pillow (لتجهيز الشعار)")
    except ImportError:
        row(False, "Pillow (لتجهيز الشعار فقط)", "python -m pip install pillow")
    try:
        try:
            importlib.import_module("pymupdf")
        except ImportError:
            importlib.import_module("fitz")
        row(True, "PyMuPDF (لعرض صفحات التشريعات)")
    except ImportError:
        row(False, "PyMuPDF (لعرض صفحات التشريعات، اختياري)", "python -m pip install pymupdf")
    fonts = ROOT / "fonts" / "Cairo-arabic.woff2"
    row(fonts.exists(), "خط Cairo المرفق (يشتغل بدون إنترنت)", "ملفات fonts ناقصة: أعد تنصيب الإضافة")
    home = Path(os.path.expanduser("~"))
    cands = glob.glob(str(home / ".claude" / "plugins" / "cache" / "*" / "kw-legislation" / "*" / "data" / "index.json"))
    sib = ROOT.parent / "kw-legislation" / "data" / "index.json"
    found = cands[-1] if cands else (str(sib) if sib.exists() else "")
    row(bool(found), "إضافة kw-legislation (مرجع التشريعات)" + (": " + found if found else ""),
        "اختيارية: بدونها ما تتحقق الإضافة من أرقام المواد")
    row(bool(shutil.which("pdftotext")), "pdftotext (فقط لو تبي تحدّث ملف التشريعات)", "اختياري: ثبّت poppler")
    bad = 0
    for ok, name, fix in rows:
        print(("✓ " if ok else "✗ ") + name + ("" if ok or not fix else "\n    الحل: " + fix))
        if not ok and "اختياري" not in name and "فقط" not in name:
            bad += 1
    print("\nجاهز" if not bad else "\nفيه %d نقص يعطّل شي أساسي" % bad)

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("carousel")
    c.add_argument("--brand")
    c.add_argument("--profile")
    c.add_argument("--project")
    c.add_argument("--deck", required=True)
    c.add_argument("--out", required=True)
    c.add_argument("--size", help="مثل 1080x1920 لتيك توك")
    c.set_defaults(fn=cmd_carousel)
    d = sub.add_parser("dashboard")
    d.add_argument("--brand")
    d.add_argument("--profile")
    d.add_argument("--project")
    d.add_argument("--news", required=True)
    d.add_argument("--out", required=True)
    d.add_argument("--date", default="")
    d.set_defaults(fn=cmd_dashboard)
    k = sub.add_parser("doctor")
    k.set_defaults(fn=cmd_doctor)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    main()
