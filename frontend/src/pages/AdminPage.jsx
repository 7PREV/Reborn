import { useEffect, useState, useCallback } from "react";
import { Link } from "react-router-dom";
import api, { formatApiErrorDetail } from "../api";
import { useAuth } from "../AuthContext";
import { AlertCircle, ScrollText, Trophy, Shield, Sparkles, Crown, UserCheck, UserX, Search, Edit3, Mail, KeyRound, X } from "lucide-react";
import { toast } from "sonner";
import BannerManager from "../components/admin/BannerManager";

function EditUserModal({ target, onClose, onSaved }) {
  const [form, setForm] = useState({
    username: target.username || "",
    email: target.email || "",
    password: "",
    act: target.act || "",
  });
  const [busy, setBusy] = useState(false);
  const submit = async (e) => {
    e.preventDefault();
    const payload = {};
    if (form.username !== target.username) payload.username = form.username;
    if (form.email !== target.email) payload.email = form.email;
    if (form.password) payload.password = form.password;
    if (form.act !== (target.act || "")) payload.act = form.act;
    if (Object.keys(payload).length === 0) {
      toast.info("لا تغييرات");
      return onClose();
    }
    setBusy(true);
    try {
      await api.put(`/admin/users/${target.id}`, payload);
      toast.success("تم تحديث المستخدم");
      onSaved();
      onClose();
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail));
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-black/70 backdrop-blur-xl p-4">
      <form onSubmit={submit} className="bg-surface border b-soft rounded-xl p-6 w-full max-w-md space-y-3" data-testid="edit-user-form">
        <div className="flex items-center justify-between">
          <h2 className="font-display font-black text-xl flex items-center gap-2"><Edit3 size={18} className="text-gold-500" /> تعديل {target.username}</h2>
          <button type="button" onClick={onClose} className="p-1 rounded hover:bg-white/5"><X size={16} /></button>
        </div>
        <div>
          <label className="text-xs uppercase tracking-widest text-white/50 mb-1 block">اسم المستخدم</label>
          <input data-testid="edit-username" value={form.username} onChange={(e) => setForm({ ...form, username: e.target.value })} className="w-full bg-background border b-soft rounded-md px-3 py-2 outline-none text-sm" />
        </div>
        <div>
          <label className="text-xs uppercase tracking-widest text-white/50 mb-1 block">البريد</label>
          <input data-testid="edit-email" type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} className="w-full bg-background border b-soft rounded-md px-3 py-2 outline-none text-sm" />
        </div>
        <div>
          <label className="text-xs uppercase tracking-widest text-white/50 mb-1 block">Activision ID</label>
          <input data-testid="edit-act" value={form.act} onChange={(e) => setForm({ ...form, act: e.target.value })} className="w-full bg-background border b-soft rounded-md px-3 py-2 outline-none text-sm" />
        </div>
        <div>
          <label className="text-xs uppercase tracking-widest text-white/50 mb-1 block">كلمة مرور جديدة (اختياري)</label>
          <input data-testid="edit-password" type="text" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} placeholder="اتركها فارغة لعدم التغيير" className="w-full bg-background border b-soft rounded-md px-3 py-2 outline-none text-sm" />
        </div>
        <button data-testid="edit-user-submit" disabled={busy} type="submit" className="w-full py-2 rounded-md bg-gold-500 text-black font-bold hover:bg-gold-400 disabled:opacity-50">{busy ? "..." : "حفظ"}</button>
      </form>
    </div>
  );
}

function UserRoleManager() {
  const { user } = useAuth();
  const [users, setUsers] = useState([]);
  const [q, setQ] = useState("");
  const [editTarget, setEditTarget] = useState(null);
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
        <UserCheck className="text-gold-500" /> إدارة اللاعبين {isOwner && <span className="text-[10px] uppercase tracking-widest text-gold-500">المالك فقط</span>}
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
              <div className="text-[10px] text-white/40 truncate">{u.email}{u.act ? ` • ${u.act}` : ""}</div>
            </div>
            <div className="text-[10px] uppercase tracking-widest text-white/40">
              {u.role === "owner" ? "مالك" : u.role === "admin" ? "منظم" : "لاعب"}
            </div>
            {u.role !== "owner" && (
              <button data-testid={`edit-user-${u.id}`} onClick={() => setEditTarget(u)} className="px-2 py-1 rounded text-xs bg-white/5 hover:bg-white/10 flex items-center gap-1">
                <Edit3 size={12} /> تعديل
              </button>
            )}
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
      {editTarget && (
        <EditUserModal target={editTarget} onClose={() => setEditTarget(null)} onSaved={load} />
      )}
    </section>
  );
}

