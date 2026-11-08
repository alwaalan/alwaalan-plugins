#!/usr/bin/env python3
"""Look up Kuwaiti legislation from the bundled, indexed PDF text (Python 3, stdlib only).

  find_article.py list [--grep كلمة]
  find_article.py article <قانون أو رقم الملف> <رقم المادة> [--full]
  find_article.py search "كلمات" [--law قانون] [--top 8]
  find_article.py page <رقم صفحة PDF> [--out صورة.png] [--dpi 110]
  find_article.py amendments <قانون> [--year 2026]   (هوامش التعديل: مضافة/معدلة/مستبدلة/ملغاة بموجب ...)

IMPORTANT: the text was machine-extracted from the PDF and can lose letters (the letter م
inside some ligatures, e.g. "الأعمال" -> "الأعال"). Use the text to FIND the article and its
page; before quoting words or relying on a number, render the page with `page` and read it.
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
PDF = ROOT / "source" / "kuwait-legislation.pdf"
DIAC = re.compile(r"[ؐ-ًؚ-ٰٟـ]")
PAGE_MARK = re.compile(r"⟦صفحة PDF (\d+)⟧")


def norm(s):
    s = DIAC.sub("", s)
    s = re.sub("[أإآٱ]", "ا", s)
    s = s.replace("ى", "ي").replace("ة", "ه")
    return re.sub(r"\s+", " ", s).strip().lower()


def load_index():
    p = DATA / "index.json"
    if not p.exists():
        sys.exit("data/index.json غير موجود")
    return json.loads(p.read_text(encoding="utf-8"))


def law_text(law):
    return (DATA / "laws" / (law["id"] + ".txt")).read_text(encoding="utf-8")


def pick_law(ix, q):
    q = q.strip()
    if re.fullmatch(r"\d{1,3}", q):
        for l in ix["laws"]:
            if l["id"] == q.zfill(3):
                return l
    nq = norm(q)
    exact = [l for l in ix["laws"] if norm(l["name"]) == nq]
    if exact:
        return exact[0]
    hits = [l for l in ix["laws"] if nq in norm(l["name"]) or nq in norm(l.get("official", ""))]
    if len(hits) == 1:
        return hits[0]
    if not hits:
        sys.exit("ما لقيت قانون يطابق «%s». جرّب: find_article.py list --grep كلمة" % q)
    print("أكثر من قانون يطابق «%s»، حدد رقم الملف:" % q)
    for l in hits:
        print("  %s  %s  (ص PDF %d-%d)" % (l["id"], l["name"], l["pdf_start"], l["pdf_end"]))
    sys.exit(3)


def page_of(text, offset):
    last = None
    for m in PAGE_MARK.finditer(text, 0, offset + 1):
        last = int(m.group(1))
    return last



FOOT_VERB = re.compile("(مضاف|معدل|مستبدل|ملغ|استبدل|أضيف|اضيف|عدلت|مضافه|معدله)")
FOOT_REF = re.compile(r"(?:رقم)?\s*([\d٠-٩]{1,4})\s*لسنة\s*([\d٠-٩]{4})")
AR = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")


def page_bodies(text):
    parts = PAGE_MARK.split(text)
    return {int(parts[i]): parts[i + 1] for i in range(1, len(parts) - 1, 2)}


def notes_in(body):
    out = []
    for line in body.split(chr(10)):
        l = line.strip()
        if FOOT_VERB.search(l) and FOOT_REF.search(l) and ("بموجب" in l or "وفق" in l):
            out.append(re.sub(r"\s+", " ", l))
    return out


def cmd_amendments(a):
    ix = load_index()
    law = pick_law(ix, a.law)
    bodies = page_bodies(law_text(law))
    rows = []
    counts = {}
    for pg in sorted(bodies):
        for n in notes_in(bodies[pg]):
            rows.append((pg, n))
            for m in FOOT_REF.finditer(n.translate(AR)):
                k = "%d/%s" % (int(m.group(1)), m.group(2))
                counts[k] = counts.get(k, 0) + 1
    if a.year:
        rows = [(p, n) for p, n in rows if a.year in n.translate(AR)]
    print("القانون: %s | هوامش تعديل: %d" % (law["name"], len(rows)))
    if counts:
        print("القوانين والمراسيم المذكورة بالهوامش: " + "، ".join(
            "%s (%d)" % (k, v) for k, v in sorted(counts.items(), key=lambda kv: -kv[1])[:12]))
    print("ملاحظة: الهامش يظهر بصفحته، وقد يخص مادة غير المادة المجاورة. تحقق بصورة الصفحة.")
    print("-" * 60)
    for pg, n in rows[: a.top]:
        print("ص PDF %d: %s" % (pg, n[:220]))
    if len(rows) > a.top:
        print("… (%d هامش إضافي، استخدم --top)" % (len(rows) - a.top))


def cmd_list(a):
    ix = load_index()
    g = norm(a.grep) if a.grep else None
    for l in ix["laws"]:
        if g and g not in norm(l["name"]) and g not in norm(l.get("official", "")):
            continue
        print("%s | %s | ص PDF %d-%d | %d مادة مفهرسة%s" % (
            l["id"], l["name"], l["pdf_start"], l["pdf_end"], len(l["articles"]),
            (" | " + l["official"]) if l.get("official") else ""))
    print("\nمصدر: %d صفحة PDF" % ix["source_pages"])


def cmd_article(a):
    ix = load_index()
    law = pick_law(ix, a.law)
    key = str(a.number).strip()
    arts = law["articles"]
    if key not in arts:
        print("المادة %s غير مفهرسة في «%s». المواد المفهرسة: %s ... %s" % (
            key, law["name"], list(arts)[:3], list(arts)[-3:]))
        print("جرّب البحث: find_article.py search \"كلمات\" --law \"%s\"" % law["name"])
        sys.exit(1)
    text = law_text(law)
    pg, off = arts[key]
    later = sorted(o for _, o in arts.values() if o > off)
    end = later[0] if later else len(text)
    body = text[off:end]
    if not a.full and len(body) > 3500:
        body = body[:3500] + "\n… (مقتطع، استخدم --full)"
    pages = sorted({int(m) for m in PAGE_MARK.findall(text[off:end])} | {pg})
    print("القانون: %s%s" % (law["name"], (" — " + law["official"]) if law.get("official") else ""))
    print("المادة: %s | صفحة PDF: %s" % (key, "، ".join(map(str, pages))))
    print("⚠ نص مستخرج آليا قد يفقد حروف (مثل م). تحقق بصورة الصفحة قبل الاقتباس: find_article.py page %d" % pg)
    print("-" * 60)
    print(body.strip())
    bodies = page_bodies(text)
    notes = []
    for p in pages:
        for n in notes_in(bodies.get(p, "")):
            notes.append((p, n))
    if notes:
        print("-" * 60)
        print("هوامش التعديل بصفحات المادة (قد يخص بعضها مادة ثانية بنفس الصفحة، تحقق بصورة الصفحة):")
        for p, n in notes[:8]:
            print("  ص PDF %d: %s" % (p, n[:200]))


def cmd_search(a):
    ix = load_index()
    words = [w for w in norm(a.query).split() if w]
    if not words:
        sys.exit("اكتب كلمات للبحث")
    laws = ix["laws"]
    if a.law:
        laws = [pick_law(ix, a.law)]
    results = []
    for law in laws:
        text = law_text(law)
        ntext = norm(text)
        # offsets differ after normalisation, so scan the raw text in windows instead
        arts = sorted(((o, k, pg) for k, (pg, o) in law["articles"].items()))
        for i, (o, k, pg) in enumerate(arts):
            end = arts[i + 1][0] if i + 1 < len(arts) else len(text)
            seg = norm(text[o:end])
            if all(w in seg for w in words):
                score = sum(seg.count(w) for w in words)
                pos = seg.find(words[0])
                snippet = re.sub(r"\s+", " ", seg[max(0, pos - 60):pos + 140])
                results.append((score, law, k, pg, snippet))
    results.sort(key=lambda r: -r[0])
    if not results:
        print("ما لقيت نتائج تحتوي كل الكلمات. جرّب كلمات أقل أو أبسط.")
        return
    for score, law, k, pg, sn in results[: a.top]:
        print("• %s — مادة %s — ص PDF %d — تطابق %d\n   …%s…" % (law["name"], k, pg, score, sn))
    print("\nملاحظة: المقتطف مطبّع (بدون همزات) ومستخرج آليا. افتح المادة بـ article ثم تحقق بصورة الصفحة.")


def cmd_page(a):
    if not PDF.exists():
        sys.exit("ملف PDF غير موجود: %s" % PDF)
    out = Path(a.out) if a.out else Path("page-%d.png" % a.page)
    try:
        try:
            import pymupdf as fitz  # type: ignore
        except ImportError:
            import fitz  # type: ignore
        doc = fitz.open(str(PDF))
        if not 1 <= a.page <= len(doc):
            sys.exit("رقم الصفحة خارج النطاق 1-%d" % len(doc))
        doc[a.page - 1].get_pixmap(dpi=a.dpi).save(str(out))
        print("تم: %s" % out)
        return
    except ImportError:
        pass
    exe = shutil.which("pdftoppm")
    if exe:
        base = str(out.with_suffix(""))
        subprocess.run([exe, "-png", "-r", str(a.dpi), "-f", str(a.page), "-l", str(a.page), "-singlefile", str(PDF), base], check=True)
        print("تم: %s.png" % base)
        return
    sys.exit("لعرض صورة الصفحة ثبّت PyMuPDF: python -m pip install pymupdf  (أو poppler/pdftoppm)")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("list"); s.add_argument("--grep"); s.set_defaults(fn=cmd_list)
    s = sub.add_parser("article"); s.add_argument("law"); s.add_argument("number"); s.add_argument("--full", action="store_true"); s.set_defaults(fn=cmd_article)
    s = sub.add_parser("search"); s.add_argument("query"); s.add_argument("--law"); s.add_argument("--top", type=int, default=8); s.set_defaults(fn=cmd_search)
    s = sub.add_parser("page"); s.add_argument("page", type=int); s.add_argument("--out"); s.add_argument("--dpi", type=int, default=110); s.set_defaults(fn=cmd_page)
    s = sub.add_parser("amendments"); s.add_argument("law"); s.add_argument("--year"); s.add_argument("--top", type=int, default=25); s.set_defaults(fn=cmd_amendments)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    main()
