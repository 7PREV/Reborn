import { useEffect, useMemo, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../AuthContext";

const TOUR_KEY = "reborn_onboarding_v1_done";

const STEPS = [
  {
    id: "step-home",
    path: "/",
    selector: '[data-testid="nav-home"]',
    title: "أهلاً بك 👋",
    text: "هنا تبدأ رحلتك. من الرئيسية تتابع الأخبار والإعلانات المهمة.",
  },
  {
    id: "step-clans",
    path: "/clans",
    selector: '[data-testid="nav-clans"]',
    title: "الكلانات",
    text: "أنشئ كلانك أو انضم لفريقك، وادخل المنافسات الرسمية بسهولة.",
  },
  {
    id: "step-matches",
    path: "/matches",
    selector: '[data-testid="nav-matches"]',
    title: "المباريات",
    text: "من هنا تدير التحديات، الشات، التصويت، وبريك الصلاة التكتيكي.",
  },
  {
    id: "step-profile",
    path: "/me",
    selector: '[data-testid="profile-link"]',
    title: "ملفك الشخصي",
    text: "أكمل بياناتك وفعّل حضورك وتابع تقدمك داخل المنصة.",
  },
];

function clearHighlight(node) {
  if (!node) return;
  node.style.outline = "";
  node.style.outlineOffset = "";
  node.style.borderRadius = "";
  node.style.boxShadow = "";
}

function applyHighlight(node) {
  if (!node) return;
  node.scrollIntoView({ behavior: "smooth", block: "center", inline: "center" });
  node.style.outline = "2px solid rgba(16,185,129,0.85)";
  node.style.outlineOffset = "4px";
  node.style.borderRadius = "10px";
  node.style.boxShadow = "0 0 0 8px rgba(16,185,129,0.15)";
}

export default function OnboardingTour() {
  const { user, loading } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();

  const [open, setOpen] = useState(false);
  const [index, setIndex] = useState(0);

  const step = useMemo(() => STEPS[index], [index]);

  useEffect(() => {
    if (loading) return;
    if (!user?.id) return;
    if (localStorage.getItem(TOUR_KEY) === "1") return;
    setOpen(true);
    setIndex(0);
  }, [loading, user?.id]);

  useEffect(() => {
    if (!open || !step) return undefined;
    if (location.pathname !== step.path) {
      navigate(step.path);
      return undefined;
    }

    let active = null;
    const timer = setTimeout(() => {
      active = document.querySelector(step.selector);
      applyHighlight(active);
    }, 160);

    return () => {
      clearTimeout(timer);
      clearHighlight(active);
    };
  }, [open, step, location.pathname, navigate]);

  const finish = () => {
    localStorage.setItem(TOUR_KEY, "1");
    setOpen(false);
  };

  const skip = () => finish();

  const next = () => {
    if (index >= STEPS.length - 1) {
      finish();
      return;
    }
    setIndex((v) => v + 1);
  };

  if (!open || !step) return null;

  return (
    <div className="fixed inset-0 z-[1200] bg-black/55 backdrop-blur-[1px]" dir="rtl">
      <div className="absolute left-1/2 top-[14%] -translate-x-1/2 w-[min(92vw,560px)] rounded-2xl border border-white/15 bg-[#111217] p-5 shadow-[0_25px_90px_rgba(0,0,0,0.55)]">
        <div className="text-[10px] uppercase tracking-widest text-emerald-300/90 mb-1">جولة تعريفية</div>
        <h3 className="text-xl font-black text-white">{step.title}</h3>
        <p className="mt-2 text-sm text-white/75 leading-7">{step.text}</p>

        <div className="mt-5 flex items-center justify-between gap-2">
          <button
            onClick={skip}
            className="px-3 py-2 rounded-md border border-white/15 text-white/70 hover:bg-white/5 text-sm"
          >
            تخطي
          </button>
          <div className="text-xs text-white/55">{index + 1} / {STEPS.length}</div>
          <button
            onClick={next}
            className="px-4 py-2 rounded-md bg-emerald-500 text-black font-bold hover:bg-emerald-400 text-sm"
          >
            {index === STEPS.length - 1 ? "ابدأ الآن" : "التالي"}
          </button>
        </div>
      </div>
    </div>
  );
}
