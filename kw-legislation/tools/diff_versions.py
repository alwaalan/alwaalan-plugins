#!/usr/bin/env python3
"""Compare two builds of the legislation index and turn the differences into news items.

  diff_versions.py --old data/index.prev.json --new data/index.json [--news-out new_items.json]

Reports: laws added / removed, laws whose article count changed, and the reference date.
With --news-out it writes ready-to-merge news items (id prefix "kwdiff-") for added laws,
each backed by the reference page where the law starts (verdict ok, source = the reference).
Titles come from the law's official title in the reference. A human still writes the angle.
"""
import argparse
import json
import re
import sys
from pathlib import Path

AR = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")


def load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def key(l):
    return re.sub(r"\s+", " ", l["name"]).strip()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--old", required=True)
    ap.add_argument("--new", required=True)
    ap.add_argument("--news-out")
    a = ap.parse_args()
    old, new = load(a.old), load(a.new)
    om = {key(l): l for l in old["laws"]}
    nm = {key(l): l for l in new["laws"]}
    added = [nm[k] for k in nm if k not in om]
    removed = [om[k] for k in om if k not in nm]
    changed = [(nm[k], len(om[k]["articles"]), len(nm[k]["articles"]))
               for k in nm if k in om and len(om[k]["articles"]) != len(nm[k]["articles"])]
    print("المرجع: %s ← %s" % (old.get("source_date", "؟"), new.get("source_date", "؟")))
    print("أُضيف (%d):" % len(added))
    for l in added:
        print("  + %s | %s | ص PDF %d" % (l["name"][:60], (l.get("official") or "")[:70], l["pdf_start"]))
    print("انحذف (%d):" % len(removed))
    for l in removed:
        print("  - %s" % l["name"][:70])
    print("تغيّر عدد المواد المفهرسة (%d):" % len(changed))
    for l, o, n in changed:
        print("  ~ %s: %d ← %d" % (l["name"][:50], o, n))
    if a.news_out:
        items = []
        for l in added:
            title = (l.get("official") or l["name"]).translate(AR)
            title = re.sub(r"\s+", " ", title).strip()
            items.append({
                "id": "kwdiff-%s" % l["id"],
                "cat": "تشريعات",
                "date": new.get("source_date", ""),
                "fit": 2,
                "ver": "ok",
                "verTxt": "من مرجع التشريعات، صفحة %d" % l["pdf_start"],
                "title": title,
                "sum": "قانون أو لائحة أُضيف للمرجع في آخر تحديث (%s). راجع نصه قبل البناء." % new.get("source_date", ""),
                "pts": ["الموضع في المرجع: ص PDF %d إلى %d" % (l["pdf_start"], l["pdf_end"]),
                        "عدد المواد المفهرسة: %d" % len(l["articles"])],
                "angle": "", "pair": "",
                "src": [["مرجع التشريعات الكويتية (kw-legislation)", "https://github.com/alwaalan/alwaalan-plugins"]],
                "law": l["name"],
            })
        Path(a.news_out).write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
        print("كتبت %d خبر مقترح في %s" % (len(items), a.news_out))


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    main()
