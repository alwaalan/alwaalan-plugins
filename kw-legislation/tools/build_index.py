#!/usr/bin/env python3
"""Build the kw-legislation data folder from the compiled PDF.

  build_index.py --pdf kuwait-legislation.pdf --out ../data

Needs `pdftotext` (poppler) on PATH. Splits the PDF into one text file per law using the
running page header (the short law name printed at the top of every page), then builds an
article index (article number -> PDF page + text offset) with a monotone filter.

Run it again whenever you get a newer PDF; the plugin itself never needs pdftotext.
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

BIDI = re.compile(r"[‪-‮‎‏⁦-⁩]")
WS = re.compile(r"[ \t ]+")
IGNORE_FIRST = re.compile(r"^(المواد\s*الصفحة|الصفحة\b|المجموعة|التعديلات حتى|[\d\s]+$)")
OFFICIAL = re.compile(
    r"^(القانون رقم|قانون رقم|المرسوم بقانون رقم|مرسوم بقانون رقم|المرسوم بالقانون رقم|مرسوم بالقانون رقم|"
    r"المرسوم رقم|مرسوم رقم|مرسوم أميري رقم|المرسوم الأميري رقم|القانون)\s*[\(\)]*\s*[\d٠-٩]"
)
ART = re.compile(r"(?<![؀-ۿ])(?:ال)?مادة\s*[\(\)]*\s*([\d٠-٩]{1,4})(\s*مكرر)?")
AR_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")


def clean_line(s):
    s = BIDI.sub("", s).replace("ـ", "")
    return WS.sub(" ", s).strip()


def extract_pages(pdf):
    exe = shutil.which("pdftotext")
    if not exe:
        sys.exit("يحتاج pdftotext (poppler) على الجهاز لبناء الفهرس")
    tmp = Path(tempfile.mkdtemp()) / "raw.txt"
    subprocess.run([exe, "-enc", "UTF-8", str(pdf), str(tmp)], check=False,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    txt = tmp.read_text(encoding="utf-8", errors="replace")
    pages = txt.split("\f")
    if pages and not pages[-1].strip():
        pages.pop()
    return pages


def first_line(page):
    for l in page.split("\n"):
        l = clean_line(l)
        if l:
            return l
    return ""


def segment(pages):
    """Return list of dicts {start,end,name,official} (1-based inclusive pages)."""
    segs = []
    cur = None
    for i, p in enumerate(pages, 1):
        h = first_line(p)
        if not h or IGNORE_FIRST.match(h):
            if cur:
                cur["end"] = i
            continue
        if cur and h == cur["name"]:
            cur["end"] = i
            continue
        cur = {"start": i, "end": i, "name": h, "official": ""}
        segs.append(cur)
    # merge official-title cover pages into the law that follows
    out = []
    i = 0
    while i < len(segs):
        s = segs[i]
        nxt = segs[i + 1] if i + 1 < len(segs) else None
        if OFFICIAL.match(s["name"]) and (s["end"] - s["start"] + 1) <= 3 and nxt and not OFFICIAL.match(nxt["name"]):
            out.append({"start": s["start"], "end": nxt["end"], "name": nxt["name"], "official": s["name"]})
            i += 2
            continue
        if OFFICIAL.match(s["name"]):
            s["official"] = s["name"]
        out.append(s)
        i += 1
    # absorb tiny segments whose header extends the previous header (e.g. "قانون X المادة 34")
    merged = []
    for s in out:
        if merged and (s["end"] - s["start"] + 1) <= 2 and s["name"].startswith(merged[-1]["name"]):
            merged[-1]["end"] = s["end"]
        elif merged and s["name"] == merged[-1]["name"]:
            merged[-1]["end"] = s["end"]
        else:
            merged.append(s)
    return merged


def article_index(text_pages):
    """text_pages: list of (pdf_page, text). Returns (full_text, {art: [pdf_page, offset]})."""
    full = []
    pos = 0
    cands = []
    for pg, t in text_pages:
        marker = "\n⟦صفحة PDF %d⟧\n" % pg
        full.append(marker)
        pos += len(marker)
        for m in ART.finditer(t):
            n = int(m.group(1).translate(AR_DIGITS))
            cands.append((n, bool(m.group(2)), pg, pos + m.start()))
        full.append(t)
        pos += len(t)
    arts = {}
    last = 0
    for n, mk, pg, off in cands:
        if mk:
            key = "%d مكرر" % n
            if key not in arts and n <= last + 1 and n >= last:
                arts[key] = [pg, off]
            continue
        if last < n <= last + 4 and str(n) not in arts:
            arts[str(n)] = [pg, off]
            last = n
    return "".join(full), arts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    out = Path(a.out)
    (out / "laws").mkdir(parents=True, exist_ok=True)
    for f in (out / "laws").glob("*.txt"):
        f.unlink()
    pages = extract_pages(a.pdf)
    segs = segment(pages)
    index = {"source_pages": len(pages), "laws": []}
    for n, s in enumerate(segs, 1):
        tp = []
        for pg in range(s["start"], s["end"] + 1):
            lines = [clean_line(l) for l in pages[pg - 1].split("\n")]
            tp.append((pg, "\n".join(l for l in lines if l)))
        text, arts = article_index(tp)
        fid = "%03d" % n
        (out / "laws" / (fid + ".txt")).write_text(text, encoding="utf-8")
        index["laws"].append({
            "id": fid, "name": s["name"], "official": s["official"],
            "pdf_start": s["start"], "pdf_end": s["end"],
            "chars": len(text), "articles": arts,
        })
    (out / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=1), encoding="utf-8")
    print("laws:", len(index["laws"]), "pages:", len(pages))


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    main()
