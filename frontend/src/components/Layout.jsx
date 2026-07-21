import { useEffect, useMemo, useState } from "react";
import { Link, NavLink, useNavigate } from "react-router-dom";
import api, { formatApiErrorDetail, notificationsList, notificationsRead } from "../api";
import { useAuth } from "../AuthContext";
import { Users, Swords, LogOut, Shield, Home as HomeIcon, ScrollText, Crown, Sparkles, Award, ShieldOff, Trophy, Instagram, Twitch, Music2, Bell, Check, X } from "lucide-react";
import { Popover, PopoverContent, PopoverTrigger } from "./ui/popover";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "./ui/tabs";
import { toast } from "sonner";

const attendancePromptShownInCurrentPageLoad = new Set();

function resolveGuardSetupUrl() {
  const fallback = "/api/downloads/RivalsGuard.exe";
  const raw = (process.env.REACT_APP_GUARD_SETUP_URL || "").trim();
  if (!raw) return fallback;

  const repo = (process.env.REACT_APP_GITHUB_REPOSITORY || "").trim();
  if (repo && raw.includes("<OWNER>/<REPO>")) {
    return raw.replace("<OWNER>/<REPO>", repo);
  }
  return raw;
}

export default function Layout({ children }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const isPlusMember = !!(user?.is_plus || user?.is_personal_plus || user?.plan === "plus");
  const guardSetupUrl = resolveGuardSetupUrl();

  const nav = [
    { to: "/", label: "الرئيسية", icon: HomeIcon, id: "nav-home" },
    { to: "/matches", label: "المباريات", icon: Swords, id: "nav-matches" },
    { to: "/tournaments", label: "البطولات", icon: Award, id: "nav-tournaments" },
    { to: "/leagues", label: "الدوريات", icon: Award, id: "nav-leagues" },
    { to: "/clans", label: "الكلانات", icon: Shield, id: "nav-clans" },
    { to: "/players", label: "اللاعبون", icon: Users, id: "nav-players" },
    { to: "/news", label: "الأخبار", icon: ScrollText, id: "nav-news" },
    { to: "/champions", label: "الأبطال", icon: Trophy, id: "nav-champions-factory" },
    { to: "/rules", label: "القوانين", icon: ScrollText, id: "nav-rules" },
    { to: "/plus", label: "PLUS", icon: Sparkles, id: "nav-plus" },
    { to: "/blacklist", label: "القائمة السوداء", icon: ShieldOff, id: "nav-blacklist" },
  ];

  return (
    <div className="min-h-screen bg-background text-foreground" dir="rtl">
      <TimedAttendanceCheckInBanner user={user} />

      <header className="sticky top-0 z-40 border-b b-soft bg-[#0a0a0bcc] backdrop-blur-xl">
        <div className="container flex items-center gap-6 h-16">
          {user && (user.role === "admin" || user.role === "owner") && (
            <NavLink
              to="/admin"
              data-testid="nav-admin"
              className="hidden md:inline-flex items-center gap-1.5 text-xs uppercase tracking-widest text-royalGold-500 hover:text-royalGold-400 border border-royalGold-500/30 rounded-md px-3 py-1.5"
            >
              <Crown size={14} /> {user.role === "owner" ? "لوحة المالك" : "لوحة الإدارة"}
            </NavLink>
          )}

          {user ? (
            <div className="flex items-center gap-3">
              <Link to="/me" data-testid="profile-link" className="flex items-center gap-2 group">
                <div className="relative h-9 w-9 rounded-md bg-surface border b-soft grid place-items-center font-display text-royalGold-500">
                  {user.username?.[0]?.toUpperCase() || "U"}
                  {isPlusMember && (
                    <Sparkles size={10} className="absolute -top-1 -right-1 text-[#d4af37] drop-shadow-[0_0_8px_rgba(212,175,55,0.55)]" />
                  )}
                </div>
                <div className="hidden sm:block text-right leading-tight">
                  <div className="text-sm font-semibold flex items-center gap-1">
                    {user.username}
                    {isPlusMember && <Sparkles size={10} className="text-[#d4af37] drop-shadow-[0_0_8px_rgba(212,175,55,0.55)]" />}
                  </div>
                  <div className="text-[10px] text-emerald-300/90 font-semibold">🪙 {Number(user?.riv_points || 0)} RIV</div>
                  <div className="text-[10px] uppercase tracking-widest text-white/40">
                    {user.role === "owner" ? "مالك" : user.role === "admin" ? "منظم" : isPlusMember ? "Plus" : "لاعب"}
                  </div>
                </div>
              </Link>
              <NotificationHub user={user} onNavigate={navigate} />
              <button
                onClick={() => { logout(); navigate("/auth"); }}
                data-testid="logout-btn"
                className="p-2 rounded-md hover:bg-white/5 text-white/50 hover:text-white"
                title="خروج"
              >
                <LogOut size={18} />
              </button>
            </div>
          ) : (
            <Link
              to="/auth"
              data-testid="auth-link"
              className="px-4 py-2 rounded-md bg-gold-500 text-black font-semibold hover:bg-gold-400 transition-colors"
            >
              دخول
            </Link>
          )}

          <nav className="hidden md:flex items-center gap-1">
            {nav.map((n) => (
              <NavLink
                key={n.to}
                to={n.to}
                end={n.to === "/"}
                data-testid={n.id}
                className={({ isActive }) =>
                  `px-3 py-2 rounded-md text-sm transition-colors flex items-center gap-2 ${n.to === "/rules" ? "whitespace-nowrap" : ""} ${
                    isActive
                      ? "bg-white/5 text-royalGold-500"
                      : "text-white/70 hover:text-white hover:bg-white/5"
                  }`
                }
              >
                <n.icon size={16} />
                <span>{n.label}</span>
              </NavLink>
            ))}
          </nav>

          <div className="flex-1" />

          <a
            href={guardSetupUrl}
            target="_blank"
            rel="noreferrer"
            data-testid="guard-setup-download"
            className="hidden md:inline-flex items-center gap-1.5 text-xs uppercase tracking-widest text-emerald-300 hover:text-emerald-200 border border-emerald-500/35 rounded-md px-3 py-1.5"
          >
            🛡️ Rivals Guard Setup
          </a>

       {/* قسم الشعار - يعرض الأيقونة البيضاء فقط ويخفي النص المدمج داخل الصورة تلقائياً */}
          <Link to="/" className="flex items-center group transition-transform duration-200 hover:scale-[1.05]" data-testid="logo-link">
            <div className="h-10 w-10 overflow-hidden relative flex items-center justify-center">
              <img 
                src="/logo.png" 
                alt="Rivals Icon" 
                className="h-10 max-w-none object-cover object-left" 
                style={{ width: '160%', transform: 'scale(1.2)' }}
              />
            </div>
          </Link>
        </div>

        <nav className="md:hidden flex items-center gap-1.5 px-2 pb-2 overflow-x-auto snap-x snap-mandatory [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
          {nav.map((n) => (
            <NavLink
              key={n.to}
              to={n.to}
              end={n.to === "/"}
              className={({ isActive }) =>
                `snap-start px-3 py-1.5 rounded-md text-xs whitespace-nowrap flex items-center gap-1 border ${n.to === "/rules" ? "whitespace-nowrap" : ""} ${
                  isActive ? "bg-white/5 text-royalGold-500 border-royalGold-500/35" : "text-white/60 border-white/10"
                }`
              }
            >
              <n.icon size={14} />
              {n.label}
            </NavLink>
          ))}
          {user?.role === "admin" || user?.role === "owner" ? (
            <NavLink
              to="/admin"
              className={({ isActive }) =>
                `px-3 py-1.5 rounded-md text-xs whitespace-nowrap flex items-center gap-1 ${
                  isActive ? "bg-white/5 text-royalGold-500" : "text-royalGold-500/70"
                }`
              }
            >
              <Crown size={14} /> {user.role === "owner" ? "المالك" : "الإدارة"}
            </NavLink>
          ) : null}
        </nav>
      </header>

      <main className="container py-8">{children}</main>

      <SiteFooter />
    </div>
  );
}

