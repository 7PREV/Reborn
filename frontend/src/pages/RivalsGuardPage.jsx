import { ShieldCheck, Download, Link2, Lock, MonitorCheck, CheckCircle2 } from "lucide-react";

function resolveGuardSetupUrl() {
  const fallback = "/api/downloads/RivalsGuard.exe";
  const raw = (process.env.REACT_APP_GUARD_SETUP_URL || "").trim();
  if (!raw) return fallback;

  const driveMatch = raw.match(/\/d\/([a-zA-Z0-9_-]{10,})\//);
  if (driveMatch?.[1]) {
    return `https://drive.google.com/uc?export=download&id=${driveMatch[1]}`;
  }

  const driveOpenMatch = raw.match(/[?&]id=([a-zA-Z0-9_-]{10,})/);
  if (driveOpenMatch?.[1]) {
    return `https://drive.google.com/uc?export=download&id=${driveOpenMatch[1]}`;
  }

  return raw;
}

function Step({ index, title, desc }) {
  return (
    <div className="rounded-xl border border-white/10 bg-surface/70 p-4 sm:p-5">
      <div className="flex items-start gap-3">
        <div className="h-8 w-8 rounded-lg bg-emerald-500/15 text-emerald-300 border border-emerald-400/35 grid place-items-center font-black text-sm">
          {index}
        </div>
        <div>
          <h3 className="font-bold text-white">{title}</h3>
          <p className="mt-1 text-sm text-white/65 leading-relaxed">{desc}</p>
        </div>
      </div>
    </div>
  );
}

export default function RivalsGuardPage() {
  const guardSetupUrl = resolveGuardSetupUrl();

  return (
    <div className="space-y-8" dir="rtl" data-testid="rivalsguard-page">
      <section className="rounded-2xl border border-emerald-400/25 bg-[radial-gradient(circle_at_20%_20%,rgba(16,185,129,0.14),transparent_45%),linear-gradient(135deg,rgba(2,6,23,0.96),rgba(17,24,39,0.92))] p-6 sm:p-8 shadow-[0_22px_90px_rgba(0,0,0,0.5)]">
        <div className="flex items-start gap-3">
          <div className="h-11 w-11 rounded-xl bg-emerald-500/20 text-emerald-300 border border-emerald-400/35 grid place-items-center">
            <ShieldCheck size={22} />
          </div>
          <div className="flex-1">
            <h1 className="font-display font-black text-2xl sm:text-3xl text-white leading-tight">RivalsGuard — نظام الحماية أثناء المباريات</h1>
            <p className="mt-2 text-white/70 text-sm sm:text-base leading-relaxed">
              RivalsGuard نظام نزاهة مخصص لمباريات المنصة. يعمل وقت المباراة للتأكد من بيئة لعب عادلة لجميع الفرق،
              ويتكامل مباشرة مع صفحة المباراة داخل Rivals.
            </p>
          </div>
        </div>

        <div className="mt-6 flex flex-wrap items-center gap-3">
          <a
            href={guardSetupUrl}
            target="_blank"
            rel="noreferrer"
            data-testid="rivalsguard-download-btn"
            className="inline-flex items-center gap-2 rounded-xl bg-emerald-400 text-slate-950 px-5 py-2.5 font-black tracking-wide hover:bg-emerald-300 transition shadow-[0_10px_30px_rgba(16,185,129,0.35)]"
          >
            <Download size={16} /> تحميل RivalsGuard_Setup.zip
          </a>
          <a
            href="https://rivalsesports.games/matches"
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-2 rounded-xl border border-white/20 text-white/85 px-4 py-2.5 hover:bg-white/5"
          >
            <Link2 size={15} /> الانتقال للمباريات
          </a>
        </div>
      </section>

      <section className="grid lg:grid-cols-3 gap-4">
        <Step
          index="1"
          title="حمّل البرنامج"
          desc="نزّل RivalsGuard_Setup.zip من الزر أعلاه وفك الضغط ثم ثبّت البرنامج على جهازك."
        />
        <Step
          index="2"
          title="ثبّته مرّة واحدة"
          desc="بعد التثبيت الأول، لا تحتاج إعادة التثبيت كل مرة. يكفي إبقاء البرنامج متاحاً على جهازك."
        />
        <Step
          index="3"
          title="ابدأ المباراة من المنصة"
          desc="ادخل صفحة المباراة في Rivals واضغط بدء المباراة، وسيتم تشغيل RivalsGuard تلقائياً عبر رابط النظام."
        />
      </section>

      <section className="rounded-2xl border border-white/10 bg-surface/60 p-5 sm:p-6 space-y-4">
        <h2 className="font-display font-black text-xl text-white flex items-center gap-2">
          <MonitorCheck size={20} className="text-emerald-300" /> كيف يعمل أثناء المباريات؟
        </h2>
        <ul className="space-y-2 text-sm text-white/70 leading-relaxed">
          <li className="flex items-start gap-2"><CheckCircle2 size={15} className="mt-0.5 text-emerald-300" /> يتصل بجلسة المباراة عند الضغط من المنصة ويؤكد حالة الحماية للفريق.</li>
          <li className="flex items-start gap-2"><CheckCircle2 size={15} className="mt-0.5 text-emerald-300" /> يرسل تحديثات حالة دورية أثناء المباراة فقط.</li>
          <li className="flex items-start gap-2"><CheckCircle2 size={15} className="mt-0.5 text-emerald-300" /> ينفصل تلقائياً عند انتهاء الجلسة أو إغلاق المباراة.</li>
        </ul>
      </section>

      <section className="rounded-2xl border border-white/10 bg-surface/60 p-5 sm:p-6 space-y-3">
        <h2 className="font-display font-black text-xl text-white flex items-center gap-2">
          <Lock size={19} className="text-royalGold-400" /> سياسة الخصوصية والشروط
        </h2>
        <p className="text-sm text-white/70 leading-relaxed">
          RivalsGuard مخصص لفحص النزاهة التقنية أثناء المباراة فقط. لا يجمع محتوى ملفاتك الشخصية ولا الرسائل
          الخاصة ولا صورك. الهدف الوحيد هو حماية المنافسة وتأكيد امتثال بيئة اللعب لشروط البطولات.
        </p>
        <p className="text-sm text-white/70 leading-relaxed">
          باستخدامك RivalsGuard أثناء المباريات الرسمية، فأنت توافق على تشغيله ضمن جلسة المباراة وعلى تطبيق
          سياسات النزاهة المعتمدة في منصة Rivals.
        </p>
      </section>
    </div>
  );
}
