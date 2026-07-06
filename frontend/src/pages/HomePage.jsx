import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import api from "../api";
import { Trophy, Swords, Users, Shield, Flame } from "lucide-react";
import HeroCarousel from "../components/HeroCarousel";

function StatCard({ icon: Icon, label, value, testid, accent = "default" }) {
  const styles = {
    live: {
      card: "bg-gradient-to-br from-royalGold-700/10 via-royalGold-600/8 to-transparent border border-royalGold-500/18",
      icon: "h-11 w-11 rounded-xl bg-gradient-to-br from-royalGold-500/22 via-royalGold-400/16 to-white/10 text-royalGold-300 border border-royalGold-400/30 shadow-[0_0_12px_rgba(203,213,225,0.22)] grid place-items-center",
    },
    clans: {
      card: "bg-gradient-to-br from-royalGold-700/10 via-royalGold-600/8 to-transparent border border-royalGold-500/18",
      icon: "h-11 w-11 rounded-xl bg-gradient-to-br from-royalGold-500/22 via-royalGold-400/16 to-white/10 text-royalGold-300 border border-royalGold-400/30 shadow-[0_0_12px_rgba(203,213,225,0.22)] grid place-items-center",
    },
    players: {
      card: "bg-gradient-to-br from-royalGold-700/10 via-royalGold-600/7 to-transparent border border-royalGold-500/16",
      icon: "h-11 w-11 rounded-xl bg-gradient-to-br from-royalGold-500/20 via-royalGold-400/14 to-white/10 text-royalGold-300 border border-royalGold-400/28 shadow-[0_0_10px_rgba(203,213,225,0.18)] grid place-items-center",
    },
    season: {
      card: "bg-gradient-to-br from-royalGold-700/10 via-royalGold-600/8 to-transparent border border-royalGold-500/18",
      icon: "h-11 w-11 rounded-xl bg-gradient-to-br from-royalGold-500/24 via-royalGold-400/18 to-white/12 text-royalGold-200 border border-royalGold-300/35 shadow-[0_0_12px_rgba(203,213,225,0.22)] grid place-items-center",
    },
    default: {
      card: "bg-gradient-to-br from-royalGold-700/10 via-royalGold-600/8 to-transparent border border-royalGold-500/18",
      icon: "h-11 w-11 rounded-xl bg-gradient-to-br from-royalGold-500/24 via-royalGold-400/18 to-white/10 text-royalGold-200 border border-royalGold-300/35 shadow-[0_0_12px_rgba(203,213,225,0.22)] grid place-items-center",
    },
  };

  const cardClass = styles[accent]?.card || styles.default.card;
  const iconBoxClass = styles[accent]?.icon || styles.default.icon;

  return (
    <div data-testid={testid} className={`rounded-lg p-5 flex items-center gap-4 ${cardClass}`}>
      <div className={iconBoxClass}>
        <Icon size={20} />
      </div>
      <div>
        <div className="text-xs uppercase tracking-widest text-white/60">{label}</div>
        <div className="text-2xl font-display font-black text-white">{value}</div>
      </div>
    </div>
  );
}

function MatchCard({ m }) {
  return (
    <Link
      to={`/matches/${m.id}`}
      data-testid={`match-card-${m.id}`}
      className="block bg-surface border b-soft rounded-lg p-5 hover:border-gold-500/30 transition group fade-in"
    >
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <span className="live-dot" />
          <span className="text-xs uppercase tracking-widest text-destructive font-bold">مباشر</span>
        </div>
        <span className="text-xs text-white/40">{m.game}</span>
      </div>
      <div className="grid grid-cols-[1fr_auto_1fr] items-center gap-4">
        <div className="text-right">
          <div className="font-display font-black text-lg truncate">{m.clan_a?.tag}</div>
          <div className="text-xs text-white/50 truncate">{m.clan_a?.name}</div>
        </div>
        <div className="font-display font-black text-2xl text-gold-500">VS</div>
        <div className="text-left">
          <div className="font-display font-black text-lg truncate">{m.clan_b?.tag}</div>
          <div className="text-xs text-white/50 truncate">{m.clan_b?.name}</div>
        </div>
      </div>
      <div className="mt-4 text-center text-xs text-white/40 group-hover:text-gold-500 transition">
        ادخل الشات والتفاصيل ←
      </div>
    </Link>
  );
}

