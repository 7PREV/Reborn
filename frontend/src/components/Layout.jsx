import { Link, NavLink, useNavigate } from "react-router-dom";
import { useAuth } from "../AuthContext";
import { Trophy, Users, Swords, LogOut, Shield, Home as HomeIcon, ScrollText, Crown, Sparkles, Award, ShieldOff } from "lucide-react";

export default function Layout({ children }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const nav = [
    { to: "/", label: "الرئيسية", icon: HomeIcon, id: "nav-home" },
    { to: "/tournaments", label: "البطولات", icon: Award, id: "nav-tournaments" },
    { to: "/matches", label: "المباريات", icon: Swords, id: "nav-matches" },
    { to: "/clans", label: "الكلانات", icon: Shield, id: "nav-clans" },
    { to: "/players", label: "اللاعبون", icon: Users, id: "nav-players" },
    { to: "/leaderboard", label: "النتائج", icon: Trophy, id: "nav-leaderboard" },
    { to: "/rules", label: "القوانين", icon: ScrollText, id: "nav-rules" },
  ];

  return (
    <div className="min-h-screen bg-background text-foreground" dir="rtl">
      <header className="sticky top-0 z-40 border-b b-soft bg-[#0a0a0bcc] backdrop-blur-xl">
        <div className="container flex items-center gap-6 h-16">
          <Link to="/" className="flex items-center gap-2" data-testid="logo-link">
            <div className="h-9 w-9 rounded-md bg-gold-500 text-black grid place-items-center font-black font-display">
              R
            </div>
            <div className="flex flex-col leading-none">
              <span className="font-display font-black text-xl tracking-tight">
                RIVALS<span className="text-gold-500">.</span>
              </span>
              <span className="text-[9px] uppercase tracking-[0.25em] text-white/40 mt-0.5">COD League</span>
            </div>
          </Link>

          <nav className="hidden md:flex items-center gap-1">
            {nav.map((n) => (
              <NavLink
                key={n.to}
                to={n.to}
                end={n.to === "/"}
                data-testid={n.id}
                className={({ isActive }) =>
                  `px-3 py-2 rounded-md text-sm transition-colors flex items-center gap-2 ${
                    isActive
                      ? "bg-white/5 text-gold-500"
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

          {user && (user.role === "admin" || user.role === "owner") && (
            <NavLink
              to="/blacklist"
              data-testid="nav-blacklist"
              className="hidden md:inline-flex items-center gap-1.5 text-xs uppercase tracking-widest text-destructive hover:text-destructive/80 border border-destructive/30 rounded-md px-3 py-1.5"
            >
              <ShieldOff size={14} /> القائمة السوداء
            </NavLink>
          )}

          {user && (user.role === "admin" || user.role === "owner") && (
            <NavLink
              to="/admin"
              data-testid="nav-admin"
              className="hidden md:inline-flex items-center gap-1.5 text-xs uppercase tracking-widest text-gold-500 hover:text-gold-400 border border-gold-500/30 rounded-md px-3 py-1.5"
            >
              <Crown size={14} /> {user.role === "owner" ? "لوحة المالك" : "لوحة الإدارة"}
            </NavLink>
          )}

          {user ? (
            <div className="flex items-center gap-3">
              <Link to="/me" data-testid="profile-link" className="flex items-center gap-2 group">
                <div className="relative h-9 w-9 rounded-md bg-surface border b-soft grid place-items-center font-display text-gold-500">
                  {user.username?.[0]?.toUpperCase() || "U"}
                  {user.is_plus && (
                    <Sparkles size={10} className="absolute -top-1 -right-1 text-gold-500" />
                  )}
                </div>
                <div className="hidden sm:block text-right leading-tight">
                  <div className="text-sm font-semibold flex items-center gap-1">
                    {user.username}
                    {user.is_plus && <Sparkles size={10} className="text-gold-500" />}
                  </div>
                  <div className="text-[10px] uppercase tracking-widest text-white/40">
                    {user.role === "owner" ? "مالك" : user.role === "admin" ? "منظم" : user.is_plus ? "Plus" : "لاعب"}
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
        </div>

        <nav className="md:hidden flex items-center gap-1 px-2 pb-2 overflow-x-auto">
          {nav.map((n) => (
            <NavLink
              key={n.to}
              to={n.to}
              end={n.to === "/"}
              className={({ isActive }) =>
                `px-3 py-1.5 rounded-md text-xs whitespace-nowrap flex items-center gap-1 ${
                  isActive ? "bg-white/5 text-gold-500" : "text-white/60"
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
                  isActive ? "bg-white/5 text-gold-500" : "text-gold-500/70"
                }`
              }
            >
              <Crown size={14} /> {user.role === "owner" ? "المالك" : "الإدارة"}
            </NavLink>
          ) : null}
        </nav>
      </header>

      <main className="container py-8">{children}</main>

      <footer className="border-t b-soft py-8 mt-12">
        <div className="container text-center text-xs text-white/40 uppercase tracking-widest">
          RIVALS — دوري Call of Duty
        </div>
      </footer>
    </div>
  );
}
