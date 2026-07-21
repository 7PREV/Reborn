import { useState } from "react";
import { useNavigate, Link, useLocation } from "react-router-dom";
import { useAuth } from "../AuthContext";
import { formatApiErrorDetail } from "../api";
import { toast } from "sonner";

export default function AuthPage() {
  const { login, register, forgotPassword, resetPassword } = useAuth();
  const [tab, setTab] = useState("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [otp, setOtp] = useState("");
  const [otpRequired, setOtpRequired] = useState(false);
  const [username, setUsername] = useState("");
  const [act, setAct] = useState("");
  const [forgotMode, setForgotMode] = useState(false);
  const [resetOtpSent, setResetOtpSent] = useState(false);
  const [resetPasswordValue, setResetPasswordValue] = useState("");
  const [resetPasswordConfirm, setResetPasswordConfirm] = useState("");
  const [acceptedTerms, setAcceptedTerms] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const navigate = useNavigate();
  const location = useLocation();
  const referralCode = new URLSearchParams(location.search || "").get("ref") || "";

  const resetFlowState = () => {
    setOtp("");
    setOtpRequired(false);
    setForgotMode(false);
    setResetOtpSent(false);
    setResetPasswordValue("");
    setResetPasswordConfirm("");
  };

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      if (forgotMode) {
        if (!email) {
          setError("اكتب بريدك الإلكتروني أولاً");
          setLoading(false);
          return;
        }
        if (!resetOtpSent) {
          await forgotPassword(email);
          setResetOtpSent(true);
          toast.success("تم إرسال رمز التحقق إلى بريدك الإلكتروني");
          setLoading(false);
          return;
        }
        if (!otp.trim()) {
          setError("اكتب رمز التحقق");
          setLoading(false);
          return;
        }
        if (!resetPasswordValue || resetPasswordValue.length < 6) {
          setError("كلمة المرور الجديدة يجب أن تكون 6 أحرف على الأقل");
          setLoading(false);
          return;
        }
        if (resetPasswordValue !== resetPasswordConfirm) {
          setError("تأكيد كلمة المرور غير مطابق");
          setLoading(false);
          return;
        }
        await resetPassword(email, otp.trim(), resetPasswordValue);
        toast.success("تم تحديث كلمة المرور بنجاح");
        setForgotMode(false);
        setResetOtpSent(false);
        setOtp("");
        setResetPasswordValue("");
        setResetPasswordConfirm("");
        setLoading(false);
        return;
      }

      if (tab === "login") {
        const data = await login(email, password, otpRequired ? otp.trim() : "");
        if (data?.otp_required) {
          setOtpRequired(true);
          toast.success("تم إرسال رمز التحقق إلى بريدك الإلكتروني");
          setLoading(false);
          return;
        }
      } else {
        if (!acceptedTerms) {
          setError("يجب الموافقة على الشروط والأحكام قبل التسجيل");
          setLoading(false);
          return;
        }
        const data = await register({
          email,
          password,
          username,
          act,
          accepted_terms: true,
          otp: otpRequired ? otp.trim() : undefined,
          referral_code: referralCode || undefined,
        });
        if (data?.otp_required) {
          setOtpRequired(true);
          toast.success("تم إرسال رمز التحقق إلى بريدك الإلكتروني");
          setLoading(false);
          return;
        }
      }
      toast.success("مرحباً بك في Rivals");
      setOtp("");
      setOtpRequired(false);
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
          src="/3813CF8E-31A7-44BD-A1EF-32BB702BF479.png"
          alt="stadium"
          className="absolute inset-0 w-full h-full object-cover"
        />
        <div className="absolute inset-0 bg-gradient-to-l from-[#0a0a0b] via-[#0a0a0b99] to-transparent" />
        <div className="relative p-16 flex flex-col justify-end">
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

          <div className="mt-10">
            <div className="grid grid-cols-2 items-center bg-gradient-to-l from-surface/95 via-surface to-background/90 border border-royalGold-500/20 rounded-2xl p-1.5 shadow-[0_6px_30px_rgba(0,0,0,0.35)] backdrop-blur-sm">
              <button
                data-testid="tab-login"
                onClick={() => {
                  setTab("login");
                  resetFlowState();
                }}
                className={`py-2.5 rounded-xl text-sm inline-flex items-center justify-center gap-2 transition-all duration-200 border ${
                  tab === "login"
                    ? "bg-gradient-to-l from-royalGold-700 via-royalGold-600 to-royalGold-500 text-white font-extrabold border-royalGold-300/40 shadow-[0_0_15px_rgba(203,213,225,0.22)]"
                    : "text-gray-400 border-transparent hover:text-white hover:bg-white/5"
                }`}
              >
                تسجيل الدخول
              </button>
              <button
                data-testid="tab-register"
                onClick={() => {
                  setTab("register");
                  resetFlowState();
                }}
                className={`py-2.5 rounded-xl text-sm inline-flex items-center justify-center gap-2 transition-all duration-200 border ${
                  tab === "register"
                    ? "bg-gradient-to-l from-royalGold-700 via-royalGold-600 to-royalGold-500 text-white font-extrabold border-royalGold-300/40 shadow-[0_0_15px_rgba(203,213,225,0.22)]"
                    : "text-gray-400 border-transparent hover:text-white hover:bg-white/5"
                }`}
              >
                إنشاء حساب
              </button>
            </div>
            <div className="mt-2 h-px w-full bg-gradient-to-l from-transparent via-royalGold-500/50 to-transparent" />
          </div>

          <form onSubmit={submit} className="mt-6 space-y-4" data-testid="auth-form">
            {!forgotMode && tab === "register" && (
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
            {!forgotMode && tab === "register" && (
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
            {!forgotMode && (
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
            )}

            {forgotMode && (
              <>
                {resetOtpSent && (
                  <div>
                    <label className="text-xs uppercase tracking-widest text-white/50 mb-2 block">
                      رمز التحقق (OTP)
                    </label>
                    <input
                      data-testid="input-reset-otp"
                      value={otp}
                      onChange={(e) => setOtp(e.target.value)}
                      required
                      className="w-full bg-surface border b-soft rounded-md px-4 py-3 outline-none focus:border-gold-500/50 placeholder-white/30"
                      placeholder="000000"
                    />
                  </div>
                )}
                {resetOtpSent && (
                  <>
                    <div>
                      <label className="text-xs uppercase tracking-widest text-white/50 mb-2 block">
                        كلمة المرور الجديدة
                      </label>
                      <input
                        data-testid="input-new-password"
                        type="password"
                        value={resetPasswordValue}
                        onChange={(e) => setResetPasswordValue(e.target.value)}
                        required
                        minLength={6}
                        className="w-full bg-surface border b-soft rounded-md px-4 py-3 outline-none focus:border-gold-500/50 placeholder-white/30"
                        placeholder="••••••••"
                      />
                    </div>
                    <div>
                      <label className="text-xs uppercase tracking-widest text-white/50 mb-2 block">
                        تأكيد كلمة المرور
                      </label>
                      <input
                        data-testid="input-new-password-confirm"
                        type="password"
                        value={resetPasswordConfirm}
                        onChange={(e) => setResetPasswordConfirm(e.target.value)}
                        required
                        minLength={6}
                        className="w-full bg-surface border b-soft rounded-md px-4 py-3 outline-none focus:border-gold-500/50 placeholder-white/30"
                        placeholder="••••••••"
                      />
                    </div>
                  </>
                )}
              </>
            )}

            {!forgotMode && otpRequired && (
              <div>
                <label className="text-xs uppercase tracking-widest text-white/50 mb-2 block">
                  رمز التحقق (OTP)
                </label>
                <input
                  data-testid="input-otp"
                  value={otp}
                  onChange={(e) => setOtp(e.target.value)}
                  required
                  className="w-full bg-surface border b-soft rounded-md px-4 py-3 outline-none focus:border-gold-500/50 placeholder-white/30"
                  placeholder="000000"
                />
                <div className="text-[10px] text-white/40 mt-1">أدخل الرمز الذي تم إرساله إلى بريدك الإلكتروني</div>
              </div>
            )}

            {error && (
              <div data-testid="auth-error" className="text-sm text-destructive border border-destructive/30 rounded-md p-3 bg-destructive/10">
                {error}
              </div>
            )}

            {!forgotMode && tab === "register" && (
              <div className="text-[11px] text-emerald-300/90 border border-emerald-500/25 bg-emerald-500/10 rounded-md px-3 py-2">
                {referralCode ? `تم تطبيق كود الإحالة: ${referralCode}` : "يمكنك التسجيل عبر رابط إحالة لكسب داعيك مكافأة RIV"}
              </div>
            )}

            {!forgotMode && tab === "register" && (
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
              {loading
                ? "..."
                : forgotMode
                  ? (resetOtpSent ? "تحديث كلمة المرور" : "إرسال رمز الاستعادة")
                  : (otpRequired ? "تحقق من الرمز" : (tab === "login" ? "دخول" : "إنشاء الحساب"))}
            </button>

            {tab === "login" && !otpRequired && !forgotMode && (
              <button
                data-testid="forgot-password-btn"
                type="button"
                onClick={() => {
                  setForgotMode(true);
                  setResetOtpSent(false);
                  setOtp("");
                }}
                className="w-full text-xs text-gold-500/80 hover:text-gold-500 underline-offset-4 hover:underline"
              >
                نسيت كلمة المرور؟
              </button>
            )}

            {forgotMode && (
              <button
                data-testid="cancel-forgot-password-btn"
                type="button"
                onClick={() => {
                  setForgotMode(false);
                  setResetOtpSent(false);
                  setOtp("");
                  setResetPasswordValue("");
                  setResetPasswordConfirm("");
                }}
                className="w-full text-xs text-white/50 hover:text-white/80 underline-offset-4 hover:underline"
              >
                إلغاء استعادة كلمة المرور
              </button>
            )}
          </form>

          <div className="my-6 flex items-center gap-3 text-white/30 text-xs">
            <div className="flex-1 h-px bg-white/10" />
            <span>أو</span>
            <div className="flex-1 h-px bg-white/10" />
          </div>

          <button
            data-testid="google-login-disabled"
            disabled
            className="w-full py-3 rounded-md border b-soft text-white/60 font-semibold transition flex items-center justify-center gap-2 text-sm"
            title="Google login coming soon"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden>
              <path d="M23.5 12.3c0-.8-.1-1.6-.2-2.3H12v4.4h6.5c-.3 1.4-1.1 2.7-2.3 3.5v2.9h3.7c2.1-1.9 3.6-4.8 3.6-8.5Z" fill="#4285F4"/>
              <path d="M12 24c3.2 0 5.8-1 7.8-2.8l-3.7-2.9c-1 .7-2.4 1.2-4.1 1.2-3.1 0-5.7-2.1-6.6-4.9H1.6v3c2 3.9 6 6.4 10.4 6.4Z" fill="#34A853"/>
              <path d="M5.4 14.6c-.2-.7-.4-1.5-.4-2.3s.1-1.6.4-2.3v-3H1.6A12 12 0 0 0 0 12.3c0 1.9.5 3.8 1.6 5.3l3.8-3Z" fill="#FBBC05"/>
              <path d="M12 4.8c1.8 0 3.4.6 4.7 1.8l3.5-3.5C17.8 1.1 15.2 0 12 0 7.6 0 3.6 2.5 1.6 6.9l3.8 3c.9-2.8 3.5-5 6.6-5Z" fill="#EA4335"/>
            </svg>
            <span>Google (قريباً)</span>
          </button>

        </div>
      </div>
    </div>
  );
}
