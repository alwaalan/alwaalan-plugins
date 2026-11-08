#!/usr/bin/env python3
"""voice_video.py: من تسجيل صوتي (أو فيديو كلام) إلى فيديو 9:16 جاهز.

الأوامر:
  doctor                       فحص الجهاز (ffmpeg, faster-whisper, الخط)
  analyze <ملف> --out <فولدر>   تفريغ الكلام بتوقيت كل كلمة + اقتراح القص (words.json, plan.json, transcript.txt)
  render  <فولدر>              يطبق القص، يحسّن الصوت، يركّب كابشن وهوية، يطلع final.mp4

كل شي محلي على جهازه: الصوت ما يطلع لأي خدمة. القص يتحدد بملف plan.json
وتقدر تعدله (أو تضيف drop) قبل render.
"""
import argparse, json, math, os, re, shutil, subprocess, sys, wave
from pathlib import Path

HERE = Path(__file__).resolve().parent
PLUGIN = HERE.parent
FONTS_SRC = PLUGIN / "fonts"

FILLERS = {"اه", "آه", "ااه", "اممم", "امم", "ممم", "مم", "هم", "ايه", "إيه", "اي", "ايوه", "اها", "آها", "اااا", "ااا", "ههه"}
PUNCT = re.compile(r"[\.,،؛;:!\"'“”«»()\[\]\-–—…ـ]")


def run(cmd, cwd=None, check=True, quiet=True):
    r = subprocess.run(cmd, cwd=cwd, capture_output=quiet, text=True, encoding="utf-8", errors="replace")
    if check and r.returncode != 0:
        sys.exit("فشل الأمر:\n" + " ".join(map(str, cmd)) + "\n" + (r.stderr or "")[-1800:])
    return r


def ffmpeg_path():
    p = shutil.which("ffmpeg")
    if not p:
        sys.exit("ffmpeg مو منصّب. نصّبه: winget install Gyan.FFmpeg")
    return p


def hex2ass(h):
    h = h.lstrip("#")
    r, g, b = h[0:2], h[2:4], h[4:6]
    return f"&H00{b}{g}{r}&".upper().replace("&H", "&H")


def load_brand(project):
    for cand in [Path(project) / ".legal-carousel" / "brand.json", Path(project) / "brand.json"]:
        if cand.exists():
            return json.loads(cand.read_text(encoding="utf-8")), cand.parent
    return None, None


# ---------------------------------------------------------------- doctor
def cmd_doctor(_):
    ok = True
    print("ffmpeg:", shutil.which("ffmpeg") or "مفقود"); ok &= bool(shutil.which("ffmpeg"))
    print("ffprobe:", shutil.which("ffprobe") or "مفقود (يجي مع ffmpeg، تأكد إنهم بنفس المجلد وبالـ PATH)"); ok &= bool(shutil.which("ffprobe"))
    if shutil.which("ffmpeg"):
        flt = run(["ffmpeg", "-hide_banner", "-filters"]).stdout
        for f in ("afftdn", "loudnorm", "acompressor", "ass", "showwaves"):
            has = re.search(rf"\b{f}\b", flt) is not None
            print(f"  فلتر {f}:", "موجود" if has else "مفقود"); ok &= has
    try:
        import faster_whisper
        print("faster-whisper:", faster_whisper.__version__)
    except Exception:
        print("faster-whisper: مفقود. نصّبه: python -m pip install faster-whisper"); ok = False
    try:
        import numpy; print("numpy:", numpy.__version__)
    except Exception:
        print("numpy: مفقود"); ok = False
    try:
        import fontTools, brotli  # noqa
        print("fonttools+brotli: موجود")
    except Exception:
        print("fonttools/brotli: مفقود (يحتاجه الخط). نصّبه: python -m pip install fonttools brotli"); ok = False
    print("النتيجة:", "جاهز" if ok else "ناقص شي")
    return 0 if ok else 1


# ---------------------------------------------------------------- audio helpers
def to_wav16k(src, dst):
    run([ffmpeg_path(), "-y", "-i", str(src), "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(dst)])


def duration(path):
    r = run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(path)])
    return float(r.stdout.strip())


def has_video(path):
    r = run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=codec_type", "-of", "csv=p=0", str(path)], check=False)
    return "video" in (r.stdout or "")


def load_energy(wav_path, hop=0.01):
    import numpy as np
    with wave.open(str(wav_path), "rb") as w:
        sr = w.getframerate()
        data = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype("float32") / 32768.0
    n = int(sr * hop)
    m = len(data) // n
    frames = data[: m * n].reshape(m, n)
    return (frames ** 2).mean(axis=1) ** 0.5, hop


