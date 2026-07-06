import { Link, NavLink, useNavigate } from "react-router-dom";
import { useAuth } from "../AuthContext";
import { Users, Swords, LogOut, Shield, Home as HomeIcon, ScrollText, Crown, Sparkles, Award, ShieldOff, Trophy } from "lucide-react";

export default function Layout({ children }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const isPlusMember = !!(user?.is_plus || user?.is_personal_plus || user?.plan === "plus");

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
                  <div className="text-[10px] uppercase tracking-widest text-white/40">
                    {user.role === "owner" ? "مالك" : user.role === "admin" ? "منظم" : isPlusMember ? "Plus" : "لاعب"}
                  </div>
                </div>
              </Link>
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

        <nav className="md:hidden flex items-center gap-1 px-2 pb-2 overflow-x-auto">
          {nav.map((n) => (
            <NavLink
              key={n.to}
              to={n.to}
              end={n.to === "/"}
              className={({ isActive }) =>
                `px-3 py-1.5 rounded-md text-xs whitespace-nowrap flex items-center gap-1 ${n.to === "/rules" ? "whitespace-nowrap" : ""} ${
                  isActive ? "bg-white/5 text-royalGold-500" : "text-white/60"
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

function SiteFooter() {
  const links = [
    { label: "Discord", href: "https://discord.gg/GmtAMu85W", testid: "footer-discord" },
    { label: "Instagram", href: "https://instagram.com/rivals.gg", testid: "footer-instagram" },
    { label: "TikTok", href: "https://tiktok.com/@.rivalsgg", testid: "footer-tiktok" },
    { label: "Support", href: "mailto:support@rivals.gg", testid: "footer-support" },
  ];
  return (
    <footer className="border-t b-soft mt-12 bg-surface/40" data-testid="site-footer">
      <div className="container py-10 grid md:grid-cols-3 gap-8">
        <div>
          <div className="font-display font-black text-xl text-gold-500">RIVALS</div>
          <p className="text-xs text-white/50 mt-2 leading-relaxed">
            دوري Call of Duty العربي. كلانات، بطولات، شات مباشر — كل شيء تحتاجه في مكان واحد.
          </p>
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
                className="px-3 py-1.5 rounded-md border b-soft hover:border-gold-500/40 text-xs text-white/70 hover:text-gold-500"
              >
                {l.label}
              </a>
            ))}
          </div>
          <a href="mailto:support@rivals.gg" className="block text-[11px] text-white/40 mt-3 hover:text-gold-500">
            support@rivals.gg
          </a>
        </div>
      </div>
      <div className="border-t b-soft py-4 text-center text-[10px] text-white/30 uppercase tracking-widest">
        © {new Date().getFullYear()} RIVALS جميع الحقوق محفوظة
      </div>
    </footer>
  );
}