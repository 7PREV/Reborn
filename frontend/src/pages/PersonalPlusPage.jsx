import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Sparkles, Check, Crown, Image as ImageIcon, Palette, Star, ShieldCheck, Trophy, Users, Swords } from "lucide-react";
import { toast } from "sonner";
import { useAuth } from "../AuthContext";

const TIERS = [
  {
    id: "personal",
    name: "Personal Plus",
    arabicSubtitle: "البلس الشخصي",
    price: "12.99",
    duration: "شهرياً",
    cta: "اشترك الآن",
    color: "border-gold-500/50",
    accent: "#FFCC00",
    badge: "للاعب الفردي",
    icon: <Sparkles size={22} />,
    perks: [
      "صورة شخصية مخصصة (≤2MB)",
      "بانر خلفية كامل (≤3MB)",
      "اختيار لون مميز يظهر في ملفك",
      "شارة Plus حصرية في الشات",
      "تجربة مجانية 3 أيام عند التسجيل",
      "أولوية في طلبات الدعم",
    ],
  },
  {
    id: "clan",
    name: "Clan Plus",
    arabicSubtitle: "بلس الكلانات",
    price: "26.99",
    duration: "شهرياً",
    cta: "اشترك للكلان",
    color: "border-emerald-500/50",
    accent: "#22D3A4",
    badge: "للقادة وأبطال الكلانات",
    icon: <Crown size={22} />,
    perks: [
      "زيادة سعة الكلان من 7 إلى 12 لاعب",
      "تعيين نائبَين للقائد بدل نائب واحد",
      "أولوية الوصول للبطولات الحصرية",
      "هالة ذهبية متحركة على اسم الكلان في الترتيب",
      "إعلان مميز عند بدء مباراة كلانك",
      "دعم أولوية في النزاعات",
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
          <Sparkles size={12} /> اشتراكات RIVALS
        </div>
        <h1 className="font-display font-black text-5xl md:text-6xl">PLUS</h1>
        <p className="text-white/60 mt-3 max-w-xl mx-auto text-sm md:text-base">
          خصّص ملفك الشخصي أو ارفع مستوى كلانك. اختر الباقة التي تناسبك:
          باقة شخصية فردية أو باقة كاملة للكلان.
        </p>
        {trialActive && user?.personal_plus_until && (
          <div data-testid="plus-trial-banner" className="inline-flex items-center gap-2 bg-gold-500/10 border border-gold-500/30 rounded-full px-4 py-2 mt-5 text-sm text-gold-500">
            <Crown size={14} /> Personal Plus التجريبية مفعّلة حتى {new Date(user.personal_plus_until).toLocaleDateString("ar")}
          </div>
        )}
      </header>

      <section className="grid md:grid-cols-2 gap-6 max-w-4xl mx-auto">
        {TIERS.map((t) => (
          <article
            key={t.id}
            data-testid={`plus-tier-${t.id}`}
            className={`relative bg-surface border ${t.color} rounded-2xl p-8 flex flex-col overflow-hidden`}
          >
            <div
              className="absolute -top-12 -left-12 w-44 h-44 rounded-full opacity-10 blur-3xl"
              style={{ background: t.accent }}
            />
            <div className="relative">
              <div className="flex items-center gap-3 mb-2">
                <div className="h-11 w-11 rounded-lg grid place-items-center" style={{ background: `${t.accent}1a`, color: t.accent }}>
                  {t.icon}
                </div>
                <div className="text-[10px] uppercase tracking-widest text-white/40">{t.badge}</div>
              </div>
              <h2 className="font-display font-black text-3xl" style={{ color: t.accent }}>{t.name}</h2>
              <div className="text-white/60 text-sm mt-1">{t.arabicSubtitle}</div>
              <div className="mt-6 flex items-baseline gap-2">
                <span className="font-display font-black text-5xl" style={{ color: t.accent }}>{t.price}</span>
                <span className="text-white/40 text-sm">ر.س / {t.duration}</span>
              </div>
              <ul className="mt-6 space-y-2.5 text-sm">
                {t.perks.map((p, i) => (
                  <li key={i} className="flex items-start gap-2 text-white/80">
                    <Check size={15} className="mt-0.5 shrink-0" style={{ color: t.accent }} />
                    <span>{p}</span>
                  </li>
                ))}
              </ul>
              <button
                data-testid={`cta-${t.id}`}
                disabled={busyTier === t.id}
                onClick={() => mockCheckout(t.id)}
                className="mt-7 w-full py-3.5 rounded-md font-bold text-black text-base disabled:opacity-60 hover:opacity-90 transition"
                style={{ background: t.accent }}
              >
                {busyTier === t.id ? "..." : t.cta}
              </button>
              <p className="text-[10px] text-white/40 text-center mt-2">دفع آمن • إلغاء في أي وقت</p>
            </div>
          </article>
        ))}
      </section>

      <section className="bg-surface border b-soft rounded-2xl p-6 md:p-8 max-w-4xl mx-auto">
        <h2 className="font-display font-black text-2xl mb-5">مقارنة سريعة</h2>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-white/40 text-xs uppercase tracking-widest">
                <th className="text-right py-2">الميزة</th>
                <th className="text-center py-2">Personal Plus</th>
                <th className="text-center py-2">Clan Plus</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5">
              <ComparisonRow label="تخصيص الأفاتار والبانر" left right={false} />
              <ComparisonRow label="لون شخصي مميز" left right={false} />
              <ComparisonRow label="شارة Plus في الشات" left right={false} />
              <ComparisonRow label="زيادة سعة الكلان إلى 12 لاعب" left={false} right />
              <ComparisonRow label="نائب إضافي للقائد" left={false} right />
              <ComparisonRow label="هالة متحركة في الترتيب" left={false} right />
              <ComparisonRow label="أولوية في الدعم" left right />
            </tbody>
          </table>
        </div>
      </section>

      <section className="text-center py-10">
        <Trophy size={32} className="mx-auto mb-3 text-gold-500" />
        <h3 className="font-display font-black text-2xl">جاهز تبرز بين اللاعبين والكلانات؟</h3>
        <div className="mt-5 flex flex-wrap gap-3 justify-center">
          <button
            data-testid="cta-bottom-personal"
            onClick={() => mockCheckout("personal")}
            className="px-5 py-3 rounded-md bg-gold-500 text-black font-bold hover:bg-gold-400 flex items-center gap-2"
          >
            <Sparkles size={14} /> Personal Plus
          </button>
          <button
            data-testid="cta-bottom-clan"
            onClick={() => mockCheckout("clan")}
            className="px-5 py-3 rounded-md bg-emerald-400 text-black font-bold hover:bg-emerald-300 flex items-center gap-2"
          >
            <Crown size={14} /> Clan Plus
          </button>
        </div>
      </section>
    </div>
  );
}

function ComparisonRow({ label, left, right }) {
  return (
    <tr>
      <td className="py-3 text-white/80">{label}</td>
      <td className="text-center">{left ? <Check size={16} className="text-gold-500 inline" /> : <span className="text-white/20">—</span>}</td>
      <td className="text-center">{right ? <Check size={16} className="text-emerald-400 inline" /> : <span className="text-white/20">—</span>}</td>
    </tr>
  );
}
