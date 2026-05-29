import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import api from "../api";
import { Trophy, Gamepad2, ScrollText, Crown, Sparkles } from "lucide-react";

function LeagueStandings({ league }) {
  const [rows, setRows] = useState(null);

  useEffect(() => {
    api
      .get(`/leagues/${league.id}/leaderboard`)
      .then((r) => setRows(r.data.standings || []))
      .catch(() => setRows([]));
  }, [league.id]);

  if (rows === null) {
    return <div className="text-white/40 text-sm py-3">جاري التحميل...</div>;
  }
  if (rows.length === 0) {
    return (
      <div className="text-white/40 text-sm py-3" data-testid={`league-empty-${league.id}`}>
        لا توجد كلانات منضمّة بعد. كن أول من ينضم!
      </div>
    );
  }

  return (
    <div className="overflow-hidden rounded-md border b-soft">
      <table className="w-full text-right text-sm" data-testid={`league-standings-${league.id}`}>
        <thead className="bg-white/5 text-[10px] uppercase tracking-widest text-white/50">
          <tr>
            <th className="py-2 px-3 w-12">#</th>
            <th className="py-2 px-3">الكلان</th>
            <th className="py-2 px-3 w-24 text-center">فوز/خسارة</th>
            <th className="py-2 px-3 w-20 text-end">النقاط</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r, idx) => (
            <tr
              key={r.clan_id}
              className={`border-t b-soft hover:bg-white/5 transition ${
                idx === 0 ? "bg-gold-500/5" : ""
              }`}
              data-testid={`league-row-${league.id}-${r.clan_id}`}
            >
              <td className="py-2 px-3">
                {idx === 0 ? (
                  <Crown size={14} className="text-gold-500 inline-block" />
                ) : (
                  <span className="text-white/40">{idx + 1}</span>
                )}
              </td>
              <td className="py-2 px-3">
                <Link
                  to={`/clans/${r.clan_id}`}
                  className="hover:text-gold-500 inline-flex items-center gap-2"
                >
                  <span className="text-[10px] text-gold-500">[{r.clan_tag}]</span>
                  <span className="font-semibold">{r.clan_name}</span>
                  {r.is_plus && <Sparkles size={11} className="text-gold-500" />}
                </Link>
              </td>
              <td className="py-2 px-3 text-center text-xs">
                <span className="text-emerald-400">{r.wins}</span>
                <span className="text-white/30 mx-1">/</span>
                <span className="text-rose-400">{r.losses}</span>
              </td>
              <td className="py-2 px-3 text-end font-bold text-gold-500">{r.points}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function LeagueCard({ league }) {
  const [showRules, setShowRules] = useState(false);
  return (
    <div
      className="bg-surface border b-soft rounded-xl overflow-hidden"
      data-testid={`league-card-${league.id}`}
    >
      {league.rules_image ? (
        <img
          src={league.rules_image}
          alt={league.name}
          className="w-full h-40 object-cover border-b b-soft"
          data-testid={`league-image-${league.id}`}
        />
      ) : (
        <div className="h-32 bg-gradient-to-br from-gold-500/10 via-transparent to-white/5 border-b b-soft grid place-items-center">
          <Trophy size={48} className="text-gold-500/40" />
        </div>
      )}
      <div className="p-5 space-y-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <h2 className="font-display font-black text-xl">{league.name}</h2>
            {league.status === "active" && (
              <span className="text-[10px] uppercase tracking-widest text-emerald-400 border border-emerald-500/30 rounded px-2 py-0.5">
                نشط
              </span>
            )}
          </div>
          <div className="flex items-center gap-2 text-xs text-white/50">
            <Gamepad2 size={13} /> {league.game || "Call of Duty"}
          </div>
          {league.description && (
            <p className="text-sm text-white/60 mt-2 leading-relaxed">
              {league.description}
            </p>
          )}
        </div>

        {league.rules && (
          <button
            onClick={() => setShowRules((v) => !v)}
            data-testid={`league-toggle-rules-${league.id}`}
            className="text-xs text-gold-500 hover:text-gold-400 inline-flex items-center gap-1"
          >
            <ScrollText size={12} />
            {showRules ? "إخفاء القوانين" : "عرض قوانين الدوري"}
          </button>
        )}
        {showRules && league.rules && (
          <div
            data-testid={`league-rules-${league.id}`}
            className="text-sm text-white/70 leading-relaxed whitespace-pre-wrap border-r-2 border-gold-500/30 pr-3"
          >
            {league.rules}
          </div>
        )}

        <div>
          <div className="text-[10px] uppercase tracking-widest text-white/40 mb-2">
            ترتيب الدوري
          </div>
          <LeagueStandings league={league} />
        </div>
      </div>
    </div>
  );
}

export default function LeaguesPage() {
  const [leagues, setLeagues] = useState(null);

  useEffect(() => {
    api
      .get("/leagues/active")
      .then((r) => setLeagues(r.data || []))
      .catch(() => setLeagues([]));
  }, []);

  return (
    <div className="space-y-8">
      <div>
        <h1 className="font-display font-black text-3xl md:text-4xl flex items-center gap-3">
          <Trophy className="text-gold-500" /> الدوريات النشطة
        </h1>
        <p className="text-white/50 mt-1">
          كل دوري له ترتيبه المستقل — انضم وتسلّق القمة. الفوز +3 • الخسارة -1 • الانسحاب -3
        </p>
      </div>

      {leagues === null && (
        <div className="text-white/40">جاري التحميل...</div>
      )}
      {leagues && leagues.length === 0 && (
        <div
          data-testid="leagues-empty-state"
          className="bg-surface border b-soft rounded-xl p-10 text-center text-white/50"
        >
          لا توجد دوريات نشطة حالياً. ترقّب الإعلان قريباً!
        </div>
      )}
      {leagues && leagues.length > 0 && (
        <div className="grid md:grid-cols-2 gap-6" data-testid="leagues-grid">
          {leagues.map((lg) => (
            <LeagueCard key={lg.id} league={lg} />
          ))}
        </div>
      )}
    </div>
  );
}
