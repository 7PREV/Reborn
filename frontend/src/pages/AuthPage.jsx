import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { useAuth } from "../AuthContext";
import { formatApiErrorDetail } from "../api";
import { toast } from "sonner";

export default function AuthPage() {
  const { login, register } = useAuth();
  const [tab, setTab] = useState("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [username, setUsername] = useState("");
  const [act, setAct] = useState("");
  const [acceptedTerms, setAcceptedTerms] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const navigate = useNavigate();

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      if (tab === "login") {
        await login(email, password);
      } else {
        if (!acceptedTerms) {
          setError("يجب الموافقة على الشروط والأحكام قبل التسجيل");
          setLoading(false);
          return;
        }
        await register({ email, password, username, act, accepted_terms: true });
      }
      toast.success("مرحباً بك في Rivals");
      navigate("/");
    } catch (err) {
      const msg = formatApiErrorDetail(err.response?.data?.detail) || err.message;
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex" dir="rtl">
      <div className="hidden lg:flex flex-1 relative grain overflow-hidden">
        <img
          src="https://static.prod-images.emergentagent.com/jobs/6e794572-9280-4c42-a6f5-c2e716461871/images/142994e1feb9d2aec8d9cc127fa5cab3debfae6c2920a6a272eb5fed5d813118.png"
          alt="stadium"
          className="absolute inset-0 w-full h-full object-cover"
        />
        <div className="absolute inset-0 bg-gradient-to-l from-[#0a0a0b] via-[#0a0a0b99] to-transparent" />
        <div className="relative p-16 flex flex-col justify-end">
          <div className="text-xs uppercase tracking-[0.3em] text-gold-500 mb-3">
            دوري RIVALS • Call of Duty
          </div>
          <h1 className="font-display font-black text-5xl xl:text-7xl leading-[1.05]">
            ادخل الحلبة.<br />
            <span className="gold-text">اقد كلانك.</span><br />
            احتل القمة.
          </h1>
          <p className="mt-6 text-white/60 text-base max-w-md">
            انضم لأكبر شبكة كلانات في المنطقة، انشئ تحديات، تابع المباريات الحية ولوحات التصدر.
          </p>
        </div>
      </div>

      <div className="flex-1 flex items-center justify-center p-6 lg:p-12">
        <div className="w-full max-w-md">
          <Link to="/" className="font-display font-black text-2xl">
            RIVALS<span className="text-gold-500">.</span>
          </Link>
          <div className="text-[10px] uppercase tracking-[0.25em] text-white/40 mt-1">دوري Call of Duty</div>

          <div className="mt-10 grid grid-cols-2 bg-surface rounded-md border b-soft p-1">
            <button
              data-testid="tab-login"
              onClick={() => setTab("login")}
              className={`py-2 rounded text-sm transition ${
                tab === "login" ? "bg-gold-500 text-black font-bold" : "text-white/60"
              }`}
            >
              تسجيل الدخول
            </button>
            <button
              data-testid="tab-register"
              onClick={() => setTab("register")}
              className={`py-2 rounded text-sm transition ${
                tab === "register" ? "bg-gold-500 text-black font-bold" : "text-white/60"
              }`}
            >
              إنشاء حساب
            </button>
          </div>

          <form onSubmit={submit} className="mt-6 space-y-4" data-testid="auth-form">
            {tab === "register" && (
              <div>
                <label className="text-xs uppercase tracking-widest text-white/50 mb-2 block">
                  اسم المستخدم
                </label>
                <input
                  data-testid="input-username"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  required
                  minLength={2}
                  className="w-full bg-surface border b-soft rounded-md px-4 py-3 outline-none focus:border-gold-500/50 placeholder-white/30"
                  placeholder="ProGamer"
                />
              </div>
            )}
            {tab === "register" && (
              <div>
                <label className="text-xs uppercase tracking-widest text-white/50 mb-2 block">
                  Activision ID (داخل اللعبة)
                </label>
                <input
                  data-testid="input-act"
                  value={act}
                  onChange={(e) => setAct(e.target.value)}
                  required
                  minLength={2}
                  maxLength={40}
                  className="w-full bg-surface border b-soft rounded-md px-4 py-3 outline-none focus:border-gold-500/50 placeholder-white/30"
                  placeholder="YourName#1234"
                />
                <div className="text-[10px] text-white/40 mt-1">اسمك داخل لعبة Call of Duty (إلزامي)</div>
              </div>
            )}
            <div>
              <label className="text-xs uppercase tracking-widest text-white/50 mb-2 block">
                البريد الإلكتروني
              </label>
              <input
                data-testid="input-email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                className="w-full bg-surface border b-soft rounded-md px-4 py-3 outline-none focus:border-gold-500/50 placeholder-white/30"
                placeholder="you@rivals.gg"
              />
            </div>
            <div>
              <label className="text-xs uppercase tracking-widest text-white/50 mb-2 block">
                كلمة المرور
              </label>
              <input
                data-testid="input-password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                minLength={6}
                className="w-full bg-surface border b-soft rounded-md px-4 py-3 outline-none focus:border-gold-500/50 placeholder-white/30"
                placeholder="••••••••"
              />
            </div>

            {error && (
              <div data-testid="auth-error" className="text-sm text-destructive border border-destructive/30 rounded-md p-3 bg-destructive/10">
                {error}
              </div>
            )}

            {tab === "register" && (
              <label className="flex items-start gap-2 cursor-pointer text-xs text-white/70" data-testid="terms-label">
                <input
                  data-testid="accept-terms"
                  type="checkbox"
                  checked={acceptedTerms}
                  onChange={(e) => setAcceptedTerms(e.target.checked)}
                  className="mt-0.5 accent-gold-500 h-4 w-4"
                />
                <span>
                  أوافق على{" "}
                  <a href="/rules" target="_blank" rel="noreferrer" className="text-gold-500 hover:underline">
                    الشروط والأحكام وسياسة الخصوصية
                  </a>
                </span>
              </label>
            )}

            <button
              data-testid="auth-submit"
              type="submit"
              disabled={loading}
              className="w-full py-3 rounded-md bg-gold-500 text-black font-bold hover:bg-gold-400 disabled:opacity-50 transition-colors"
            >
              {loading ? "..." : tab === "login" ? "دخول" : "إنشاء الحساب"}
            </button>

            {tab === "login" && (
              <button
                data-testid="forgot-password-btn"
                type="button"
                onClick={async () => {
                  if (!email) { setError("اكتب بريدك الإلكتروني أولاً"); return; }
                  try {
                    const apiMod = await import("../api");
                    await apiMod.default.post("/auth/forgot-password", { email });
                    toast.success("تم إرسال طلب استعادة كلمة المرور. سيتواصل معك المنظم قريباً.");
                  } catch (err) {
                    setError(err.response?.data?.detail || "فشل الإرسال");
                  }
                }}
                className="w-full text-xs text-gold-500/80 hover:text-gold-500 underline-offset-4 hover:underline"
              >
                نسيت كلمة المرور؟
              </button>
            )}
          </form>

          <div className="my-6 flex items-center gap-3 text-white/30 text-xs">
            <div className="flex-1 h-px bg-white/10" />
            <span>أو</span>
            <div className="flex-1 h-px bg-white/10" />
          </div>

          <button
            data-testid="google-login"
            onClick={() => toast.info("تسجيل Google قريباً")}
            className="w-full py-3 rounded-md border b-soft hover:bg-white/5 transition flex items-center justify-center gap-2 text-sm"
          >
            <span className="text-base">G</span>
            <span>متابعة مع Google</span>
          </button>

          <p className="mt-8 text-xs text-white/30 text-center">
            حساب تجريبي: admin@rivals.gg / Admin@12345
          </p>
        </div>
      </div>
    </div>
  );
}
