import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Sparkles, Check, Crown, Image as ImageIcon, Palette, Star, ShieldCheck, Trophy, Users, Swords } from "lucide-react";
import { toast } from "sonner";
import { useAuth } from "../AuthContext";
import api, { formatApiErrorDetail } from "../api";

const TIERS = [
  {
    id: "personal",
    name: "Personal Plus",
    arabicSubtitle: "البلس الشخصي",
    price: "10.99",
    duration: "شهرياً",
    currency: "ر.س",
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
    ],
  },
  {
    id: "clan",
    name: "Clan Plus",
    arabicSubtitle: "بلس الكلانات",
    price: "26.99",
    duration: "شهرياً",
    currency: "ر.س",
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
    ],
  },
];

export default function PersonalPlusPage() {
  const { user, refresh } = useAuth();
  const [busyTier, setBusyTier] = useState(null);
  const [busyRivTier, setBusyRivTier] = useState(null);
  const navigate = useNavigate();

  const mockCheckout = (tierId) => {
    setBusyTier(tierId);
    setTimeout(() => {
      setBusyTier(null);
      toast.success("🚧 الدفع قيد التطوير — سيتم تفعيل الاشتراك عند ربط بوابة الدفع");
    }, 1100);
  };

  const checkoutWithRiv = async (tierId) => {
    setBusyRivTier(tierId);
    try {
      const plan = tierId === "personal" ? "person_plus" : "clan_plus";
      const { data } = await api.post("/billing/checkout", {
        plan,
        provider: "riv_points",
        pay_with_riv_points: true,
      });
      await refresh();
      toast.success(`تم الدفع بنقاط RIV بنجاح • الرصيد المتبقي: ${data?.riv_points ?? "--"} RIV`);
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail));
    } finally {
      setBusyRivTier(null);
    }
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
        <div className="mt-4 text-emerald-300 font-semibold">🪙 رصيدك الحالي: {Number(user?.riv_points || 0)} RIV</div>
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
              <div className="mt-6 flex flex-col items-start gap-1 leading-tight">
                <span className="font-display font-black text-5xl leading-none" style={{ color: t.accent }}>{t.price}</span>
                <span className="text-white/50 text-sm whitespace-nowrap inline-flex items-center gap-1">
                  <span className="font-semibold">{t.currency}</span>
                  <span className="text-white/35">/</span>
                  <span>{t.duration}</span>
                </span>
              </div>
              <ul className="mt-6 space-y-2.5 text-sm">
                {t.perks.map((p) => (
                  <li key={p} className="flex items-start gap-2 text-white/80">
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
              <button
                data-testid={`cta-riv-${t.id}`}
                disabled={busyRivTier === t.id}
                onClick={() => checkoutWithRiv(t.id)}
                className="mt-2 w-full py-3 rounded-md font-bold text-sm border border-emerald-500/40 text-emerald-300 hover:bg-emerald-500/10 disabled:opacity-60"
              >
                {busyRivTier === t.id
                  ? "..."
                  : `Pay with RIV Points (${t.id === "personal" ? 11 : 27} RIV)`}
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
