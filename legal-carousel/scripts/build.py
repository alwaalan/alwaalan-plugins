#!/usr/bin/env python3
"""legal-carousel build tool (Python 3, standard library only).

  build.py carousel  --brand brand.json --deck deck.json --out carousel.html
  build.py dashboard --brand brand.json --news news.json --out news.html [--date "8 نوفمبر 2026"]

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

def cmd_carousel(a):
    brand = load_json(a.brand)
    deck = load_json(a.deck)
    meta = deck.setdefault("meta", {})
    slides = deck.get("slides", [])
    size = brand.get("size", {"w": 1080, "h": 1440})
    tpl = (TPL / "carousel.template.html").read_text(encoding="utf-8")
    title = meta.get("title", "carousel")
    html = (tpl.replace("__BRAND_JSON__", embed_json(brand))
               .replace("__DECK_JSON__", embed_json(deck))
               .replace("__LOGO__", logo_b64(brand, a.brand))
               .replace("__FONT_Q__", font_query(brand))
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
    brand = load_json(a.brand)
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
               .replace("__LOGO__", logo_b64(brand, a.brand))
               .replace("__FONT_Q__", font_query(brand))
               .replace("__DATE__", a.date or ""))
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    print("تم بناء الداشبورد: %s (%d خبر)" % (out, len(news)))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("carousel")
    c.add_argument("--brand", required=True)
    c.add_argument("--deck", required=True)
    c.add_argument("--out", required=True)
    c.set_defaults(fn=cmd_carousel)
    d = sub.add_parser("dashboard")
    d.add_argument("--brand", required=True)
    d.add_argument("--news", required=True)
    d.add_argument("--out", required=True)
    d.add_argument("--date", default="")
    d.set_defaults(fn=cmd_dashboard)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    main()
