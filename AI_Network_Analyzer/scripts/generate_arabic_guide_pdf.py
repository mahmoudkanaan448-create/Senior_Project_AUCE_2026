"""Generate the formal Arabic user & defense guidebook as PDF."""

from pathlib import Path

import arabic_reshaper
from bidi.algorithm import get_display
from fpdf import FPDF

OUT_DIR = Path(__file__).resolve().parent.parent / "reports"
DESKTOP = Path.home() / "OneDrive" / "Desktop"
if not DESKTOP.exists():
    DESKTOP = Path.home() / "Desktop"

FONT = r"C:\Windows\Fonts\arial.ttf"
FONT_BOLD = r"C:\Windows\Fonts\arialbd.ttf"


def ar(text: str) -> str:
    """Reshape Arabic and apply RTL for correct PDF rendering."""
    return get_display(arabic_reshaper.reshape(text))


class GuidePDF(FPDF):
    def header(self):
        self.set_font("Arabic", "B", 10)
        self.set_text_color(40, 60, 90)
        self.cell(0, 8, ar("كتيب تشغيل وشرح مشروع محلل حركة الشبكة بالذكاء الاصطناعي"), align="C", new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(40, 60, 90)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(4)

    def footer(self):
        self.set_y(-15)
        self.set_font("Arabic", "", 9)
        self.set_text_color(100, 100, 100)
        self.cell(0, 10, ar(f"صفحة {self.page_no()}"), align="C")

    def title_page(self):
        self.add_page()
        self.ln(40)
        self.set_font("Arabic", "B", 22)
        self.set_text_color(20, 40, 80)
        self.set_x(self.l_margin)
        self.multi_cell(self.epw, 12, ar("كتيب تشغيل المشروع وشرحه للمناقشة"), align="C")
        self.ln(8)
        self.set_font("Arabic", "B", 16)
        self.set_x(self.l_margin)
        self.multi_cell(self.epw, 10, ar("نظام تحليل حركة الشبكة واكتشاف الشذوذ بالذكاء الاصطناعي"), align="C")
        self.ln(6)
        self.set_font("Arabic", "", 13)
        self.set_text_color(60, 60, 60)
        self.set_x(self.l_margin)
        self.multi_cell(self.epw, 9, ar("مشروع تخرج — الجامعة الأمريكية للثقافة والتعليم AUCE — 2026"), align="C")
        self.ln(20)
        self.set_font("Arabic", "", 12)
        for line in [
            "يتضمن هذا الكتيب:",
            "• كيفية تشغيل التطبيق واستخدامه",
            "• شرح الروابط وصفحات لوحة التحكم",
            "• شرح مكونات النظام والنماذج الذكية",
            "• دليل العرض الجامعي والتحضير للأسئلة",
        ]:
            self.set_x(self.l_margin)
            self.multi_cell(self.epw, 9, ar(line), align="R")
        self.ln(25)
        self.set_font("Arabic", "B", 11)
        self.set_x(self.l_margin)
        self.multi_cell(self.epw, 8, ar("بيانات الدخول الافتراضية: admin / admin123"), align="C")

    def _write(self, text: str, align: str = "R"):
        """Write a block from the left margin (avoids RTL width errors)."""
        self.set_x(self.l_margin)
        self.multi_cell(self.epw, 7.5, ar(text), align=align)

    def h1(self, text: str):
        self.set_font("Arabic", "B", 15)
        self.set_text_color(20, 50, 90)
        self.ln(4)
        self.set_x(self.l_margin)
        self.multi_cell(self.epw, 10, ar(text), align="R")
        self.ln(2)

    def h2(self, text: str):
        self.set_font("Arabic", "B", 12)
        self.set_text_color(40, 70, 110)
        self.ln(2)
        self.set_x(self.l_margin)
        self.multi_cell(self.epw, 8, ar(text), align="R")
        self.ln(1)

    def p(self, text: str):
        self.set_font("Arabic", "", 11)
        self.set_text_color(30, 30, 30)
        self._write(text)
        self.ln(1)

    def bullet(self, text: str):
        self.set_font("Arabic", "", 11)
        self.set_text_color(30, 30, 30)
        self._write("• " + text)

    def box(self, lines: list[str]):
        self.set_draw_color(80, 110, 150)
        self.set_font("Arabic", "", 10)
        start = self.get_y()
        for line in lines:
            self.set_x(self.l_margin + 5)
            self.multi_cell(self.epw - 10, 7, ar(line), align="R")
        end = self.get_y()
        self.rect(self.l_margin, start - 1, self.epw, end - start + 3)
        self.ln(4)


def build():
    pdf = GuidePDF()
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_font("Arabic", "", FONT)
    pdf.add_font("Arabic", "B", FONT_BOLD)

    # ========== TITLE ==========
    pdf.title_page()

    # ========== 1 ==========
    pdf.add_page()
    pdf.h1("١) ما هو المشروع؟")
    pdf.p(
        "هذا المشروع منصة لاكتشاف التهديدات الشبكية والاستجابة لها "
        "(Network Detection and Response – NDR). يقوم النظام بمراقبة حركة الشبكة، "
        "استخراج الخصائص، ثم تحليلها بواسطة خمسة نماذج ذكاء اصطناعي، "
        "وإصدار تنبيهات، وإثراء النتائج بمعلومات تهديدات خارجية، "
        "مع إمكانية حظر عناوين IP الضارة وإنتاج تقارير."
    )
    pdf.h2("الهدف العلمي")
    pdf.bullet("دمج التعلم الخاضع للإشراف مع التعلم غير الخاضع للإشراف لكشف الهجمات المعروفة والمجهولة.")
    pdf.bullet("إضافة بعد زمني عبر نموذج تسلسلي للتنبؤ المبكر.")
    pdf.bullet("توفير واجهة تشغيل واضحة لمحلل الأمن ولوحة تحكم تفاعلية.")
    pdf.bullet("أتمتة جزء من الاستجابة: تنبيه، حظر، تقرير.")

    # ========== 2 ==========
    pdf.h1("٢) الروابط وما وظيفة كل منها")
    pdf.p("التطبيق يعمل محلياً على جهازك. الروابط ليست للتحميل من الإنترنت، بل لفتح الواجهات بعد التشغيل.")

    pdf.h2("رابط لوحة التحكم (الأهم للمستخدم واللجنة)")
    pdf.box([
        "http://localhost:8501",
        "أو: http://127.0.0.1:8501",
        "الوظيفة: واجهة Streamlit الرسومية — الشاشات، الرسوم، التنبيهات، الإعدادات.",
        "هذا هو الرابط الذي تعرضه أمام اللجنة.",
    ])

    pdf.h2("رابط واجهة البرمجة API")
    pdf.box([
        "http://127.0.0.1:8000/docs",
        "الوظيفة: توثيق تفاعلي لـ FastAPI (Swagger).",
        "يعرض كل نقاط النهاية: تسجيل الدخول، التنبؤ، التنبيهات، الحظر، التقارير...",
        "مفيد لإثبات أن النظام مبني على معمارية REST آمنة بـ JWT.",
    ])

    pdf.h2("رابط الصحة (اختياري)")
    pdf.box([
        "http://127.0.0.1:8000/health",
        "الوظيفة: التحقق السريع أن الخادم الخلفي يعمل.",
    ])

    pdf.p("معنى localhost / 127.0.0.1: عنوان الجهاز المحلي نفسه. المنفذ 8501 للوحة التحكم، والمنفذ 8000 للخادم الخلفي.")

    # ========== 3 ==========
    pdf.add_page()
    pdf.h1("٣) كيف تشغّل التطبيق؟")
    pdf.h2("الطريقة الأسهل")
    pdf.bullet("من سطح المكتب: انقر مرتين على الاختصار «AI Network Analyzer».")
    pdf.bullet("أو من مجلد المشروع: انقر مرتين على الملف run.bat.")
    pdf.bullet("سيفتح المتصفح تلقائياً على http://localhost:8501")
    pdf.bullet("بيانات الدخول: اسم المستخدم admin — كلمة المرور admin123")
    pdf.bullet("اترك نوافذ الـ API والـ Dashboard مفتوحة أثناء الاستخدام.")

    pdf.h2("موقع المشروع على الجهاز")
    pdf.box([
        r"c:\Users\mohamad\.vscode\Senior_Project_AUCE_2026\AI_Network_Analyzer",
        "بيئة بايثون المثبتة: C:\\aindr_venv",
        "قاعدة البيانات: database\\analyzer.db",
        "النماذج المدربة: مجلد models",
        "مجموعة البيانات التجريبية: datasets\\dataset.csv",
    ])

    pdf.h2("التشغيل اليدوي (إن لزم)")
    pdf.p("في نافذة PowerShell أولى:")
    pdf.box([
        r"C:\aindr_venv\Scripts\Activate",
        r"cd c:\Users\mohamad\.vscode\Senior_Project_AUCE_2026\AI_Network_Analyzer",
        "python main.py",
    ])
    pdf.p("في نافذة ثانية:")
    pdf.box([
        r"C:\aindr_venv\Scripts\Activate",
        r"cd c:\Users\mohamad\.vscode\Senior_Project_AUCE_2026\AI_Network_Analyzer",
        "streamlit run dashboard/home.py",
    ])

    pdf.h2("إيقاف التطبيق")
    pdf.p("أغلق نوافذ AI-NDR-API و AI-NDR-Dashboard، أو اضغط Ctrl+C داخل كل نافذة طرفية.")

    # ========== 4 ==========
    pdf.h1("٤) ماذا يرى المستخدم داخل التطبيق؟")
    pdf.p("بعد تسجيل الدخول تظهر لوحة تحكم متعددة الصفحات في الشريط الجانبي:")

    pages = [
        ("الصفحة الرئيسية Home", "مؤشرات عامة: عدد التدفقات، التنبيهات، عناوين محظورة، توزيع الهجمات، مقارنة أداء النماذج."),
        ("Live Monitoring", "مراقبة التدفقات الأخيرة، ورفع ملفات CSV لحركة الشبكة."),
        ("AI Detection", "تشغيل الكشف على التدفقات غير المعالجة، وعرض نتائج الاندماج بين النماذج."),
        ("Threat Intelligence", "البحث عن سمعة عنوان IP والموقع الجغرافي ودرجة الخطورة."),
        ("Alerts", "إدارة دورة حياة التنبيه: جديد، قيد التحقيق، مغلق."),
        ("Blocked IPs", "عرض الحظر اليدوي والآلي، وإلغاء الحظر عند الحاجة."),
        ("AI Models", "عرض مقاييس الدقة والاستدعاء وF1، وإمكانية إعادة التدريب."),
        ("Reports", "ملخصات وتصدير تقارير PDF/CSV."),
        ("Settings", "عتبات الثقة، البريد، تيليجرام، إعدادات عامة."),
    ]
    for title, desc in pages:
        pdf.h2(title)
        pdf.p(desc)

    # ========== 5 ==========
    pdf.add_page()
    pdf.h1("٥) معمارية النظام — ماذا تعمل كل طبقة؟")
    pdf.bullet("طبقة المراقبة Monitoring: التقاط الحزم (Scapy)، بناء التدفقات، استخراج الخصائص الإحصائية.")
    pdf.bullet("طبقة التدريب Training: تجهيز البيانات وتدريب خمسة نماذج وحفظها في models.")
    pdf.bullet("طبقة الكشف Detection: تحميل النماذج، التنبؤ، محرك القرار (Decision Fusion)، حساب الثقة.")
    pdf.bullet("الذكاء القابل للتفسير XAI: يوضح أهم الخصائص التي أثّرت في القرار.")
    pdf.bullet("استخبارات التهديدات TI: AbuseIPDB / الموقع الجغرافي ودرجة المخاطر.")
    pdf.bullet("الاستجابة Alerts/Firewall: بريد، تيليجرام، حظر IP على مستوى النظام عند الإمكان.")
    pdf.bullet("الخادم API: FastAPI + JWT + صلاحيات حسب الدور.")
    pdf.bullet("الواجهة Dashboard: Streamlit للعرض التفاعلي.")
    pdf.bullet("قاعدة البيانات: SQLite محلياً (مع إمكانية PostgreSQL لاحقاً).")

    pdf.h2("لماذا بايثون 3.14؟")
    pdf.p(
        "النظام معدّ ليعمل على بايثون 3.14. نماذج Autoencoder والتسلسل الزمني تستخدم "
        "PyTorch إن توفر، وإلا تستخدم شبكات MLP عبر scikit-learn كبديل متوافق، "
        "لأن TensorFlow لا يدعم ويندوز مع 3.14 بشكل مستقر."
    )

    # ========== 6 ==========
    pdf.h1("٦) النماذج الخمسة — كيف تشرحها للجنة؟")

    models = [
        ("Random Forest", "تعلم خاضع للإشراف. مجموعة أشجار قرار. ممتاز للهجمات المعروفة المصنّفة."),
        ("XGBoost", "تعزيز تدرّجي. غالباً أدق من غابة عشوائية على الجداول الرقمية."),
        ("Isolation Forest", "غير خاضع للإشراف. يعزل الشذوذ بسرعة — مفيد لهجمات Zero-day."),
        ("Autoencoder", "شبكة تعيد بناء الحركة الطبيعية؛ خطأ إعادة البناء العالي = شذوذ."),
        ("LSTM / Sequence", "يحلل نافذة زمنية من التدفقات المتتالية لاكتشاف الأنماط الزمنية والتنبؤ."),
    ]
    for name, desc in models:
        pdf.h2(name)
        pdf.p(desc)

    pdf.h2("اندماج القرار Decision Fusion")
    pdf.p(
        "لا يعتمد النظام على نموذج واحد. تُجمع مخرجات النماذج بالتصويت الموزون، "
        "ثم تُحسب درجة التهديد والخطورة (Low/Medium/High/Critical). هذا يقلل الإنذارات الكاذبة."
    )

    # ========== 7 ==========
    pdf.add_page()
    pdf.h1("٧) سيناريو عرض أمام اللجنة (١٠–١٥ دقيقة)")
    pdf.bullet("١. افتتح الاختصار وشغّل النظام، وافتح http://localhost:8501")
    pdf.bullet("٢. سجّل الدخول بـ admin / admin123")
    pdf.bullet("٣. اعرض الصفحة الرئيسية واشرح المؤشرات.")
    pdf.bullet("٤. انتقل إلى AI Models واشرح النماذج الخمسة والمقاييس.")
    pdf.bullet("٥. من Live Monitoring ارفع CSV أو اعرض التدفقات.")
    pdf.bullet("٦. شغّل الكشف من AI Detection واعرض التصنيف والثقة.")
    pdf.bullet("٧. افتح Threat Intelligence لعرض إثراء عنوان IP.")
    pdf.bullet("٨. اعرض Alerts و Blocked IPs كجزء الاستجابة.")
    pdf.bullet("٩. افتح http://127.0.0.1:8000/docs لدقيقة واحدة لإثبات الـ API.")
    pdf.bullet("١٠. اختم: هجين AI + XAI + TI + استجابة آلية = منصة NDR متكاملة.")

    pdf.h2("جمل افتتاحية مقترحة")
    pdf.p(
        "«طورت منصة لاكتشاف التهديدات الشبكية تعتمد على محرك ذكاء اصطناعي هجين "
        "يجمع بين نماذج خاضعة وغير خاضعة للإشراف مع تحليل زمني، مع واجهة تشغيل "
        "وخادم REST آمن واستجابة آلية.»"
    )

    # ========== 8 ==========
    pdf.h1("٨) أسئلة متوقعة وكيف تجيب")

    qa = [
        ("لماذا خمسة نماذج؟", "لأن لكل نموذج نقطة قوة: المعروفة، المجهولة، الزمنية. الاندماج يرفع الدقة ويقلل الإنذارات الكاذبة."),
        ("ما الفرق بين Isolation Forest و Autoencoder؟", "الأول إحصائي/شجري يعزل الشواذ، والثاني عصبي يعتمد خطأ إعادة البناء. منهجان مختلفان لنفس الهدف."),
        ("كيف تتعاملون مع Zero-day؟", "بالنماذج غير الخاضعة للإشراف التي لا تحتاج أمثلة هجوم مسبقة."),
        ("ما دور LSTM؟", "يفهم تسلسل الأحداث عبر الزمن مثل تصعيد DDoS أو مسح المنافذ التدريجي."),
        ("كيف تؤمّنون الـ API؟", "JWT بعد تسجيل الدخول، وتجزئة كلمات المرور بـ bcrypt، وصلاحيات حسب الدور RBAC."),
        ("لماذا SQLite؟", "لسهولة التطوير والعرض المحلي. المعمارية تدعم PostgreSQL عبر تغيير DATABASE_URL."),
        ("ما معنى XAI؟", "تفسير القرار للمحلل الأمني: أي الخصائص أثّرت أكثر، لزيادة الثقة والشفافية."),
        ("هل النظام يمنع الهجوم فعلاً؟", "نعم جزئياً عبر حظر IP والتنبيه الفوري؛ وهو مكمل لجدار ناري وليس بديلاً كاملاً."),
        ("ما مصدر البيانات؟", "يمكن استخدام CIC-IDS أو بيانات تجريبية مولَّدة محلياً للتدريب والعرض."),
        ("ما حدود النظام؟", "التقاط الحي يحتاج صلاحيات؛ جودة النتائج تعتمد على البيانات؛ العتبات تحتاج ضبطاً."),
        ("لماذا Streamlit؟", "سرعة بناء واجهة بايثون تفاعلية مناسبة للنماذج الأولية والعروض الأكاديمية."),
        ("كيف تقيسون الأداء؟", "Accuracy, Precision, Recall, F1, ROC-AUC مع مقارنة بين النماذج."),
    ]
    for q, a in qa:
        pdf.h2("س: " + q)
        pdf.p("ج: " + a)

    # ========== 9 ==========
    pdf.add_page()
    pdf.h1("٩) مصطلحات سريعة للجنة")
    terms = [
        ("Flow", "مجموعة حزم تشترك في عناوين ومنافذ وبروتوكول خلال مدة زمنية."),
        ("Feature Extraction", "تحويل التدفق إلى متجه رقمي تفهمه نماذج التعلم الآلي."),
        ("False Positive", "تنبيه خاطئ على حركة طبيعية."),
        ("Severity", "مستوى خطورة التنبيه: منخفض إلى حرج."),
        ("Threat Intelligence", "معلومات خارجية عن سمعة العناوين والتهديدات."),
        ("NDR", "Network Detection and Response — كشف واستجابة على مستوى الشبكة."),
    ]
    for t, d in terms:
        pdf.h2(t)
        pdf.p(d)

    # ========== 10 ==========
    pdf.h1("١٠) قائمة تحقق قبل المناقشة")
    pdf.bullet("التأكد أن C:\\aindr_venv موجودة والمكتبات مثبتة.")
    pdf.bullet("تشغيل run.bat مرة قبل المناقشة بيوم واختبار الدخول.")
    pdf.bullet("التأكد أن النماذج موجودة داخل مجلد models.")
    pdf.bullet("تحضير ملف CSV صغير للعرض الحي.")
    pdf.bullet("إغلاق البرامج الثقيلة لتفادي بطء الجهاز.")
    pdf.bullet("حفظ لقطات شاشة احتياطية إن تعذّر التشغيل الحي.")
    pdf.bullet("مراجعة هذا الكتيب وأسئلة القسم ٨.")

    pdf.h1("١١) خلاصة")
    pdf.p(
        "التطبيق محلي: تشغّله ثم تفتح لوحة التحكم. "
        "الرابط الأساسي للعرض هو http://localhost:8501 "
        "ورابط إثبات الـ API هو http://127.0.0.1:8000/docs. "
        "الدخول الافتراضي admin / admin123. "
        "اشرح للجنة أنه نظام NDR هجين يكتشف، يفسّر، يثري، ويستجيب."
    )

    pdf.ln(10)
    pdf.set_font("Arabic", "B", 12)
    pdf.set_text_color(20, 50, 90)
    pdf.multi_cell(0, 8, ar("بالتوفيق في المناقشة."), align="C")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out1 = OUT_DIR / "دليل_تشغيل_وشرح_المشروع.pdf"
    out2 = DESKTOP / "دليل_تشغيل_وشرح_المشروع.pdf"
    pdf.output(str(out1))
    pdf.output(str(out2))
    print(f"Saved: {out1}")
    print(f"Saved: {out2}")


if __name__ == "__main__":
    build()
