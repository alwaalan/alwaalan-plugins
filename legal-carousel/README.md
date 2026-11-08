# legal-carousel — مصنع كاروسيل التوعية القانونية

إضافة (Plugin) لمحامين وصنّاع محتوى قانوني: تقرأ هوية صاحب الحساب من أعماله، تبني داشبورد أخبار، تحوّل الخبر لكاروسيل 3:4، وتصدّر PNG.

## المهارات
| المهارة | شنو تسوي |
|---|---|
| `brand-setup` | تقرأ كاروسيلاتك وشعارك وتحفظ الهوية في `.legal-carousel/brand.json` |
| `news-board` | تجيب أخبار من مصادر منشورة وتبني `الأخبار.html` (تحديد، حذف، قيد الإنجاز، منجزة، محذوفة، طلب أخبار جديدة) |
| `legal-carousel` | تحوّل الخبر لكاروسيل بقواعد أسلوبك مع فحص آلي ومعاينة |
| `export-png` | تحفظ الشرائح PNG عالية الدقة بفولدرك |

## التشغيل (أول مرة)
1. افتح جلسة بفولدر مشروعك (فيه شعارك وكاروسيلاتك السابقة).
2. قل: «سجل هويتي» ← `brand-setup`.
3. قل: «جيب أخبار» ← الداشبورد.
4. انسخ خبر من الداشبورد والصقه ← الكاروسيل ← «اعتمدها» ← PNG.

## المتطلبات
- Python 3 (الأوامر بالسكربتات بالمكتبة القياسية فقط).
- Pillow لمعالجة الشعار فقط: `pip install pillow`.
- Chrome أو Edge لتصدير PNG من الطرفية.
- مهارة `legal-reference` (التشريعات الكويتية) اختيارية للتحقق من أرقام المواد. لدولة ثانية استبدلها بمرجع تشريعات بلدك.

## هيكل الملفات
```
.claude-plugin/plugin.json
skills/{brand-setup,news-board,legal-carousel,export-png}/SKILL.md
scripts/{build.py,export_slides.py,tint_logo.py}
templates/{carousel.template.html,dashboard.template.html}
examples/{brand.sample.json,media-law.deck.json,news.example.json}
```

## ملفات مشروعك (تنكتب بفولدرك)
```
.legal-carousel/brand.json   الهوية
.legal-carousel/logo.png     الشعار بلون الهوية
.legal-carousel/news.json    الأخبار
.legal-carousel/decks/*.json شرائح كل كاروسيل
الأخبار.html                 الداشبورد
<موضوع>/carousel-*.html + PNG
```

## تنبيه
الإضافة تساعد بالصياغة والتصميم؛ أرقام المواد ونصوص التشريعات الجديدة تُراجع من الجريدة الرسمية قبل النشر، والقرار الأخير لصاحب الحساب.
