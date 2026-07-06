import { useEffect, useState } from "react";
import api from "../../api";
import { Swords } from "lucide-react";

export default function H2HWidget({ matchId }) {
  const [data, setData] = useState(null);

  useEffect(() => {
    api.get(`/matches/${matchId}/h2h`).then((r) => setData(r.data)).catch(() => setData(null));
  }, [matchId]);

  if (!data) return null;
  const { clan_a, clan_b, a_wins, b_wins, total } = data;
  const max = Math.max(a_wins + b_wins, 1);
  const aPct = (a_wins / max) * 100;
  const bPct = (b_wins / max) * 100;

  return (
    <div data-testid="h2h-widget" className="bg-surface border b-soft rounded-xl p-5">
      <div className="flex items-center gap-2 mb-3">
        <Swords size={16} className="text-destructive" />
        <h3 className="font-display font-bold text-sm uppercase tracking-widest">المواجهات السابقة</h3>
        <span className="text-xs text-white/40 mr-auto">{total} مباراة</span>
      </div>
      {total === 0 ? (
        <div className="text-center text-white/40 text-sm py-4" data-testid="h2h-empty">أول مواجهة بين الكلانين!</div>
      ) : (
        <>
          <div className="flex items-baseline justify-between gap-3 mb-2">
            <div className="text-right">
              <div className="text-xs text-white/50">{clan_a?.name} <span className="text-gold-500">[{clan_a?.tag}]</span></div>
              <div className="font-display font-black text-3xl text-emerald-400" data-testid="h2h-a-wins">{a_wins}</div>
            </div>
            <div className="text-white/30 text-xs">VS</div>
            <div className="text-left">
              <div className="text-xs text-white/50"><span className="text-gold-500">[{clan_b?.tag}]</span> {clan_b?.name}</div>
              <div className="font-display font-black text-3xl text-destructive" data-testid="h2h-b-wins">{b_wins}</div>
            </div>
          </div>
          <div className="h-2 rounded-full bg-white/5 overflow-hidden flex">
            <div className="h-full bg-emerald-500/70" style={{ width: `${aPct}%`, transition: "width 600ms" }} />
            <div className="h-full bg-destructive/70 mr-auto" style={{ width: `${bPct}%`, transition: "width 600ms" }} />
          </div>
        </>
      )}
    </div>
  );
}
