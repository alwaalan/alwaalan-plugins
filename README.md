# alwaalan-plugins

إضافات Claude لمحامين وصنّاع محتوى التوعية القانونية بالعربية.

| الإضافة | شنو تسوي |
|---|---|
| [`legal-carousel`](legal-carousel) | تقرأ هويتك من أعمالك، تبني داشبورد أخبار بمراحل، تحوّل الخبر لكاروسيل 3:4 (وتيك توك 9:16) مع فحص آلي، وتصدّر PNG، وتجهز مسودة نشر |
| [`kw-legislation`](kw-legislation) | مرجع التشريعات الكويتية (84 قانوناً ولائحة حتى 5/10/2026) مع بحث بالمادة والتحقق بصورة الصفحة |

## التنصيب (Claude Code)
```text
/plugin marketplace add alwaalan/alwaalan-plugins
/plugin install legal-carousel@alwaalan-plugins
/plugin install kw-legislation@alwaalan-plugins
```
في تطبيق Claude: Customize ثم Plugins ثم Discover ثم Code، أضف `alwaalan/alwaalan-plugins` وفعّل الإضافتين. إضافات Code ما تظهر في المحادثات العادية ولا في Cowork.

## أول استخدام
1. افتح جلسة Code بفولدر مشروعك (فيه شعارك وكاروسيلاتك السابقة إن وجدت).
2. «سجل هويتي» ثم «جيب أخبار» ثم الصق خبر من الداشبورد ثم «اعتمدها».
3. `python <مسار الإضافة>/scripts/build.py doctor` يفحص جهازك (بايثون، Chrome أو Edge، Pillow، PyMuPDF).

## المتطلبات
Python 3.8+ وChrome أو Edge. Pillow لتجهيز الشعار، وPyMuPDF لعرض صفحات التشريعات (يطلب Claude إذنك قبل تنصيبه).

## تنبيهات
- المرجع تجميع غير رسمي وتاريخه محدد، والنصوص الرسمية من «الكويت اليوم». أرقام المواد تُراجع من صورة صفحتها قبل أي نشر.
- الإضافة تساعد بالصياغة والتصميم، والقرار الأخير لصاحب الحساب. لا شي ينشر تلقائياً.
- الترخيص: MIT للكود. المواد الخارجية في [NOTICE.md](NOTICE.md). التغييرات في [CHANGELOG.md](CHANGELOG.md).