def snap_quiet(energy, hop, a, b):
    """أهدأ نقطة داخل الفاصل [a,b] بالثواني (نقطة قص ما تقطع حرف)."""
    import numpy as np
    i0, i1 = max(0, int(a / hop)), min(len(energy), int(b / hop) + 1)
    if i1 - i0 < 1:
        return (a + b) / 2
    return (i0 + int(np.argmin(energy[i0:i1]))) * hop + hop / 2


# ---------------------------------------------------------------- analyze
def cmd_analyze(a):
    src = Path(a.input)
    if not src.exists():
        sys.exit(f"ما لقيت الملف: {src}")
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    wav = out / "_analysis.wav"
    to_wav16k(src, wav)
    total = duration(src)

    try:
        from faster_whisper import WhisperModel
    except Exception:
        sys.exit("faster-whisper مو منصّب: python -m pip install faster-whisper")
    print(f"تفريغ الصوت بموديل {a.model} (أول مرة ينزّل الموديل، والتفريغ على المعالج يأخذ وقت)...", flush=True)
    model = WhisperModel(a.model, device="cpu", compute_type="int8")
    prompt = a.prompt or "تسجيل لمحامي كويتي يشرح قانون بلهجة كويتية."
    import numpy as np
    with wave.open(str(wav), "rb") as wf:  # نمرر الصوت كمصفوفة (يتجاوز فك الترميز بمكتبة av)
        audio = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16).astype("float32") / 32768.0
    segs, info = model.transcribe(audio, language=a.lang, word_timestamps=True, vad_filter=False,
                                  initial_prompt=prompt, condition_on_previous_text=False, beam_size=5)
    words = []
    for s in segs:
        for w in (s.words or []):
            t = w.word.strip()
            if t:
                words.append({"w": t, "s": round(w.start, 3), "e": round(w.end, 3), "p": round(float(w.probability), 3)})
    if not words:
        sys.exit("ما طلع كلام من الملف. تأكد إن فيه صوت.")
    (out / "words.json").write_text(json.dumps({"source": str(src), "duration": total, "words": words}, ensure_ascii=False, indent=1), encoding="utf-8")

    plan = build_plan(words, total, wav, a)
    (out / "plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=1), encoding="utf-8")
    (out / "transcript.txt").write_text(make_transcript(words), encoding="utf-8")
    wav.unlink(missing_ok=True)

    cut = sum(c["e"] - c["s"] for c in plan["cuts"])
    print(f"\nالمدة الأصلية {total:.1f}ث | كلمات {len(words)} | مقترح قص {cut:.1f}ث ({len(plan['cuts'])} قطعة)")
    print("الملفات: transcript.txt (للمراجعة)، plan.json (القص، عدّله لو تبي)، words.json")
    low = [w["w"] for w in words if w["p"] < 0.5]
    if low:
        print(f"كلمات ثقة التفريغ فيها واطية (راجعها): {' | '.join(low[:15])}")
    return 0


def make_transcript(words):
    lines, cur, last = [], [], 0.0
    for w in words:
        if cur and w["s"] - last > 0.7:
            lines.append(cur); cur = []
        cur.append(w); last = w["e"]
    if cur: lines.append(cur)
    return "\n".join(f"[{l[0]['s']:7.2f}-{l[-1]['e']:7.2f}] " + " ".join(x["w"] for x in l) for l in lines) + "\n"


def build_plan(words, total, wav, a):
    """يحدد الأجزاء المحذوفة (cuts) بوقت الملف الأصلي."""
    energy, hop = load_energy(wav)
    cuts = []  # {s,e,why}
    keep_gap = a.keep_gap       # أقصى وقفة تبقى بين الكلمات
    pad = 0.05
    # وقفات بين الكلمات + بداية ونهاية
    first = words[0]["s"]
    if first > 0.25:
        cuts.append({"s": 0.0, "e": round(snap_quiet(energy, hop, max(0, first - 0.3), first - 0.04), 3), "why": "بداية صامتة"})
    for x, y in zip(words, words[1:]):
        gap = y["s"] - x["e"]
        if gap > a.max_gap:
            # نقص من الوسط ونخلي وقفة قصيرة طبيعية؛ نقطتا القص تنزلان على أهدأ لحظة
            lo, hi = x["e"] + pad, y["s"] - pad
            c0, c1 = lo + keep_gap / 2, hi - keep_gap / 2
            if c1 - c0 > 0.04:
                c0 = snap_quiet(energy, hop, c0 - 0.03, c0 + 0.03)
                c1 = snap_quiet(energy, hop, c1 - 0.03, c1 + 0.03)
                if c1 - c0 > 0.04:
                    cuts.append({"s": round(c0, 3), "e": round(c1, 3), "why": f"وقفة {gap:.2f}ث"})
    last = words[-1]["e"]
    if total - last > 0.4:
        cuts.append({"s": round(snap_quiet(energy, hop, last + 0.05, last + 0.25), 3), "e": round(total, 3), "why": "نهاية صامتة"})
    # حشو (اختياري) وتكرار كلمة
    flagged = []
    for i, w in enumerate(words):
        clean = PUNCT.sub("", w["w"]).strip()
        is_filler = clean in FILLERS
        is_rep = i + 1 < len(words) and clean and clean == PUNCT.sub("", words[i + 1]["w"]).strip() and len(clean) > 1
        if is_filler or is_rep:
            flagged.append({"s": round(max(0, w["s"] - 0.02), 3), "e": round(w["e"] + 0.04, 3),
                            "word": w["w"], "why": "حشو" if is_filler else "تكرار"})
    if a.cut_fillers:
        for f in flagged:
            cuts.append({"s": f["s"], "e": f["e"], "why": f["why"] + ": " + f["word"]})
        flagged = []
    cuts.sort(key=lambda c: c["s"])
    return {"cuts": merge_ranges(cuts), "suggested_not_applied": flagged,
            "settings": {"max_gap": a.max_gap, "keep_gap": a.keep_gap},
            "note": "cuts تتطبق عند render. انقل من suggested_not_applied إلى cuts اللي تبيه، أو أضف {\"s\":..,\"e\":..,\"why\":..} بوقت الملف الأصلي."}


def merge_ranges(rs):
    out = []
    for r in sorted(rs, key=lambda c: c["s"]):
        if out and r["s"] <= out[-1]["e"] + 0.01:
            out[-1]["e"] = max(out[-1]["e"], r["e"])
            out[-1]["why"] += " + " + r["why"]
        else:
            out.append(dict(r))
    return out


# ---------------------------------------------------------------- render
def keep_intervals(total, cuts):
    kept, pos = [], 0.0
    for c in sorted(cuts, key=lambda c: c["s"]):
        s, e = max(0.0, c["s"]), min(total, c["e"])
        if s > pos + 0.03:
            kept.append((pos, s))
        pos = max(pos, e)
    if total > pos + 0.03:
        kept.append((pos, total))
    return kept


def remap(t, kept):
    """وقت الأصل -> وقت الناتج، أو None لو داخل جزء محذوف."""
    acc = 0.0
    for s, e in kept:
        if s - 1e-6 <= t <= e + 1e-6:
            return acc + (t - s)
        acc += e - s
    return None


def fix_fonts(workdir):
    """يحوّل خط Cairo (woff2) إلى TTF عشان فلتر ass ما يقرا woff2."""
    fd = workdir / "fonts"
    fd.mkdir(exist_ok=True)
    try:
        from fontTools.ttLib import TTFont
    except Exception:
        return fd, "Segoe UI"
    made = False
    for f in sorted(FONTS_SRC.glob("Cairo-*.woff2")):
        dst = fd / (f.stem + ".ttf")
        if not dst.exists():
            try:
                t = TTFont(str(f)); t.flavor = None; t.save(str(dst))
            except Exception:
                continue
        made = True
    return fd, ("Cairo" if made else "Segoe UI")


def make_ass(words, kept, brand, W, H, workdir, font):
    c = (brand or {}).get("colors", {})
    txt = hex2ass(c.get("text", "#F3EFE6")); acc = hex2ass(c.get("accent", "#C9A55C"))
    wmap = ((brand or {}).get("style", {}) or {}).get("wordMap", {"وش": "شنو", "مين": "منو"})
    qonly = ((brand or {}).get("style", {}) or {}).get("punctuation", "question-only") == "question-only"

    items = []
    for w in words:
        if w.get("drop"):
            continue
        s, e = remap(w["s"] + 0.001, kept), remap(max(w["s"] + 0.001, w["e"] - 0.001), kept)
        if s is None:
            continue
        if e is None or e < s:
            e = s + 0.2
        t = w["w"]
        if qonly:
            q = "؟" in t or "?" in t
            t = PUNCT.sub("", t).replace("?", "").replace("؟", "").strip()
            if q: t += "؟"
        t = wmap.get(t, t)
        if t:
            items.append({"t": t, "s": s, "e": e})
    # تجميع بعبارات 1 إلى 4 كلمات
    chunks, cur = [], []
    for it in items:
        if cur and (len(cur) >= 4 or it["s"] - cur[-1]["e"] > 0.45 or cur[-1]["t"].endswith("؟")):
            chunks.append(cur); cur = []
        cur.append(it)
    if cur: chunks.append(cur)

    def ts(x):
        h = int(x // 3600); m = int(x % 3600 // 60); s = x % 60
        return f"{h}:{m:02d}:{s:05.2f}"

    size = int(W * 0.085)
    head = (f"[Script Info]\nScriptType: v4.00+\nPlayResX: {W}\nPlayResY: {H}\nWrapStyle: 0\nScaledBorderAndShadow: yes\n\n"
            f"[V4+ Styles]\nFormat: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding\n"
            f"Style: Cap,{font},{size},{txt},{txt},&H00000000&,&H80000000&,1,0,0,0,100,100,0,0,1,6,2,2,60,60,{int(H*0.26)},1\n\n"
            f"[Events]\nFormat: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text\n")
    lines = []
    for ch in chunks:
        for i, it in enumerate(ch):
            start = it["s"]
            end = ch[i + 1]["s"] if i + 1 < len(ch) else min(it["e"] + 0.35, it["s"] + 1.6)
            if end <= start: end = start + 0.15
            parts = [(f"{{\\c{acc}\\fscx108\\fscy108}}{x['t']}{{\\c{txt}\\fscx100\\fscy100}}" if j == i else x["t"]) for j, x in enumerate(ch)]
            lines.append(f"Dialogue: 0,{ts(start)},{ts(end)},Cap,,0,0,0,,{' '.join(parts)}")
    (workdir / "captions.ass").write_text(head + "\n".join(lines) + "\n", encoding="utf-8-sig")
    return len(chunks)


def audio_chain(a):
    ch = ["highpass=f=80", "afftdn=nr=%d:nf=-35:tn=1" % a.denoise]
    if a.enhance:
        ch += ["equalizer=f=200:t=q:w=1.2:g=-2", "equalizer=f=3500:t=q:w=1.0:g=2.5",
               "acompressor=threshold=-21dB:ratio=3.2:attack=8:release=140:makeup=3",
               "alimiter=limit=0.95"]
    ch.append("loudnorm=I=-16:TP=-1.5:LRA=9")
    return ",".join(ch)


def cmd_render(a):
    work = Path(a.folder)
    wj = json.loads((work / "words.json").read_text(encoding="utf-8"))
    plan = json.loads((work / "plan.json").read_text(encoding="utf-8"))
    src = Path(wj["source"]); total = wj["duration"]
    if a.source: src = Path(a.source)
    if not src.exists(): sys.exit(f"ملف المصدر مفقود: {src}")
    kept = keep_intervals(total, plan["cuts"])
    if not kept: sys.exit("القص شال كل شي. راجع plan.json")
    new_len = sum(e - s for s, e in kept)
    brand, bdir = load_brand(a.project or work.parent)
    W, H = 1080, 1920
    ff = ffmpeg_path()
    fdir, font = fix_fonts(work)
    nchunks = make_ass(wj["words"], kept, brand, W, H, work, font)
    colors = (brand or {}).get("colors", {})
    bg = colors.get("bg", "#0E1B2E").lstrip("#"); acc = colors.get("accent", "#C9A55C").lstrip("#")
    handle = (brand or {}).get("handle", "")
    vid = has_video(src) and not a.audio_only

    # --- خطوة 1: قص + تحسين الصوت
    fade = 0.012
    aparts, vparts = [], []
    for i, (s, e) in enumerate(kept):
        aparts.append(f"[0:a]atrim={s:.3f}:{e:.3f},asetpts=PTS-STARTPTS,afade=t=in:d={fade},afade=t=out:st={max(0,e-s-fade):.3f}:d={fade}[a{i}]")
        if vid:
            vparts.append(f"[0:v]trim={s:.3f}:{e:.3f},setpts=PTS-STARTPTS[v{i}]")
    n = len(kept)
    g = ";".join(aparts + vparts)
    g += ";" + "".join(f"[a{i}]" for i in range(n)) + f"concat=n={n}:v=0:a=1[ac];[ac]{audio_chain(a)}[aout]"
    if vid:
        g += ";" + "".join(f"[v{i}]" for i in range(n)) + f"concat=n={n}:v=1:a=0[vc]"
    (work / "_cut.txt").write_text(g, encoding="utf-8")
    cmd = [ff, "-y", "-i", str(src), "-/filter_complex", "_cut.txt", "-map", "[aout]"]
    if vid: cmd += ["-map", "[vc]", "-c:v", "libx264", "-preset", "fast", "-crf", "16", "-pix_fmt", "yuv420p"]
    cmd += ["-c:a", "pcm_s16le", "_cut_a.mkv"]
    print("قص وتحسين الصوت...", flush=True)
    run(cmd, cwd=work)
    run([ff, "-y", "-i", "_cut_a.mkv", "-vn", "-c:a", "aac", "-b:a", "256k", "clean_audio.m4a"], cwd=work)

    # --- خطوة 2: التركيب
    logo = None
    if brand and bdir and (bdir / brand.get("logo", "logo.png")).exists():
        shutil.copy(bdir / brand.get("logo", "logo.png"), work / "_logo.png"); logo = "_logo.png"
    fc = []
    if vid:
        fc.append(f"[0:v]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H}[base]")
        a_in = "0:a"
        inputs = ["-i", "_cut_a.mkv"]
    else:
        fc.append(f"color=c=0x{bg}:s={W}x{H}:r=30,format=yuv420p[bgc]")
        fc.append(f"[0:a]showwaves=s=216x68:mode=cline:colors=0x{acc}:r=30:scale=sqrt,scale={W}:340:flags=neighbor,format=rgba[wv]")
        fc.append("[bgc][wv]overlay=0:(H-h)/2-120:shortest=1[base]")
        inputs = ["-i", "_cut_a.mkv"]
    last = "base"
    if logo:
        inputs += ["-i", logo]
        li = len([x for x in inputs if x == "-i"]) - 1
        fc.append(f"[{li}:v]scale=220:-1[lg]")
        fc.append(f"[{last}][lg]overlay=(W-w)/2:90[withlogo]"); last = "withlogo"
    fc.append(f"[{last}]ass=captions.ass:fontsdir=fonts[outv]")
    (work / "_comp.txt").write_text(";".join(fc), encoding="utf-8")
    out = work / (a.name or "final.mp4")
    cmd = [ff, "-y"] + inputs + ["-/filter_complex", "_comp.txt", "-map", "[outv]", "-map", "0:a",
                                  "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
                                  "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", out.name]
    print("تركيب الفيديو والكابشن...", flush=True)
    run(cmd, cwd=work)
    for t in ("_cut.txt", "_comp.txt", "_cut_a.mkv", "_logo.png"):
        (work / t).unlink(missing_ok=True)
    print(f"\nتم: {out}\nالمدة {new_len:.1f}ث (الأصل {total:.1f}ث) | عبارات الكابشن {nchunks} | الخط {font}")
    return 0


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = p.add_subparsers(dest="cmd", required=True)
    sp.add_parser("doctor").set_defaults(fn=cmd_doctor)
    x = sp.add_parser("analyze")
    x.add_argument("input"); x.add_argument("--out", required=True)
    x.add_argument("--model", default="small", help="tiny|base|small|medium|large-v3 (الأكبر أدق وأبطأ)")
    x.add_argument("--lang", default="ar"); x.add_argument("--prompt", default="")
    x.add_argument("--max-gap", type=float, default=0.45, help="أي وقفة أطول من كذا تنقص")
    x.add_argument("--keep-gap", type=float, default=0.18, help="الوقفة اللي تبقى بعد القص")
    x.add_argument("--cut-fillers", action="store_true", help="يحذف الحشو (ااا/ممم) والكلمة المكررة تلقائياً")
    x.set_defaults(fn=cmd_analyze)
    r = sp.add_parser("render")
    r.add_argument("folder"); r.add_argument("--project", default=None, help="فولدر المشروع اللي فيه .legal-carousel/brand.json")
    r.add_argument("--source", default=None); r.add_argument("--name", default="final.mp4")
    r.add_argument("--audio-only", action="store_true", help="تجاهل فيديو المصدر وسوّ خلفية الهوية بموجة صوت")
    r.add_argument("--denoise", type=int, default=12, help="قوة إزالة الضجيج dB")
    r.add_argument("--no-enhance", dest="enhance", action="store_false")
    r.set_defaults(fn=cmd_render)
    a = p.parse_args()
    sys.exit(a.fn(a))


if __name__ == "__main__":
    main()