function TimedAttendanceCheckInBanner({ user }) {
  const [mounted, setMounted] = useState(false);
  const [visible, setVisible] = useState(false);
  const [progressShrink, setProgressShrink] = useState(false);
  const [checking, setChecking] = useState(false);

  const dismissBanner = () => {
    setVisible(false);
    setProgressShrink(false);
    setTimeout(() => setMounted(false), 260);
  };

  useEffect(() => {
    let cancelled = false;

    const checkShouldShow = async () => {
      if (!user?.id || !user?.clan_id) {
        setMounted(false);
        setVisible(false);
        setProgressShrink(false);
        return;
      }

      if (attendancePromptShownInCurrentPageLoad.has(user.id)) {
        return;
      }

      try {
        const { data } = await api.get(`/clans/${user.clan_id}/attendance`);
        if (cancelled) return;

        const isCheckedIn = !!data?.checked_in?.some((p) => p?.id === user.id);
        if (isCheckedIn) {
          setMounted(false);
          setVisible(false);
          setProgressShrink(false);
          return;
        }

        attendancePromptShownInCurrentPageLoad.add(user.id);
        setMounted(true);
        setVisible(true);
        setTimeout(() => {
          if (!cancelled) setProgressShrink(true);
        }, 40);
      } catch {
        // ignore quietly
      }
    };

    checkShouldShow();

    return () => {
      cancelled = true;
    };
  }, [user?.id, user?.clan_id]);

  useEffect(() => {
    if (!mounted) return undefined;
    const timer = setTimeout(() => {
      dismissBanner();
    }, 7000);
    return () => clearTimeout(timer);
  }, [mounted]);

  const handleCheckIn = async () => {
    if (!user?.clan_id || checking) return;
    setChecking(true);
    try {
      await api.post(`/clans/${user.clan_id}/attendance/checkin`);
      toast.success("✅ تم تسجيل حضورك بنجاح!");
      dismissBanner();
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail));
    } finally {
      setChecking(false);
    }
  };

  if (!mounted) return null;

  return (
    <div
      className={`fixed top-4 left-1/2 -translate-x-1/2 z-[999] w-[min(92vw,560px)] transition-all duration-300 ${
        visible ? "translate-y-0 opacity-100" : "-translate-y-6 opacity-0 pointer-events-none"
      }`}
      data-testid="timed-checkin-banner"
    >
      <div className="relative overflow-hidden bg-[#111113]/95 backdrop-blur-md border border-gray-800 rounded-2xl p-4 shadow-[0_8px_30px_rgba(0,0,0,0.45)]">
        <div className="text-center mb-3">
          <h3 className="text-base md:text-lg font-black text-white">🤔 ودك تحضر الحين؟</h3>
        </div>

        <div className="flex items-center justify-center gap-2.5">
          <button
            type="button"
            onClick={handleCheckIn}
            disabled={checking}
            className="px-5 py-2 rounded-xl bg-emerald-500 text-black font-black hover:bg-emerald-400 shadow-[0_0_20px_rgba(16,185,129,0.5)] hover:shadow-[0_0_24px_rgba(16,185,129,0.7)] transition-all disabled:opacity-60"
          >
            {checking ? "..." : "ايه"}
          </button>
          <button
            type="button"
            onClick={dismissBanner}
            className="px-5 py-2 rounded-xl border border-red-500/35 bg-red-500/10 text-red-300 font-bold hover:bg-red-500/20 hover:border-red-400/50 transition-all"
          >
            لا ماني فاضي
          </button>
        </div>

        <div className="absolute bottom-0 left-0 right-0 h-[3px] bg-white/10">
          <div
            className="h-full bg-gradient-to-l from-white to-emerald-400"
            style={{
              width: progressShrink ? "0%" : "100%",
              transitionProperty: "width",
              transitionDuration: "7000ms",
              transitionTimingFunction: "linear",
            }}
          />
        </div>
      </div>
    </div>
  );
}

