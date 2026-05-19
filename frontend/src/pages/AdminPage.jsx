import { useEffect, useState, useCallback } from "react";
import { Link } from "react-router-dom";
import api, { formatApiErrorDetail } from "../api";
import { useAuth } from "../AuthContext";
import { AlertCircle, ScrollText, Trophy, Shield, Sparkles, Crown, UserCheck, UserX, Search } from "lucide-react";
import { toast } from "sonner";

function UserRoleManager() {
  const { user } = useAuth();
  const [users, setUsers] = useState([]);
  const [q, setQ] = useState("");
  const isOwner = user?.role === "owner";

  const load = useCallback(async () => {
    const { data } = await api.get("/admin/users");
    setUsers(data);
  }, []);

  useEffect(() => { load(); }, [load]);

  const setRole = async (uid, role) => {
    try {
      await api.post(`/admin/users/${uid}/role`, { role });
      toast.success(role === "admin" ? "تم رفعه لمنظم" : "تم خفض دوره");
      load();
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail));
    }
  };

  const filtered = users.filter((u) =>
    !q || u.username?.toLowerCase().includes(q.toLowerCase()) || u.email?.includes(q)
  );

  return (
    <section>
      <h2 className="font-display font-black text-2xl mb-4 flex items-center gap-2">
        <UserCheck className="text-gold-500" /> إدارة الأدوار {isOwner && <span className="text-[10px] uppercase tracking-widest text-gold-500">المالك فقط</span>}
      </h2>
      <div className="relative max-w-md mb-4">
        <Search size={16} className="absolute right-3 top-1/2 -translate-y-1/2 text-white/30" />
        <input
          data-testid="users-search"
          value={q} onChange={(e) => setQ(e.target.value)}
          placeholder="بحث..."
          className="w-full bg-surface border b-soft rounded-md pr-10 pl-4 py-2 outline-none focus:border-gold-500/40 text-sm"
        />
      </div>
      <div className="bg-surface border b-soft rounded-lg divide-y divide-white/5 max-h-[500px] overflow-y-auto">
        {filtered.map((u) => (
          <div key={u.id} data-testid={`user-row-${u.id}`} className="p-3 flex items-center gap-3">
            <div className="h-9 w-9 rounded-md bg-white/5 grid place-items-center text-gold-500 font-display">
              {u.username[0]?.toUpperCase()}
            </div>
            <div className="flex-1 min-w-0">
              <div className="font-bold truncate flex items-center gap-1">
                {u.username}
                {u.role === "owner" && <Crown size={12} className="text-gold-500" />}
                {u.is_plus && <Sparkles size={10} className="text-gold-500" />}
              </div>
              <div className="text-[10px] text-white/40 truncate">{u.email}</div>
            </div>
            <div className="text-[10px] uppercase tracking-widest text-white/40">
              {u.role === "owner" ? "مالك" : u.role === "admin" ? "منظم" : "لاعب"}
            </div>
            {isOwner && u.role !== "owner" && (
              <div className="flex gap-1">
                {u.role === "admin" ? (
                  <button data-testid={`demote-${u.id}`} onClick={() => setRole(u.id, "player")} className="px-2 py-1 rounded text-xs bg-destructive/10 text-destructive hover:bg-destructive/20 flex items-center gap-1">
                    <UserX size={12} /> خفض
                  </button>
                ) : (
                  <button data-testid={`promote-${u.id}`} onClick={() => setRole(u.id, "admin")} className="px-2 py-1 rounded text-xs bg-gold-500/10 text-gold-500 hover:bg-gold-500/20 flex items-center gap-1">
                    <UserCheck size={12} /> منظم
                  </button>
                )}
              </div>
            )}
          </div>
        ))}
        {filtered.length === 0 && <div className="p-4 text-center text-white/40 text-sm">لا توجد نتائج</div>}
      </div>
    </section>
  );
}

