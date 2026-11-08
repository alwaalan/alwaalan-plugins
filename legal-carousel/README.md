# legal-carousel: مصنع كاروسيل التوعية القانونية

إضافة Claude لمحامين وصنّاع محتوى قانوني: تقرأ هوية صاحب الحساب من أعماله، تبني داشبورد أخبار بمراحل، تحوّل الخبر لكاروسيل 3:4 (وتيك توك 9:16)، تفحصه آلياً وتصدّر PNG.

## المهارات
| المهارة | شنو تسوي |
|---|---|
| `brand-setup` | تقرأ كاروسيلاتك وشعارك وتحفظ الهوية في `.legal-carousel/brand.json` (أو `brands/<اسم>.json` لأكثر من هوية) |
| `news-board` | تجيب أخبار من مصادر منشورة، تطابقها مع مرجع التشريعات، وتبني الداشبورد (مراحل، مواضيع دائمة، تحذير تكرار، تصدير واستيراد الحالة) |
| `legal-carousel` | تحوّل الخبر لكاروسيل بقواعد أسلوبك مع فحص قواعد وفحص تصميم آلي ومعاينة |
| `export-png` | تحفظ الشرائح PNG عالية الدقة بفولدرك |
| `schedule-draft` | تجهز مسودة نشر في Metricool بدون نشر تلقائي |

## التشغيل (أول مرة)
1. افتح جلسة Code بفولدر مشروعك (فيه شعارك وكاروسيلاتك السابقة).
2. قل: «سجل هويتي» ثم «جيب أخبار» ثم الصق خبر من الداشبورد ثم «اعتمدها».
3. `python scripts/build.py doctor` يفحص جهازك.

## أنواع الشرائح
`cover` · `point` · `list` · `chips` · `steps` · `save` · `stat` (رقم ضخم) · `mistake` (خطأ وصح) · `compare` (قبل وبعد) · `faq` · `ruling` (حكم قضائي). مثال لكلها: `examples/all-types.deck.json`.

## الأدوات (scripts/)
| الملف | وظيفته |
|---|---|
| `build.py carousel` | يبني الكاروسيل من هوية وملف شرائح ويفحص القواعد (`--profile` و`--size`) |
| `build.py dashboard` | يبني الداشبورد من هوية وأخبار |
| `build.py doctor` | يفحص الجهاز |
| `check_deck.py` | فحص التصميم بمتصفح خفي |
| `export_slides.py` | تصدير PNG بمتصفح خفي |
| `tint_logo.py` | تحويل الشعار لـ PNG شفاف بلون الهوية |

## المتطلبات
Python 3.8+ وChrome أو Edge. Pillow لتجهيز الشعار فقط (`python -m pip install pillow`). مرجع التشريعات اختياري (إضافة `kw-legislation`): بدونه ما تكتب الإضافة أرقام مواد أبداً.

## هيكل الملفات
```
.claude-plugin/plugin.json
skills/{brand-setup,news-board,legal-carousel,export-png,schedule-draft}/SKILL.md
scripts/{build.py,check_deck.py,export_slides.py,tint_logo.py}
templates/{carousel.template.html,dashboard.template.html}
fonts/Cairo-*.woff2 · fonts/OFL.txt
examples/{brand.sample.json,media-law.deck.json,all-types.deck.json,news.example.json}
```

## ملفات مشروعك (تنكتب بفولدرك)
```
.legal-carousel/brand.json     الهوية (أو brands/<اسم>.json)
.legal-carousel/logo.png       الشعار بلون الهوية
.legal-carousel/news.json      الأخبار
.legal-carousel/decks/*.json   شرائح كل كاروسيل
داشبورد الأخبار.html            الداشبورد
<موضوع>/carousel-*.html + PNG
```

## تنبيه
الإضافة تساعد بالصياغة والتصميم. أرقام المواد ونصوص التشريعات الجديدة تُراجع من الجريدة الرسمية قبل النشر، والقرار الأخير لصاحب الحساب. لا شي ينشر تلقائياً.