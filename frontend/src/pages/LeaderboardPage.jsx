import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import api from "../api";
import { Trophy, Crown, Shield } from "lucide-react";

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

      <div className="inline-flex bg-surface border b-soft rounded-md p-1">
        <button data-testid="tab-lb-clans" onClick={() => setTab("clans")} className={`px-5 py-2 rounded text-sm ${tab === "clans" ? "bg-gold-500 text-black font-bold" : "text-white/60"}`}>
          الكلانات
        </button>
        <button data-testid="tab-lb-players" onClick={() => setTab("players")} className={`px-5 py-2 rounded text-sm ${tab === "players" ? "bg-gold-500 text-black font-bold" : "text-white/60"}`}>
          اللاعبون
        </button>
      </div>

      <div className="bg-surface border b-soft rounded-xl overflow-hidden">
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
              const isPlus = tab === "clans" ? row.is_plus : row.is_personal_plus;
              return (
                <tr key={row.id} data-testid={`lb-row-${idx}`} className="border-t b-soft hover:bg-white/[0.03] transition">
                  <td className="py-3 px-4">
                    <div className={`inline-grid place-items-center h-8 w-8 rounded-md font-display font-black ${
                      idx === 0 ? "bg-gold-500 text-black" :
                      idx === 1 ? "bg-slate-300 text-black" :
                      idx === 2 ? "bg-amber-700 text-white" :
                      "bg-white/5 text-white/60"
                    }`}>{idx + 1}</div>
                  </td>
                  <td className="py-3 px-4">
                    {tab === "clans" ? (
                      <Link to={`/clans/${row.id}`} className={`inline-flex items-center gap-3 hover:text-gold-500 ${isPlus ? "plus-glow rounded-md px-2 py-1" : ""}`}>
                        <Shield size={18} className="text-gold-500/70" />
                        <span className="font-bold">{row.name}</span>
                        <span className="text-xs text-white/40">[{row.tag}]</span>
                        {isPlus && <Crown size={12} className="text-gold-500" />}
                      </Link>
                    ) : (
                      <Link to={`/players/${row.id}`} data-testid={`lb-player-${row.id}`} className={`inline-flex items-center gap-3 hover:text-gold-500 ${isPlus ? "plus-glow rounded-md px-2 py-1" : ""}`}>
                        <div className="h-8 w-8 rounded bg-white/5 grid place-items-center text-gold-500 font-display">{row.username[0].toUpperCase()}</div>
                        <span className="font-bold">{row.username}</span>
                        {isPlus && <Crown size={12} className="text-gold-500" />}
                      </Link>
                    )}
                  </td>
                  <td className="py-3 px-4 text-white/70">
                    <span className="text-emerald-400">{wins}</span>
                    <span className="text-white/30 mx-1">/</span>
                    <span className="text-destructive">{losses}</span>
                  </td>
                  <td className="py-3 px-4 text-center font-mono text-gold-500">{kd}</td>
                  <td className="py-3 px-4 text-end font-display font-black text-gold-500">{row.points}</td>
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