function NotificationHub({ user, onNavigate }) {
  const [open, setOpen] = useState(false);
  const [tab, setTab] = useState("general");
  const [items, setItems] = useState([]);
  const [unread, setUnread] = useState(0);
  const [loading, setLoading] = useState(false);
  const [actingId, setActingId] = useState("");

  const reload = async () => {
    if (!user?.id) return;
    setLoading(true);
    try {
      const { data } = await notificationsList({ limit: 80 });
      setItems(Array.isArray(data?.items) ? data.items : []);
      setUnread(Number(data?.unread_count || 0));
    } catch {
      setItems([]);
      setUnread(0);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user?.id]);

  useEffect(() => {
    if (!open) return;
    reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  useEffect(() => {
    const timer = setInterval(() => {
      if (user?.id) reload();
    }, 45000);
    return () => clearInterval(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user?.id]);

  const generalItems = useMemo(() => items.filter((n) => n.channel !== "actionable"), [items]);
  const actionableItems = useMemo(() => items.filter((n) => n.channel === "actionable"), [items]);

  const markRead = async (ids = [], markAll = false) => {
    try {
      const { data } = await notificationsRead({ ids, mark_all: markAll });
      if (typeof data?.unread_count === "number") setUnread(data.unread_count);
      setItems((prev) =>
        prev.map((n) => (markAll || ids.includes(n.id) ? { ...n, read_at: new Date().toISOString() } : n))
      );
    } catch {
      // ignore
    }
  };

  const openNotification = async (n) => {
    if (!n) return;
    if (n.id && !n.read_at) await markRead([n.id]);
    const route = n?.data?.route;
    if (route && typeof route === "string") {
      setOpen(false);
      onNavigate(route);
    }
  };

  const handleAction = async (n, action) => {
    if (!n?.id) return;
    setActingId(n.id);
    try {
      if (n.type === "clan_invite") {
        const joinReqId = n?.data?.join_request_id;
        if (!joinReqId) throw new Error("missing join request id");
        await api.post(`/invites/${joinReqId}`, { action });
      } else if (n.type === "clan_challenge") {
        const challengeId = n?.data?.challenge_id;
        if (!challengeId) throw new Error("missing challenge id");
        const { data } = await api.post(`/challenges/${challengeId}`, { action });
        if (action === "accept" && data?.match?.id) {
          setOpen(false);
          onNavigate(`/matches/${data.match.id}`);
        }
      }
      await markRead([n.id]);
      await reload();
    } catch {
      // ignore
    } finally {
      setActingId("");
    }
  };

  const renderNotificationItem = (n) => {
    const msg = n?.message || n?.body || n?.title || "";
    const pending = n?.status === "pending";
    const isActionable = n?.channel === "actionable";
    return (
      <div key={n.id} className="rounded-md border b-soft bg-background/40 p-2.5 space-y-2">
        <button
          type="button"
          onClick={() => openNotification(n)}
          className="w-full text-right"
        >
          <div className="text-xs text-white/90 leading-relaxed">{msg}</div>
          <div className="mt-1 text-[10px] text-white/35">
            {n?.created_at ? new Date(n.created_at).toLocaleString("ar") : ""}
          </div>
        </button>

        {isActionable && pending && (
          <div className="flex gap-2">
            <button
              type="button"
              disabled={actingId === n.id}
              onClick={() => handleAction(n, "accept")}
              className="px-2.5 py-1.5 rounded bg-emerald-500 text-black text-xs font-bold hover:bg-emerald-400 disabled:opacity-60"
            >
              <span className="inline-flex items-center gap-1">
                <Check size={12} /> {n.type === "clan_challenge" ? "قبول التحدي" : "قبول العقد"}
              </span>
            </button>
            <button
              type="button"
              disabled={actingId === n.id}
              onClick={() => handleAction(n, "reject")}
              className="px-2.5 py-1.5 rounded border b-soft text-xs hover:bg-white/5 disabled:opacity-60"
            >
              <span className="inline-flex items-center gap-1">
                <X size={12} /> رفض
              </span>
            </button>
          </div>
        )}
      </div>
    );
  };

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <button
          type="button"
          data-testid="notifications-trigger"
          className="relative p-2 rounded-md hover:bg-white/5 text-white/60 hover:text-white"
          title="الإشعارات"
        >
          <Bell size={18} />
          {unread > 0 && (
            <span className="absolute -top-1 -left-1 min-w-[16px] h-4 px-1 rounded-full bg-destructive text-[10px] text-white grid place-items-center font-bold">
              {unread > 99 ? "99+" : unread}
            </span>
          )}
        </button>
      </PopoverTrigger>
      <PopoverContent align="start" className="w-[min(92vw,360px)] p-3">
        <div className="flex items-center justify-between mb-2">
          <div className="text-sm font-bold">الإشعارات</div>
          <button
            type="button"
            onClick={() => markRead([], true)}
            className="text-[11px] text-gold-500 hover:text-gold-400"
          >
            تعيين الكل كمقروء
          </button>
        </div>

        <Tabs value={tab} onValueChange={setTab}>
          <TabsList className="w-full grid grid-cols-2">
            <TabsTrigger value="general" className="text-xs">إشعارات عامة</TabsTrigger>
            <TabsTrigger value="actionable" className="text-xs">تنبيهات تفاعلية</TabsTrigger>
          </TabsList>

          <TabsContent value="general" className="mt-3">
            <div className="max-h-80 overflow-y-auto space-y-2">
              {loading ? (
                <div className="text-xs text-white/45 py-4 text-center">جاري التحميل...</div>
              ) : generalItems.length === 0 ? (
                <div className="text-xs text-white/45 py-4 text-center">لا توجد إشعارات عامة</div>
              ) : (
                generalItems.map(renderNotificationItem)
              )}
            </div>
          </TabsContent>

          <TabsContent value="actionable" className="mt-3">
            <div className="max-h-80 overflow-y-auto space-y-2">
              {loading ? (
                <div className="text-xs text-white/45 py-4 text-center">جاري التحميل...</div>
              ) : actionableItems.length === 0 ? (
                <div className="text-xs text-white/45 py-4 text-center">لا توجد تنبيهات تفاعلية</div>
              ) : (
                actionableItems.map(renderNotificationItem)
              )}
            </div>
          </TabsContent>
        </Tabs>
      </PopoverContent>
    </Popover>
  );
}

function SiteFooter() {
  const links = [
    {
      label: "X",
      href: "https://x.com/rivals__es?s=11",
      testid: "footer-x",
      icon: (
        <svg viewBox="0 0 24 24" className="h-4 w-4" aria-hidden="true" fill="currentColor">
          <path d="M18.901 1.153h3.68l-8.03 9.172L24 22.847h-7.406l-5.8-7.584-6.638 7.584H.474l8.59-9.815L0 1.154h7.594l5.243 6.932zM17.607 20.64h2.039L6.486 3.244H4.298z" />
        </svg>
      ),
    },
    { label: "Twitch", href: "https://www.twitch.tv/rivals_es", testid: "footer-twitch", icon: <Twitch size={16} /> },
    { label: "Instagram", href: "https://www.instagram.com/rivals_es?igsh=ZWoyc3h0am8wdnF1&utm_source=qr", testid: "footer-instagram", icon: <Instagram size={16} /> },
    { label: "TikTok", href: "https://www.tiktok.com/@rivals__es?_r=1&_t=ZS-981M5GVV4Jo", testid: "footer-tiktok", icon: <Music2 size={16} /> },
  ];
  return (
    <footer className="border-t b-soft mt-12 bg-surface/40" data-testid="site-footer">
      <div className="container py-10 grid md:grid-cols-3 gap-8">
        <div>
          <div className="font-display font-black text-xl text-gold-500">RIVALS</div>
          <p className="text-xs text-white/50 mt-2 leading-relaxed">
            دوري Call of Duty العربي. كلانات، بطولات، شات مباشر — كل شيء تحتاجه في مكان واحد.
          </p>
          <a
            href="https://eauthenticate.saudibusiness.gov.sa/certificate-details/0000309390"
            target="_blank"
            rel="noreferrer"
            aria-label="شعار توثيق التجارة الإلكترونية"
            title="توثيق التجارة الإلكترونية"
            style={{
              display: "inline-block",
              marginTop: "15px",
              transition: "all 0.3s ease",
            }}
            onMouseOver={(e) => {
              const img = e.currentTarget.querySelector("img");
              if (img) {
                img.style.opacity = "1";
              }
            }}
            onMouseOut={(e) => {
              const img = e.currentTarget.querySelector("img");
              if (img) {
                img.style.opacity = "0.8";
              }
            }}
          >
            <img
              src="/sbc-dark.png"
              alt="شعار توثيق التجارة الإلكترونية"
              className="w-[230px] sm:w-[280px] lg:w-[340px] h-auto"
              style={{
                opacity: 0.8,
                transition: "all 0.3s ease",
              }}
            />
          </a>
        </div>
        <div>
          <div className="text-[10px] uppercase tracking-widest text-white/40 mb-3">روابط مفيدة</div>
          <ul className="space-y-1.5 text-sm">
            <li><a href="/rules" className="text-white/70 hover:text-gold-500">القوانين</a></li>
            <li><a href="/leagues" className="text-white/70 hover:text-gold-500">الدوريات</a></li>
            <li><a href="/plus" className="text-white/70 hover:text-gold-500">PLUS</a></li>
            <li><a href="/blacklist" className="text-white/70 hover:text-gold-500">القائمة السوداء</a></li>
          </ul>
        </div>
        <div>
          <div className="text-[10px] uppercase tracking-widest text-white/40 mb-3">تابعنا</div>
          <div className="flex flex-wrap gap-2">
            {links.map((l) => (
              <a
                key={l.label}
                href={l.href}
                target="_blank"
                rel="noreferrer"
                data-testid={l.testid}
                aria-label={l.label}
                title={l.label}
                className="h-9 w-9 rounded-md border b-soft hover:border-gold-500/40 text-white/70 hover:text-gold-500 inline-flex items-center justify-center"
              >
                {l.icon}
              </a>
            ))}
          </div>
          <a href="mailto:1rivalsgg@gmail.com" className="block text-[11px] text-white/40 mt-3 hover:text-gold-500">
            1rivalsgg@gmail.com
          </a>
        </div>
      </div>
      <div className="border-t b-soft py-4 text-center text-[10px] text-white/30 uppercase tracking-widest">
        © {new Date().getFullYear()} RIVALS جميع الحقوق محفوظة
      </div>
    </footer>
  );
}