export default function AdminPage() {
  const { user } = useAuth();
  const [live, setLive] = useState([]);
  const [history, setHistory] = useState([]);
  const [clans, setClans] = useState([]);
  const [disputes, setDisputes] = useState([]);
  const [tournaments, setTournaments] = useState([]);

  useEffect(() => {
    if (!user || (user.role !== "admin" && user.role !== "owner")) return;
    api.get("/matches/live").then((r) => {
      setLive(r.data);
      setDisputes(r.data.filter((m) => (m.maps || []).some((mp) => mp.disputed)));
    });
    api.get("/matches/history").then((r) => setHistory(r.data));
    api.get("/clans").then((r) => setClans(r.data));
    api.get("/tournaments").then((r) => setTournaments(r.data));
  }, [user]);

  if (!user || (user.role !== "admin" && user.role !== "owner")) {
    return (
      <div className="bg-surface border b-soft rounded-xl p-12 text-center">
        <AlertCircle size={32} className="mx-auto mb-3 text-destructive" />
        غير مصرح — للمنظمين والمالك فقط
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <div>
        <div className="text-xs uppercase tracking-widest text-gold-500 mb-2">
          {user.role === "owner" ? "لوحة المالك" : "لوحة الإدارة"}
        </div>
        <h1 className="font-display font-black text-3xl md:text-4xl flex items-center gap-3">
          مرحباً يا {user.username}
          {user.role === "owner" && <Crown className="text-gold-500" size={28} />}
        </h1>
        <p className="text-white/50 mt-1">
          {user.role === "owner" ? "تحكم كامل: الأدوار، البطولات، المباريات، القوانين" : "إدارة البطولات والمباريات والقوانين"}
        </p>
      </div>

      <div className="grid sm:grid-cols-4 gap-4">
        <Stat label="مباشر" value={live.length} accent />
        <Stat label="نزاعات" value={disputes.length} destructive />
        <Stat label="٢٤ ساعة" value={history.length} />
        <Stat label="بطولات" value={tournaments.length} />
      </div>

      <div className="grid lg:grid-cols-3 gap-4">
        <Link to="/tournaments" className="bg-surface border b-soft rounded-lg p-5 hover:border-gold-500/30 flex items-center gap-3">
          <Trophy className="text-gold-500" />
          <div>
            <div className="font-display font-bold">إدارة البطولات</div>
            <div className="text-xs text-white/50">{tournaments.length} بطولة</div>
          </div>
        </Link>
        <Link to="/rules" className="bg-surface border b-soft rounded-lg p-5 hover:border-gold-500/30 flex items-center gap-3">
          <ScrollText className="text-gold-500" />
          <div>
            <div className="font-display font-bold">القوانين</div>
            <div className="text-xs text-white/50">إضافة، تعديل وحذف</div>
          </div>
        </Link>
        <div className="bg-surface border b-soft rounded-lg p-5 flex items-center gap-3">
          <Shield className="text-gold-500" />
          <div>
            <div className="font-display font-bold">{clans.length} كلان</div>
            <div className="text-xs text-white/50">إجمالي الكلانات النشطة</div>
          </div>
        </div>
      </div>

      {disputes.length > 0 && (
        <section>
          <h2 className="font-display font-black text-2xl mb-4 text-destructive flex items-center gap-2">
            <AlertCircle /> نزاعات تنتظر قرارك ({disputes.length})
          </h2>
          <div className="bg-surface border border-destructive/30 rounded-lg divide-y divide-white/5">
            {disputes.map((m) => (
              <Link key={m.id} to={`/matches/${m.id}`} className="p-4 flex items-center gap-4 hover:bg-destructive/5">
                <span className="live-dot" />
                <div className="flex-1 flex items-center gap-3">
                  <span className="font-bold">{m.clan_a?.tag}</span>
                  <span className="text-white/40">vs</span>
                  <span className="font-bold">{m.clan_b?.tag}</span>
                </div>
                <span className="text-xs text-destructive">حلّ النزاع ←</span>
              </Link>
            ))}
          </div>
        </section>
      )}

      <UserRoleManager />
    </div>
  );
}

function Stat({ label, value, accent, destructive }) {
  let valueColor = "";
  if (accent) valueColor = "text-gold-500";
  if (destructive) valueColor = "text-destructive";
  return (
    <div className="bg-surface border b-soft rounded-lg p-5">
      <div className={`text-xs uppercase tracking-widest ${destructive ? "text-destructive" : "text-white/40"}`}>{label}</div>
      <div className={`text-3xl font-display font-black ${valueColor}`}>{value}</div>
    </div>
  );
}
