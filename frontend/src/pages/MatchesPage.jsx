import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import api from "../api";

export default function MatchesPage() {
  const [live, setLive] = useState([]);
  const [history, setHistory] = useState([]);
  const [tab, setTab] = useState("live");

  useEffect(() => {
    api.get("/matches/live").then((r) => setLive(r.data));
    api.get("/matches/history").then((r) => setHistory(r.data));
  }, []);

  const data = tab === "live" ? live : history;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-display font-black text-3xl md:text-4xl">المباريات</h1>
        <p className="text-white/50 mt-1">تابع المباريات المباشرة وتاريخ آخر ٢٤ ساعة</p>
      </div>

      <div className="inline-flex bg-surface border b-soft rounded-md p-1">
        <button data-testid="tab-live-matches" onClick={() => setTab("live")} className={`px-5 py-2 rounded text-sm ${tab === "live" ? "bg-gold-500 text-black font-bold" : "text-white/60"}`}>
          مباشر ({live.length})
        </button>
        <button data-testid="tab-history" onClick={() => setTab("history")} className={`px-5 py-2 rounded text-sm ${tab === "history" ? "bg-gold-500 text-black font-bold" : "text-white/60"}`}>
          سجل ٢٤ ساعة ({history.length})
        </button>
      </div>

      {data.length === 0 ? (
        <div className="bg-surface border b-soft rounded-lg p-12 text-center text-white/40">
          {tab === "live" ? "لا توجد مباريات مباشرة" : "لا توجد مباريات في آخر ٢٤ ساعة"}
        </div>
      ) : (
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {data.map((m) => (
            <Link
              key={m.id}
              to={`/matches/${m.id}`}
              data-testid={`match-${m.id}`}
              className="bg-surface border b-soft rounded-lg p-5 hover:border-gold-500/30 transition fade-in"
            >
              <div className="flex items-center justify-between mb-4">
                {m.status === "live" ? (
                  <div className="flex items-center gap-2">
                    <span className="live-dot" />
                    <span className="text-xs uppercase tracking-widest text-destructive font-bold">مباشر</span>
                  </div>
                ) : (
                  <span className="text-xs uppercase tracking-widest text-white/40">منتهية</span>
                )}
                <span className="text-xs text-white/40">{m.game}</span>
              </div>
              <div className="grid grid-cols-[1fr_auto_1fr] items-center gap-2">
                <div className="text-right">
                  <div className={`font-display font-black text-lg truncate ${m.winner_clan_id === m.clan_a_id ? "text-gold-500" : ""}`}>{m.clan_a?.tag}</div>
                  <div className="text-xs text-white/50 truncate">{m.clan_a?.name}</div>
                </div>
                <div className="text-center">
                  {m.status === "finished" ? (
                    <div className="font-display font-black text-xl">
                      {m.score_a} <span className="text-white/30">-</span> {m.score_b}
                    </div>
                  ) : (
                    <div className="font-display font-black text-xl text-gold-500">VS</div>
                  )}
                </div>
                <div className="text-left">
                  <div className={`font-display font-black text-lg truncate ${m.winner_clan_id === m.clan_b_id ? "text-gold-500" : ""}`}>{m.clan_b?.tag}</div>
                  <div className="text-xs text-white/50 truncate">{m.clan_b?.name}</div>
                </div>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