function ClanEditor() {
  const [clans, setClans] = useState([]);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState({ name: "", tag: "", description: "" });
  const [transferTarget, setTransferTarget] = useState(null);

  const load = useCallback(async () => {
    const { data } = await api.get("/clans");
    setClans(data);
  }, []);
  useEffect(() => { load(); }, [load]);

  const startEdit = (c) => { setEditing(c); setForm({ name: c.name, tag: c.tag, description: c.description || "" }); };
  const save = async (e) => {
    e.preventDefault();
    try {
      await api.put(`/admin/clans/${editing.id}`, form);
      toast.success("تم تحديث الكلان");
      setEditing(null);
      load();
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail));
    }
  };

  const startTransfer = async (c) => {
    const { data } = await api.get(`/clans/${c.id}`);
    setTransferTarget(data);
  };

  const transferOwnership = async (memberId) => {
    if (!transferTarget) return;
    // eslint-disable-next-line no-alert
    if (!confirm("نقل ملكية الكلان لهذا اللاعب؟")) return;
    try {
      await api.post(`/admin/clans/${transferTarget.id}/transfer/${memberId}`);
      toast.success("تم نقل ملكية الكلان");
      setTransferTarget(null);
      load();
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail));
    }
  };

  return (
    <section>
      <h2 className="font-display font-black text-2xl mb-4 flex items-center gap-2">
        <Shield className="text-gold-500" /> إدارة الكلانات
      </h2>
      <div className="bg-surface border b-soft rounded-lg divide-y divide-white/5 max-h-[400px] overflow-y-auto">
        {clans.map((c) => (
          <div key={c.id} className="p-3 flex items-center gap-3" data-testid={`admin-clan-${c.id}`}>
            <div className="h-9 w-9 rounded-md bg-gold-500/10 grid place-items-center text-gold-500"><Shield size={16} /></div>
            <div className="flex-1 min-w-0">
              <div className="font-bold truncate">{c.name} <span className="text-xs text-gold-500">[{c.tag}]</span></div>
              <div className="text-[10px] text-white/40 truncate">{c.points} نقطة • {c.member_ids?.length || 0} لاعب</div>
            </div>
            <button data-testid={`transfer-clan-${c.id}`} onClick={() => startTransfer(c)} className="px-2 py-1 rounded text-xs bg-gold-500/10 text-gold-500 hover:bg-gold-500/20 flex items-center gap-1">
              <Crown size={12} /> نقل الملكية
            </button>
            <button data-testid={`edit-clan-${c.id}`} onClick={() => startEdit(c)} className="px-2 py-1 rounded text-xs bg-white/5 hover:bg-white/10 flex items-center gap-1">
              <Edit3 size={12} /> تعديل
            </button>
          </div>
        ))}
        {clans.length === 0 && <div className="p-4 text-center text-white/40 text-sm">لا توجد كلانات</div>}
      </div>
      {editing && (
        <div className="fixed inset-0 z-50 grid place-items-center bg-black/70 backdrop-blur-xl p-4">
          <form onSubmit={save} className="bg-surface border b-soft rounded-xl p-6 w-full max-w-md space-y-3" data-testid="edit-clan-form">
            <div className="flex items-center justify-between">
              <h2 className="font-display font-black text-xl">تعديل {editing.name}</h2>
              <button type="button" onClick={() => setEditing(null)} className="p-1 rounded hover:bg-white/5"><X size={16} /></button>
            </div>
            <input data-testid="edit-clan-name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="الاسم" className="w-full bg-background border b-soft rounded-md px-3 py-2 outline-none text-sm" />
            <input data-testid="edit-clan-tag" value={form.tag} onChange={(e) => setForm({ ...form, tag: e.target.value })} placeholder="التاج" className="w-full bg-background border b-soft rounded-md px-3 py-2 outline-none text-sm" />
            <textarea data-testid="edit-clan-desc" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} placeholder="الوصف" rows={2} className="w-full bg-background border b-soft rounded-md px-3 py-2 outline-none text-sm resize-none" />
            <button data-testid="edit-clan-submit" type="submit" className="w-full py-2 rounded-md bg-gold-500 text-black font-bold hover:bg-gold-400">حفظ</button>
          </form>
        </div>
      )}
      {transferTarget && (
        <div className="fixed inset-0 z-50 grid place-items-center bg-black/70 backdrop-blur-xl p-4">
          <div className="bg-surface border b-soft rounded-xl p-6 w-full max-w-md space-y-3" data-testid="transfer-modal">
            <div className="flex items-center justify-between">
              <h2 className="font-display font-black text-xl flex items-center gap-2">
                <Crown size={18} className="text-gold-500" /> نقل ملكية {transferTarget.name}
              </h2>
              <button type="button" onClick={() => setTransferTarget(null)} className="p-1 rounded hover:bg-white/5"><X size={16} /></button>
            </div>
            <p className="text-xs text-white/50">اختر اللاعب الذي ستنقل إليه القيادة. يجب أن يكون عضواً في الكلان.</p>
            <div className="max-h-[300px] overflow-y-auto divide-y divide-white/5">
              {(transferTarget.members || []).filter((m) => m.id !== transferTarget.leader_id).map((m) => (
                <button
                  key={m.id}
                  data-testid={`transfer-to-${m.id}`}
                  onClick={() => transferOwnership(m.id)}
                  className="w-full p-3 flex items-center gap-3 hover:bg-gold-500/5 text-right"
                >
                  <div className="h-8 w-8 rounded-md bg-white/5 grid place-items-center text-gold-500 font-display">{m.username[0]?.toUpperCase()}</div>
                  <div className="flex-1 min-w-0">
                    <div className="font-bold text-sm">{m.username}</div>
                    <div className="text-[10px] text-white/40">{m.points || 0} نقطة</div>
                  </div>
                  <Crown size={14} className="text-gold-500" />
                </button>
              ))}
              {(transferTarget.members || []).filter((m) => m.id !== transferTarget.leader_id).length === 0 && (
                <div className="p-4 text-center text-white/40 text-sm">لا يوجد أعضاء آخرون</div>
              )}
            </div>
          </div>
        </div>
      )}
    </section>
  );
}

