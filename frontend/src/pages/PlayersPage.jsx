import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import api from "../api";
import { Search, Sparkles } from "lucide-react";

export default function PlayersPage() {
  const [users, setUsers] = useState([]);
  const [q, setQ] = useState("");

  useEffect(() => {
    api.get("/users/search", { params: { q } }).then((r) => setUsers(r.data));
  }, [q]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-display font-black text-3xl md:text-4xl">اللاعبون</h1>
        <p className="text-white/50 mt-1">ابحث عن لاعب بالاسم أو البريد</p>
      </div>

      <div className="relative max-w-xl">
        <Search size={18} className="absolute right-3 top-1/2 -translate-y-1/2 text-white/30" />
        <input
          data-testid="search-players"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="اسم اللاعب..."
          className="w-full bg-surface border b-soft rounded-md pr-10 pl-4 py-3 outline-none focus:border-gold-500/40"
        />
      </div>

      <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {users.map((u) => (
          <Link
            key={u.id}
            to={`/players/${u.id}`}
            data-testid={`player-${u.id}`}
            className={`bg-surface border b-soft rounded-lg p-4 flex items-center gap-3 fade-in hover:border-gold-500/40 transition ${u.is_personal_plus ? "plus-glow" : ""}`}
          >
            <div className="h-12 w-12 rounded-md bg-gold-500/10 text-gold-500 grid place-items-center font-display font-black text-lg overflow-hidden">
              {u.is_personal_plus && u.avatar ? (
                <img src={u.avatar} alt={u.username} className="h-full w-full object-cover" />
              ) : (u.username[0] || "?").toUpperCase()}
            </div>
            <div className="flex-1 min-w-0">
              <div className="font-bold truncate flex items-center gap-1">
                {u.username}
                {u.is_personal_plus && <Sparkles size={11} className="text-gold-500" />}
              </div>
              <div className="text-xs text-white/40 truncate">
                {u.role === "owner" ? "مالك" : u.role === "admin" ? "منظم" : u.clan_id ? "في كلان" : "حر"}
              </div>
            </div>
            <div className="text-gold-500 font-display font-black">{u.points}</div>
          </Link>
        ))}
        {users.length === 0 && <div className="col-span-full text-center text-white/40 py-12">لا توجد نتائج</div>}
      </div>
    </div>
  );
}