export default function HomePage() {
  const [live, setLive] = useState([]);
  const [topClans, setTopClans] = useState([]);
  const [counts, setCounts] = useState({ live: 0, clans: 0, players: 0 });

  useEffect(() => {
    (async () => {
      const [l, c, p] = await Promise.all([
        api.get("/matches/live"),
        api.get("/leaderboard/clans"),
        api.get("/leaderboard/players"),
      ]);
      setLive(l.data);
      setTopClans(c.data.slice(0, 5));
      setCounts({ live: l.data.length, clans: c.data.length, players: p.data.length });
    })().catch(() => {});
  }, []);

  return (
    <div className="space-y-10">
      <HeroCarousel />

      {/* Stats */}
      <section className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard icon={Flame} label="مباريات مباشرة" value={counts.live} testid="stat-live" accent="live" />
        <StatCard icon={Shield} label="كلانات نشطة" value={counts.clans} testid="stat-clans" accent="clans" />
        <StatCard icon={Users} label="إجمالي اللاعبين" value={counts.players} testid="stat-players" accent="players" />
        <StatCard icon={Trophy} label="الموسم" value="٢٠٢٦" testid="stat-season" accent="season" />
      </section>

      {/* Live matches + top clans */}
      <section className="grid lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="font-display font-black text-2xl flex items-center gap-2">
              <Swords size={22} className="text-gold-500" /> المباريات الآن
            </h2>
            <Link to="/matches" className="text-xs text-white/50 hover:text-gold-500">عرض الكل ←</Link>
          </div>
          {live.length === 0 ? (
            <div className="bg-surface border b-soft rounded-lg p-10 text-center text-white/40">
              لا توجد مباريات مباشرة الآن. تابع لاحقاً!
            </div>
          ) : (
            <div className="grid sm:grid-cols-2 gap-4">
              {live.slice(0, 4).map((m) => (
                <MatchCard key={m.id} m={m} />
              ))}
            </div>
          )}
        </div>

        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="font-display font-black text-2xl flex items-center gap-2">
              <Trophy size={22} className="text-gold-500" /> أفضل الكلانات
            </h2>
          </div>
          <div className="bg-surface border b-soft rounded-lg divide-y divide-white/5">
            {topClans.length === 0 && (
              <div className="p-6 text-center text-white/40 text-sm">لا توجد بيانات بعد</div>
            )}
            {topClans.map((c, idx) => (
              <Link
                key={c.id}
                to={`/clans/${c.id}`}
                data-testid={`top-clan-${idx}`}
                className="flex items-center gap-3 p-4 hover:bg-white/5 transition"
              >
                <div
                  className={`h-8 w-8 grid place-items-center rounded-md font-display font-black text-sm ${
                    idx === 0
                      ? "bg-gradient-to-b from-royalGold-200 via-royalGold-400 to-royalGold-700 text-white shadow-[0_0_12px_rgba(203,213,225,0.3)]"
                      : idx === 1
                      ? "bg-gradient-to-b from-gray-100 via-gray-300 to-gray-500 text-black shadow-[0_0_12px_rgba(229,231,235,0.3)]"
                      : idx === 2
                      ? "bg-gradient-to-b from-slate-200 via-slate-400 to-slate-600 text-white shadow-[0_0_12px_rgba(148,163,184,0.32)]"
                      : "bg-white/5 text-white/50"
                  }`}
                >
                  {idx + 1}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="font-bold truncate">{c.name}</div>
                  <div className="text-xs text-white/40">[{c.tag}]</div>
                </div>
                <div className="text-gold-500 font-display font-black">{c.points}</div>
              </Link>
            ))}
          </div>
        </div>
      </section>
    </div>
  );
}