function PasswordResetsPanel() {
  const [resets, setResets] = useState([]);
  const load = useCallback(async () => {
    try {
      const { data } = await api.get("/admin/password-resets");
      setResets(data);
    } catch (err) {
      // expected for non-staff
    }
  }, []);
  useEffect(() => { load(); }, [load]);

  const complete = async (rid) => {
    await api.post(`/admin/password-resets/${rid}/complete`);
    toast.success("تم تعليم الطلب كمكتمل");
    load();
  };

  return (
    <section data-testid="password-resets-section">
      <h2 className="font-display font-black text-2xl mb-4 flex items-center gap-2">
        <KeyRound className="text-gold-500" /> طلبات استعادة كلمة المرور
      </h2>
      <div className="bg-surface border b-soft rounded-lg divide-y divide-white/5">
        {resets.length === 0 && (
          <div className="p-4 text-center text-white/40 text-sm">لا توجد طلبات معلّقة</div>
        )}
        {resets.map((r) => (
          <div key={r.id} className="p-3 flex items-center gap-3" data-testid={`reset-${r.id}`}>
            <Mail size={14} className="text-gold-500" />
            <div className="flex-1 min-w-0">
              <div className="font-bold text-sm">{r.username} <span className="text-white/40 text-xs">• {r.email}</span></div>
              <div className="text-[10px] text-white/40">
                Token: <span className="text-gold-500 font-mono">{r.token}</span> • {new Date(r.created_at).toLocaleString("ar")}
              </div>
            </div>
            <button onClick={() => complete(r.id)} className="px-3 py-1.5 rounded bg-gold-500/10 text-gold-500 text-xs hover:bg-gold-500/20">
              تم الإرسال
            </button>
          </div>
        ))}
      </div>
      <p className="text-[10px] text-white/40 mt-2">
        ⚠️ ميزة الإيميل غير مُفعّلة بعد. أرسل الرابط يدويًا للاعب أو وفّر API key لخدمة Resend/SendGrid.
      </p>
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
      <ClanEditor />
      <PasswordResetsPanel />
      <BannerManager />
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
