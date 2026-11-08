#!/usr/bin/env python3
"""Cross-check news items against the bundled Kuwaiti legislation (Python 3, stdlib only).

  enrich_news.py --news .legal-carousel/news.json [--out news.json] [--data <kw-legislation>/data]

For every item it:
  1. finds decree/law numbers mentioned in title/summary/points ("رقم 102 لسنة 2026"),
  2. looks for each one in the reference text. status: "found" (it is a law's own title in the
     reference, with the PDF page), "mentioned" (only cited inside another law's text), "missing",
  3. attaches optional article references (item["law"] + item["articles"]) with their pages,
  4. writes item["legis"] = {checked, source_date, decrees[], refs[], verdict}.

verdict follows the PRIMARY decree (the one in the title, else the first mentioned): "ok" (it is a law's own
title in the reference), "partial" (only cited/amended inside another law), "missing" (not in the
reference: may be newer or outside the compilation), "none" (no decree number mentioned).
It never edits titles or facts. It only adds evidence the dashboard can show.
"""
import argparse
import datetime
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AR = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
DECREE = re.compile(r"(\d{1,4})\s*[\(\)]*\s*لسنة\s*(\d{4})")
PAGE_MARK = re.compile(r"⟦صفحة PDF (\d+)⟧")


def norm_digits(s):
    return s.translate(AR)


def load(data):
    ix = json.loads((data / "index.json").read_text(encoding="utf-8"))
    return ix


def build_decree_map(data, ix):
    """decree 'N/Y' -> list of {id,name,pdf_page,title} (title=True when seen near the law's start)."""
    out = {}
    for law in ix["laws"]:
        text = norm_digits((data / "laws" / (law["id"] + ".txt")).read_text(encoding="utf-8"))
        first_page = law["pdf_start"]
        pos_pages = [(m.start(), int(m.group(1))) for m in PAGE_MARK.finditer(text)]
        for m in DECREE.finditer(text):
            key = "%d/%s" % (int(m.group(1)), m.group(2))
            pg = first_page
            for off, p in pos_pages:
                if off <= m.start():
                    pg = p
                else:
                    break
            ls = text.rfind(chr(10), 0, m.start()) + 1
            title_line = bool(re.match(r"\s*(?:ال)?(?:مرسوم|قانون|قرار|لائحة)", text[ls:m.start()] + "x")) and (m.start() - ls) < 70
            lst = out.setdefault(key, [])
            if not any(x["id"] == law["id"] and x["pdf_page"] == pg for x in lst):
                lst.append({"id": law["id"], "name": law["name"], "pdf_page": pg,
                            "own": title_line and (pg - law["pdf_start"]) <= 1})
    return out


def find_law(ix, q):
    nq = re.sub(r"\s+", " ", q).strip()
    for l in ix["laws"]:
        if l["name"] == nq or l["id"] == nq.zfill(3):
            return l
    for l in ix["laws"]:
        if nq in l["name"] or nq in l.get("official", ""):
            return l
    return None


def enrich(item, ix, dmap):
    text = norm_digits(" ".join([item.get("title", ""), item.get("sum", "")] + list(item.get("pts", []))))
    seen = []
    for m in DECREE.finditer(text):
        key = "%d/%s" % (int(m.group(1)), m.group(2))
        if key not in seen:
            seen.append(key)
    decrees = []
    for key in seen:
        hits = dmap.get(key, [])
        own = [h for h in hits if h["own"]]
        use = own or hits
        status = "found" if own else ("mentioned" if hits else "missing")
        decrees.append({
            "ref": key,
            "status": status,
            "laws": [{"id": h["id"], "name": h["name"], "pdf_page": h["pdf_page"]} for h in use[:3]],
        })
    refs = []
    q = item.get("law")
    if q:
        law = find_law(ix, q)
        if law:
            for a in item.get("articles", []):
                k = str(a)
                if k in law["articles"]:
                    refs.append({"law": law["name"], "law_id": law["id"], "article": k,
                                 "pdf_page": law["articles"][k][0]})
                else:
                    refs.append({"law": law["name"], "law_id": law["id"], "article": k, "pdf_page": None})
        else:
            refs.append({"law": q, "law_id": None, "article": None, "pdf_page": None})
    primary = None
    title_keys = ["%d/%s" % (int(m.group(1)), m.group(2)) for m in DECREE.finditer(norm_digits(item.get("title", "")))]
    for d in decrees:
        if d["ref"] in title_keys:
            primary = d
            break
    if primary is None and decrees:
        primary = decrees[0]
    if not decrees:
        verdict = "none"
    else:
        verdict = {"found": "ok", "mentioned": "partial", "missing": "missing"}[primary["status"]]
    item["legis"] = {
        "checked": datetime.date.today().isoformat(),
        "source_date": ix.get("source_date", ""),
        "decrees": decrees,
        "primary": primary["ref"] if primary else "",
        "refs": refs,
        "verdict": verdict,
    }
    return item


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--news", required=True)
    ap.add_argument("--out")
    ap.add_argument("--data", default=str(ROOT / "data"))
    a = ap.parse_args()
    data = Path(a.data)
    ix = load(data)
    dmap = build_decree_map(data, ix)
    p = Path(a.news)
    news = json.loads(p.read_text(encoding="utf-8"))
    items = news["items"] if isinstance(news, dict) else news
    for it in items:
        enrich(it, ix, dmap)
    out = Path(a.out) if a.out else p
    out.write_text(json.dumps(news, ensure_ascii=False, indent=2), encoding="utf-8")
    ok = {"ok": 0, "partial": 0, "missing": 0, "none": 0}
    for it in items:
        ok[it["legis"]["verdict"]] += 1
        d = ", ".join("%s:%s" % (x["ref"], x["status"]) for x in it["legis"]["decrees"]) or "-"
        print("%-9s %-8s %s" % (it.get("id", "?"), it["legis"]["verdict"], d))
    print("\nملخص:", ok, "| تاريخ المرجع:", ix.get("source_date", "غير محدد"))


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    main()
