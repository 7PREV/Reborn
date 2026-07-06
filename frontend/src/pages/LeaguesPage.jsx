import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import api from "../api";
import { ArrowLeft, Gamepad2, ScrollText, Trophy } from "lucide-react";

function LeagueCard({ league }) {
  return (
    <Link
      to={`/leagues/${league.id}`}
      className="group block bg-surface border b-soft rounded-xl overflow-hidden hover:border-gold-500/35 transition animate-float-up"
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
            <h2 className="font-display font-black text-xl group-hover:text-gold-500 transition-colors">{league.name}</h2>
            {league.status === "active" && (
              <span className="text-[10px] uppercase tracking-widest text-emerald-400 border border-emerald-500/30 rounded px-2 py-0.5 animate-pulse-glow">
                نشط
              </span>
            )}
          </div>
          <div className="flex items-center gap-2 text-xs text-white/50">
            <Gamepad2 size={13} /> {league.game || "Call of Duty"}
          </div>
          {league.description && (
            <p className="text-sm text-white/60 mt-2 leading-relaxed line-clamp-2">
              {league.description}
            </p>
          )}
        </div>

        <div className="flex items-center justify-between text-xs text-white/45">
          <span className="inline-flex items-center gap-1">
            <ScrollText size={12} /> القوانين والصور: {league.rules_image ? 1 : 0}
          </span>
          <span className="inline-flex items-center gap-1 text-gold-500 group-hover:text-gold-400">
            عرض التفاصيل <ArrowLeft size={12} />
          </span>
        </div>
      </div>
    </Link>
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
