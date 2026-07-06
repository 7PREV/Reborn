import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import api from "../api";
import { Trophy, Crown } from "lucide-react";
import ClanLogo from "../components/clan/ClanLogo";

export default function LeaderboardPage() {
  const [clans, setClans] = useState([]);
  const [players, setPlayers] = useState([]);
  const [tab, setTab] = useState("clans");

  useEffect(() => {
    api.get("/leaderboard/clans").then((r) => setClans(r.data));
    api.get("/leaderboard/players").then((r) => setPlayers(r.data));
  }, []);

  const data = tab === "clans" ? clans : players;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-display font-black text-3xl md:text-4xl flex items-center gap-3">
          <Trophy className="text-gold-500" /> لوحة النتائج
        </h1>
        <p className="text-white/50 mt-1">الترتيب الكامل</p>
      </div>

      <div className="flex justify-end">
        <div className="w-full sm:w-auto">
          <div className="inline-flex items-center bg-gradient-to-l from-surface/95 via-surface to-background/90 border border-royalGold-500/20 rounded-2xl p-1.5 shadow-[0_6px_30px_rgba(0,0,0,0.35)] backdrop-blur-sm">
            <button
              data-testid="tab-lb-clans"
              onClick={() => setTab("clans")}
              className={`px-5 py-2.5 rounded-xl text-sm inline-flex items-center gap-2 transition-all duration-200 border ${
                tab === "clans"
                  ? "bg-gradient-to-l from-royalGold-700 via-royalGold-600 to-royalGold-500 text-white font-extrabold border-royalGold-300/40 shadow-[0_0_15px_rgba(203,213,225,0.22)]"
                  : "text-gray-400 border-transparent hover:text-white hover:bg-white/5"
              }`}
            >
              الكلانات
            </button>
            <button
              data-testid="tab-lb-players"
              onClick={() => setTab("players")}
              className={`px-5 py-2.5 rounded-xl text-sm inline-flex items-center gap-2 transition-all duration-200 border ${
                tab === "players"
                  ? "bg-gradient-to-l from-royalGold-700 via-royalGold-600 to-royalGold-500 text-white font-extrabold border-royalGold-300/40 shadow-[0_0_15px_rgba(203,213,225,0.22)]"
                  : "text-gray-400 border-transparent hover:text-white hover:bg-white/5"
              }`}
            >
              اللاعبون
            </button>
          </div>
          <div className="mt-2 h-px w-full bg-gradient-to-l from-transparent via-royalGold-500/50 to-transparent" />
        </div>
      </div>

      <div className="bg-gradient-to-b from-surface via-surface to-background/90 border border-royalGold-500/30 rounded-xl overflow-hidden shadow-[0_0_24px_rgba(212,175,55,0.22)]">
        <table className="w-full text-right">
          <thead className="bg-white/5 text-xs uppercase tracking-widest text-white/50">
            <tr>
              <th className="py-3 px-4 w-16">#</th>
              <th className="py-3 px-4">{tab === "clans" ? "الكلان" : "اللاعب"}</th>
              <th className="py-3 px-4">فوز / خسارة</th>
              <th className="py-3 px-4 w-20 text-center">W/L</th>
              <th className="py-3 px-4 text-end w-32">النقاط</th>
            </tr>
          </thead>
          <tbody>
            {data.map((row, idx) => {
              const wins = row.wins || 0;
              const losses = row.losses || 0;
              const kd = row.kd != null ? row.kd : (losses === 0 ? wins.toFixed(2) : (wins / losses).toFixed(2));
              const isPlus = tab === "clans" ? (row.is_clan_plus || row.is_plus) : row.is_personal_plus;
              return (
                <tr key={row.id} data-testid={`lb-row-${idx}`} className="border-t border-royalGold-500/15 hover:bg-royalGold-500/[0.04] transition">
                  <td className="py-3 px-4">
                    <div className={`inline-grid place-items-center h-8 w-8 rounded-md font-display font-black ${
                      idx === 0 ? "bg-gradient-to-b from-royalGold-100 via-royalGold-300 to-royalGold-700 text-white border border-royalGold-200/70 shadow-[0_0_18px_rgba(212,175,55,0.52)]" :
                      idx === 1 ? "bg-gradient-to-b from-gray-100 via-gray-300 to-gray-500 text-black border border-royalGold-200/35 shadow-[0_0_10px_rgba(212,175,55,0.2)]" :
                      idx === 2 ? "bg-gradient-to-b from-slate-200 via-slate-400 to-slate-600 text-white border border-royalGold-200/30 shadow-[0_0_10px_rgba(212,175,55,0.18)]" :
                      "bg-royalGold-500/10 border border-royalGold-500/25 text-royalGold-200"
                    }`}>{idx + 1}</div>
                  </td>
                  <td className="py-3 px-4">
                    {tab === "clans" ? (
                      <Link to={`/clans/${row.id}`} className={`inline-flex items-center gap-2 hover:text-royalGold-300 ${isPlus ? "plus-glow rounded-md px-2 py-1" : ""}`}>
                        <ClanLogo
                          clan={row}
                          className="h-[18px] w-[18px] rounded overflow-hidden border border-royalGold-400/40 bg-royalGold-500/10 grid place-items-center"
                          fallbackIconSize={14}
                          fallbackIconClassName="text-royalGold-400"
                        />
                        <span className="font-bold">{row.name}</span>
                        <span className="text-xs text-white/40">[{row.tag}]</span>
                        {isPlus && <Crown size={12} className="text-royalGold-300" />}
                        {(row.badges || []).slice(0, 3).map((b) => (
                          <span
                            key={b.id}
                            title={b.label}
                            data-testid={`badge-${row.id}-${b.id}`}
                            className="inline-flex h-5 min-w-5 items-center justify-center rounded-md border border-royalGold-200/75 bg-gradient-to-b from-royalGold-200 via-royalGold-500 to-royalGold-700 px-1 text-[10px] font-display font-black uppercase text-white shadow-[0_0_10px_rgba(212,175,55,0.55)]"
                          >
                            {(() => {
                              const label = String(b.label || b.kind || "").trim();
                              if (!label) return "B";
                              if (/^admin$/i.test(label)) return "A";
                              if (/^(prev|plus|personal)/i.test(label)) return "P";
                              return label[0].toUpperCase();
                            })()}
                          </span>
                        ))}
                      </Link>
                    ) : (
                      <Link to={`/players/${row.id}`} data-testid={`lb-player-${row.id}`} className={`inline-flex items-center gap-3 hover:text-royalGold-300 ${isPlus ? "plus-glow rounded-md px-2 py-1" : ""}`}>
                        <div className="h-8 w-8 rounded-md bg-gradient-to-b from-royalGold-200/35 via-royalGold-500/25 to-royalGold-700/20 border border-royalGold-300/50 grid place-items-center text-royalGold-200 font-display shadow-[0_0_10px_rgba(212,175,55,0.28)]">{row.username[0].toUpperCase()}</div>
                        <span className="font-bold">{row.username}</span>
                        {isPlus && <Crown size={12} className="text-royalGold-300" />}
                      </Link>
                    )}
                  </td>
                  <td className="py-3 px-4 text-white/70">
                    <span className="text-emerald-400">{wins}</span>
                    <span className="text-white/30 mx-1">/</span>
                    <span className="text-destructive">{losses}</span>
                  </td>
                  <td className="py-3 px-4 text-center font-mono text-royalGold-300">{kd}</td>
                  <td className="py-3 px-4 text-end font-display font-black text-royalGold-300">{row.points}</td>
                </tr>
              );
            })}
            {data.length === 0 && (
              <tr><td colSpan={5} className="py-12 text-center text-white/40">لا توجد بيانات</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
