import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import api from "../api";
import { Trophy, Swords, Users, Shield, Flame } from "lucide-react";

function StatCard({ icon: Icon, label, value, testid }) {
  return (
    <div data-testid={testid} className="bg-surface border b-soft rounded-lg p-5 flex items-center gap-4">
      <div className="h-10 w-10 rounded-md bg-gold-500/10 text-gold-500 grid place-items-center">
        <Icon size={20} />
      </div>
      <div>
        <div className="text-xs uppercase tracking-widest text-white/40">{label}</div>
        <div className="text-2xl font-display font-black">{value}</div>
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
      {/* Hero */}
      <section className="relative overflow-hidden rounded-xl border b-soft grain">
        <img
          src="https://images.unsplash.com/photo-1566304211221-a25fe7aacbe2?w=1600&q=80"
          alt=""
          className="absolute inset-0 w-full h-full object-cover opacity-30"
        />
        <div className="absolute inset-0 bg-gradient-to-l from-[#0a0a0b] via-[#0a0a0bcc] to-[#0a0a0b88]" />
        <div className="relative p-8 md:p-14">
          <div className="text-xs uppercase tracking-[0.3em] text-gold-500 mb-3">
            بطولات • كلانات • مجد
          </div>
          <h1 className="font-display font-black text-4xl md:text-5xl lg:text-6xl leading-[1.05] max-w-3xl">
            حلبة <span className="gold-text">الأبطال</span>
            <br />
            تبدأ من هنا.
          </h1>
          <p className="mt-5 text-white/60 max-w-xl">
            تابع المباريات الحية، شارك في التحديات، وكوّن كلانك الخاص. كل دقيقة بطولة.
          </p>
          <div className="mt-7 flex gap-3 flex-wrap">
            <Link
              to="/clans"
              data-testid="cta-clans"
              className="px-5 py-3 rounded-md bg-gold-500 text-black font-bold hover:bg-gold-400 transition"
            >
              استكشف الكلانات
            </Link>
            <Link
              to="/matches"
              data-testid="cta-matches"
              className="px-5 py-3 rounded-md border b-soft hover:bg-white/5 transition"
            >
              المباريات الحية
            </Link>
          </div>
        </div>
      </section>

      {/* Stats */}
      <section className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard icon={Flame} label="مباريات مباشرة" value={counts.live} testid="stat-live" />
        <StatCard icon={Shield} label="كلانات نشطة" value={counts.clans} testid="stat-clans" />
        <StatCard icon={Users} label="إجمالي اللاعبين" value={counts.players} testid="stat-players" />
        <StatCard icon={Trophy} label="الموسم" value="٢٠٢٦" testid="stat-season" />
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
                      ? "bg-gold-500 text-black"
                      : idx === 1
                      ? "bg-slate-300 text-black"
                      : idx === 2
                      ? "bg-amber-700 text-white"
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
