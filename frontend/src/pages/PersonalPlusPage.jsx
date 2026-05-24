import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Sparkles, Check, Crown, Image as ImageIcon, Palette, Star, ShieldCheck, Trophy } from "lucide-react";
import { toast } from "sonner";
import { useAuth } from "../AuthContext";

const TIERS = [
  {
    id: "trial",
    name: "تجربة مجانية",
    arabicSubtitle: "للمستخدمين الجدد",
    price: "0",
    duration: "3 أيام",
    cta: "تم تفعيلها تلقائياً عند التسجيل",
    color: "border-white/10",
    accent: "#FFFFFF",
    perks: [
      "تجربة جميع ميزات Personal Plus لمدة 3 أيام",
      "تخصيص الأفاتار والبانر واللون المميز",
      "بدون الحاجة لبطاقة دفع",
    ],
  },
  {
    id: "monthly",
    name: "شهري Personal Plus",
    arabicSubtitle: "الخطة الشعبية",
    price: "29",
    duration: "30 يوماً",
    cta: "اشترك الآن",
    color: "border-gold-500/50",
    accent: "#FFCC00",
    badge: "الأكثر مبيعاً",
    perks: [
      "رفع صورة شخصية مخصصة (≤2MB)",
      "رفع بانر خلفية كامل (≤3MB)",
      "اختيار لون مميز يظهر في ملفك",
      "شارة Plus حصرية في الشات",
      "أولوية في طلبات الدعم",
    ],
  },
  {
    id: "yearly",
    name: "سنوي Personal Plus",
    arabicSubtitle: "وفّر 40%",
    price: "189",
    duration: "365 يوماً",
    cta: "اشترك السنوي",
    color: "border-emerald-500/50",
    accent: "#22D3A4",
    badge: "أفضل قيمة",
    perks: [
      "كل ميزات الشهري",
      "12 شهر بسعر 7 أشهر",
      "هدية إطار حصري في الترتيب",
      "وصول مبكر للميزات الجديدة",
    ],
  },
];

export default function PersonalPlusPage() {
  const { user } = useAuth();
  const [busyTier, setBusyTier] = useState(null);
  const navigate = useNavigate();

  const mockCheckout = (tierId) => {
    setBusyTier(tierId);
    setTimeout(() => {
      setBusyTier(null);
      toast.success("🚧 الدفع قيد التطوير — سيتم تفعيل الاشتراك عند ربط بوابة الدفع");
    }, 1100);
  };

  const trialActive = !!user?.is_personal_plus;

  return (
    <div className="space-y-10">
      <header className="text-center pt-2">
        <div className="inline-flex items-center gap-2 text-xs uppercase tracking-widest text-gold-500 mb-3">
          <Sparkles size={12} /> اشتراك شخصي
        </div>
        <h1 className="font-display font-black text-4xl md:text-6xl">Personal Plus</h1>
        <p className="text-white/60 mt-3 max-w-xl mx-auto text-sm md:text-base">
          خصّص ملفك الشخصي بصورة وبانر ولون مميز يخلّيك تتميز في كل الشات والترتيب.
          مجاناً 3 أيام لكل مستخدم جديد.
        </p>
        {trialActive && user?.personal_plus_until && (
          <div data-testid="plus-trial-banner" className="inline-flex items-center gap-2 bg-gold-500/10 border border-gold-500/30 rounded-full px-4 py-2 mt-5 text-sm text-gold-500">
            <Crown size={14} /> تجربتك المجانية مفعّلة حتى {new Date(user.personal_plus_until).toLocaleDateString("ar")}
          </div>
        )}
      </header>

      <section className="grid md:grid-cols-3 gap-5">
        {TIERS.map((t) => (
          <article
            key={t.id}
            data-testid={`plus-tier-${t.id}`}
            className={`relative bg-surface border ${t.color} rounded-2xl p-6 flex flex-col`}
          >
            {t.badge && (
              <div className="absolute -top-3 right-4 text-[10px] uppercase tracking-widest bg-gold-500 text-black px-2 py-1 rounded-full font-bold flex items-center gap-1">
                <Star size={10} /> {t.badge}
              </div>
            )}
            <div className="text-[10px] uppercase tracking-widest text-white/40">{t.arabicSubtitle}</div>
            <h2 className="font-display font-black text-2xl mt-1" style={{ color: t.accent }}>{t.name}</h2>
            <div className="mt-4 flex items-baseline gap-2">
              <span className="font-display font-black text-4xl" style={{ color: t.accent }}>{t.price}</span>
              <span className="text-white/40 text-sm">ر.س / {t.duration}</span>
            </div>
            <ul className="mt-5 space-y-2 text-sm flex-1">
              {t.perks.map((p, i) => (
                <li key={i} className="flex items-start gap-2 text-white/80">
                  <Check size={14} className="mt-0.5 shrink-0" style={{ color: t.accent }} />
                  <span>{p}</span>
                </li>
              ))}
            </ul>
            {t.id === "trial" ? (
              <button
                data-testid={`cta-${t.id}`}
                onClick={() => navigate("/me")}
                className="mt-6 w-full py-3 rounded-md border b-soft text-sm hover:bg-white/5"
              >
                {trialActive ? "اذهب إلى ملفك الشخصي ←" : t.cta}
              </button>
            ) : (
              <button
                data-testid={`cta-${t.id}`}
                disabled={busyTier === t.id}
                onClick={() => mockCheckout(t.id)}
                className="mt-6 w-full py-3 rounded-md font-bold text-black disabled:opacity-60"
                style={{ background: t.accent }}
              >
                {busyTier === t.id ? "..." : t.cta}
              </button>
            )}
          </article>
        ))}
      </section>

      <section className="bg-surface border b-soft rounded-2xl p-6 md:p-8">
        <h2 className="font-display font-black text-2xl mb-5">ماذا تحصل عليه؟</h2>
        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <FeatureCell icon={<ImageIcon size={18} />} title="أفاتار مخصص" body="رفع صورة شخصية تظهر في ملفك وكل المحادثات." />
          <FeatureCell icon={<ImageIcon size={18} />} title="بانر شخصي" body="خلفية كاملة لملفك تعطيك هوية بصرية واضحة." />
          <FeatureCell icon={<Palette size={18} />} title="لون مميز" body="اختر hex مخصص يلوّن اسمك وعداداتك." />
          <FeatureCell icon={<ShieldCheck size={18} />} title="شارة Plus" body="شارة تظهر بجوار اسمك في الشات والترتيب." />
        </div>
      </section>

      <section className="text-center py-10">
        <Trophy size={32} className="mx-auto mb-3 text-gold-500" />
        <h3 className="font-display font-black text-2xl">جاهز تبرز بين اللاعبين؟</h3>
        <button
          data-testid="cta-bottom"
          onClick={() => mockCheckout("monthly")}
          className="mt-5 px-6 py-3 rounded-md bg-gold-500 text-black font-bold hover:bg-gold-400"
        >
          فعّل Personal Plus
        </button>
      </section>
    </div>
  );
}

function FeatureCell({ icon, title, body }) {
  return (
    <div className="bg-background/40 border b-soft rounded-lg p-4">
      <div className="h-9 w-9 rounded-md bg-gold-500/10 grid place-items-center text-gold-500">{icon}</div>
      <div className="mt-3 font-bold">{title}</div>
      <div className="text-xs text-white/60 mt-1">{body}</div>
    </div>
  );
}
