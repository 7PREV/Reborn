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

      <div className="flex justify-end">
        <div className="w-full sm:w-auto">
          <div className="inline-flex items-center bg-gradient-to-l from-surface/95 via-surface to-background/90 border border-royalGold-500/20 rounded-2xl p-1.5 shadow-[0_6px_30px_rgba(0,0,0,0.35)] backdrop-blur-sm">
            <button
              data-testid="tab-live-matches"
              onClick={() => setTab("live")}
              className={`px-5 py-2.5 rounded-xl text-sm inline-flex items-center gap-2 transition-all duration-200 border ${
                tab === "live"
                  ? "bg-gradient-to-l from-royalGold-700 via-royalGold-600 to-royalGold-500 text-white font-extrabold border-royalGold-300/40 shadow-[0_0_15px_rgba(203,213,225,0.22)]"
                  : "text-gray-400 border-transparent hover:text-white hover:bg-white/5"
              }`}
            >
              مباشر ({live.length})
            </button>
            <button
              data-testid="tab-history"
              onClick={() => setTab("history")}
              className={`px-5 py-2.5 rounded-xl text-sm inline-flex items-center gap-2 transition-all duration-200 border ${
                tab === "history"
                  ? "bg-gradient-to-l from-royalGold-700 via-royalGold-600 to-royalGold-500 text-white font-extrabold border-royalGold-300/40 shadow-[0_0_15px_rgba(203,213,225,0.22)]"
                  : "text-gray-400 border-transparent hover:text-white hover:bg-white/5"
              }`}
            >
              سجل ٢٤ ساعة ({history.length})
            </button>
          </div>
          <div className="mt-2 h-px w-full bg-gradient-to-l from-transparent via-royalGold-500/50 to-transparent" />
        </div>
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
                    <span className="text-xs uppercase tracking-widest text-destructive font-bold px-2 py-0.5 rounded-full border border-royalGold-500/30 shadow-[0_0_10px_rgba(203,213,225,0.18)] bg-royalGold-500/10">مباشر</span>
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
