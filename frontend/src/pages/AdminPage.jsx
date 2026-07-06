import { useEffect, useState, useCallback } from "react";
import { Link } from "react-router-dom";
import api, { formatApiErrorDetail } from "../api";
import { useAuth } from "../AuthContext";
import { AlertCircle, ScrollText, Trophy, Shield, Sparkles, Crown, UserCheck, UserX, Search, Edit3, Mail, KeyRound, X, Zap, Plus, Image as ImageIcon, Gamepad2, Power } from "lucide-react";
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
    if (!isOwner) {
      setUsers([]);
      return;
    }
    try {
      const { data } = await api.get("/admin/users");
      setUsers(data);
    } catch {
      setUsers([]);
    }
  }, [isOwner]);

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
  const [suspendTarget, setSuspendTarget] = useState(null);
  const [suspendForm, setSuspendForm] = useState({ hours: 24, reason: "" });
  const [suspendBusy, setSuspendBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const { data } = await api.get("/clans");
      setClans(data);
    } catch {
      setClans([]);
    }
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
    try {
      const { data } = await api.get(`/clans/${c.id}`);
      setTransferTarget(data);
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail));
    }
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

  const openSuspend = (clan) => {
    setSuspendTarget(clan);
    setSuspendForm({ hours: 24, reason: "" });
  };

  const submitSuspend = async (e) => {
    e.preventDefault();
    if (!suspendTarget) return;
    const hours = Number(suspendForm.hours || 0);
    if (!Number.isFinite(hours) || hours < 1) {
      return toast.error("مدة الإيقاف يجب أن تكون ساعة واحدة على الأقل");
    }
    setSuspendBusy(true);
    try {
      await api.post(`/admin/clans/${suspendTarget.id}/suspend`, {
        hours,
        reason: suspendForm.reason || "",
      });
      toast.success("تم إيقاف الكلان بنجاح");
      setSuspendTarget(null);
      load();
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail));
    } finally {
      setSuspendBusy(false);
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
              {c.suspended_until && (
                <div className="text-[10px] text-rose-300 truncate">موقوف حتى {new Date(c.suspended_until).toLocaleString("ar")}</div>
              )}
            </div>
            <button data-testid={`transfer-clan-${c.id}`} onClick={() => startTransfer(c)} className="px-2 py-1 rounded text-xs bg-gold-500/10 text-gold-500 hover:bg-gold-500/20 flex items-center gap-1">
              <Crown size={12} /> نقل الملكية
            </button>
            <button data-testid={`edit-clan-${c.id}`} onClick={() => startEdit(c)} className="px-2 py-1 rounded text-xs bg-white/5 hover:bg-white/10 flex items-center gap-1">
              <Edit3 size={12} /> تعديل
            </button>
            <button data-testid={`suspend-clan-${c.id}`} onClick={() => openSuspend(c)} className="px-2 py-1 rounded text-xs bg-destructive/10 text-destructive hover:bg-destructive/20 flex items-center gap-1">
              <Power size={12} /> إيقاف الكلان
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
      {suspendTarget && (
        <div className="fixed inset-0 z-50 grid place-items-center bg-black/70 backdrop-blur-xl p-4">
          <form onSubmit={submitSuspend} className="bg-surface border b-soft rounded-xl p-6 w-full max-w-md space-y-3" data-testid="suspend-clan-form">
            <div className="flex items-center justify-between">
              <h2 className="font-display font-black text-xl text-destructive">إيقاف الكلان: {suspendTarget.name}</h2>
              <button type="button" onClick={() => setSuspendTarget(null)} className="p-1 rounded hover:bg-white/5"><X size={16} /></button>
            </div>
            <div>
              <label className="text-xs uppercase tracking-widest text-white/50 mb-1 block">المدة (كم ساعة)</label>
              <input
                data-testid="suspend-hours"
                type="number"
                min={1}
                value={suspendForm.hours}
                onChange={(e) => setSuspendForm((p) => ({ ...p, hours: e.target.value }))}
                className="w-full bg-background border b-soft rounded-md px-3 py-2 outline-none text-sm"
              />
            </div>
            <div>
              <label className="text-xs uppercase tracking-widest text-white/50 mb-1 block">سبب الإيقاف (اختياري)</label>
              <textarea
                data-testid="suspend-reason"
                value={suspendForm.reason}
                onChange={(e) => setSuspendForm((p) => ({ ...p, reason: e.target.value }))}
                rows={3}
                placeholder="مثال: مخالفات متكررة / سلوك غير رياضي"
                className="w-full bg-background border b-soft rounded-md px-3 py-2 outline-none text-sm resize-none"
              />
            </div>
            <div className="flex items-center justify-end gap-2">
              <button type="button" onClick={() => setSuspendTarget(null)} className="px-3 py-2 rounded text-sm hover:bg-white/5">إلغاء</button>
              <button data-testid="suspend-submit" type="submit" disabled={suspendBusy} className="px-4 py-2 rounded bg-destructive text-white text-sm font-bold hover:bg-destructive/90 disabled:opacity-50">
                {suspendBusy ? "..." : "تأكيد الإيقاف"}
              </button>
            </div>
          </form>
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
    try {
      await api.post(`/admin/password-resets/${rid}/complete`);
      toast.success("تم تعليم الطلب كمكتمل");
      load();
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail));
    }
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

function LeaguesManager() {
  const [leagues, setLeagues] = useState([]);
  const [creating, setCreating] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState({ name: "", game: "Call of Duty", rules: "", description: "", rules_image: "", super_rivals_enabled: false });
  const [busy, setBusy] = useState(false);
  const [completingLeagueId, setCompletingLeagueId] = useState("");
  const [recentSuperRivals, setRecentSuperRivals] = useState([]);

  const load = useCallback(async () => {
    try {
      const { data } = await api.get("/leagues/active");
      setLeagues(data);
    } catch (err) {
      // benign
    }
  }, []);
  useEffect(() => { load(); }, [load]);

  const reset = () => {
    setForm({ name: "", game: "Call of Duty", rules: "", description: "", rules_image: "", super_rivals_enabled: false });
    setCreating(false);
    setEditing(null);
  };

  const onImage = async (e) => {
    const f = e.target.files?.[0];
    if (!f) return;
    if (f.size > 3_000_000) return toast.error("الصورة كبيرة (الحد 3MB)");
    const fr = new FileReader();
    fr.onload = () => setForm((p) => ({ ...p, rules_image: fr.result }));
    fr.readAsDataURL(f);
  };

  const submit = async (e) => {
    e.preventDefault();
    if (!form.name || !form.game) return toast.error("الاسم واللعبة إلزاميان");
    setBusy(true);
    try {
      if (editing) {
        await api.put(`/leagues/${editing}`, form);
        toast.success("تم تحديث الدوري");
      } else {
        await api.post("/leagues/custom", form);
        toast.success("تم إنشاء الدوري");
      }
      reset();
      load();
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail));
    } finally {
      setBusy(false);
    }
  };

  const finishLeague = async (lid) => {
    const league = leagues.find((x) => x.id === lid);
    const superMsg = league?.super_rivals_enabled
      ? "سيتم إنشاء بطولة السوبر رايفلز تلقائياً من أفضل 4 كلانات."
      : "نظام السوبر رايفلز غير مفعل لهذا الدوري.";
    // eslint-disable-next-line no-alert
    if (!confirm(`تأكيد اكتمال الدوري الآن؟ ${superMsg}`)) return;
    setCompletingLeagueId(lid);
    try {
      let result;
      try {
        const { data } = await api.patch(`/leagues/${lid}/status`, { status: "completed" });
        result = data;
      } catch {
        const { data } = await api.post(`/leagues/${lid}/complete`);
        result = data;
      }

      const tid = result?.super_rivals_tournament_id;
      if (tid) {
        setRecentSuperRivals((prev) => {
          const next = [
            {
              league_id: lid,
              tournament_id: tid,
              qualified_clan_ids: result?.qualified_clan_ids || [],
              created_at: new Date().toISOString(),
            },
            ...prev.filter((x) => x.league_id !== lid),
          ];
          return next.slice(0, 6);
        });
        toast.success("تم إنهاء الدوري وإنشاء بطولة السوبر رايفلز بنجاح", {
          description: "يمكنك فتح شجرة البطولة مباشرة من لوحة الإدارة.",
        });
      } else {
        toast.success("تم إنهاء الدوري");
      }
      load();
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail));
    } finally {
      setCompletingLeagueId("");
    }
  };

  const startEdit = (lg) => {
    setEditing(lg.id);
    setForm({
      name: lg.name, game: lg.game,
      rules: lg.rules || "", description: lg.description || "",
      rules_image: lg.rules_image || "",
      super_rivals_enabled: !!lg.super_rivals_enabled,
    });
    setCreating(true);
  };

  return (
    <section data-testid="leagues-manager">
      <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
        <h2 className="font-display font-black text-2xl flex items-center gap-2">
          <Gamepad2 className="text-gold-500" /> إدارة الدوريات المتعددة
        </h2>
        {!creating && (
          <button
            data-testid="open-league-form"
            onClick={() => setCreating(true)}
            className="px-3 py-2 rounded-md bg-gold-500 text-black text-sm font-bold hover:bg-gold-400 flex items-center gap-1"
          >
            <Plus size={14} /> دوري جديد
          </button>
        )}
      </div>

      {creating && (
        <form onSubmit={submit} className="bg-surface border b-soft rounded-xl p-5 space-y-3 mb-4" data-testid="league-form">
          <div className="grid sm:grid-cols-2 gap-3">
            <div>
              <label className="text-xs uppercase tracking-widest text-white/50 mb-1 block">اسم الدوري</label>
              <input
                data-testid="league-name"
                required minLength={2} maxLength={80}
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                placeholder="دوري الأبطال - الموسم الأول"
                className="w-full bg-background border b-soft rounded-md px-3 py-2 outline-none text-sm focus:border-gold-500/40"
              />
            </div>
            <div>
              <label className="text-xs uppercase tracking-widest text-white/50 mb-1 block">اللعبة</label>
              <input
                data-testid="league-game"
                required minLength={2} maxLength={40}
                value={form.game}
                onChange={(e) => setForm({ ...form, game: e.target.value })}
                placeholder="Call of Duty MW3"
                className="w-full bg-background border b-soft rounded-md px-3 py-2 outline-none text-sm focus:border-gold-500/40"
              />
            </div>
          </div>
          <div>
            <label className="text-xs uppercase tracking-widest text-white/50 mb-1 block">وصف</label>
            <input
              data-testid="league-description"
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
              placeholder="بطولة خاصة بـ Plus، 8 كلانات، خروج المغلوب"
              className="w-full bg-background border b-soft rounded-md px-3 py-2 outline-none text-sm"
            />
          </div>
          <div>
            <label className="text-xs uppercase tracking-widest text-white/50 mb-1 block">قوانين الدوري (نص)</label>
            <textarea
              data-testid="league-rules"
              value={form.rules}
              onChange={(e) => setForm({ ...form, rules: e.target.value })}
              placeholder="مثال: BO3 - 5v5 - الخريطة الممنوعة Nuketown - الأسلحة المسموحة..."
              rows={4}
              className="w-full bg-background border b-soft rounded-md px-3 py-2 outline-none text-sm resize-none"
            />
          </div>
          <label className="flex items-center gap-3 rounded-lg border border-royalGold-500/25 bg-royalGold-500/5 px-3 py-2.5 cursor-pointer hover:border-royalGold-500/45 transition">
            <input
              type="checkbox"
              checked={!!form.super_rivals_enabled}
              onChange={(e) => setForm({ ...form, super_rivals_enabled: e.target.checked })}
              className="h-4 w-4 accent-royalGold-500"
            />
            <span className="text-sm text-white/90">تفعيل نظام سوبر رايفلز لأول 4 مراكز</span>
          </label>
          <div>
            <label className="text-xs uppercase tracking-widest text-white/50 mb-1 block">صورة القوانين (اختياري — ≤3MB)</label>
            <div className="flex items-start gap-3 flex-wrap">
              <label className="cursor-pointer inline-flex items-center gap-2 px-3 py-2 rounded-md bg-background border b-soft hover:border-gold-500/40 text-sm">
                <ImageIcon size={14} />
                <span>اختر صورة</span>
                <input data-testid="league-image-input" type="file" accept="image/*" onChange={onImage} className="hidden" />
              </label>
              <input
                data-testid="league-image-url"
                value={form.rules_image.startsWith("http") ? form.rules_image : ""}
                onChange={(e) => setForm({ ...form, rules_image: e.target.value })}
                placeholder="أو ألصق رابط صورة (https://...)"
                className="flex-1 min-w-[200px] bg-background border b-soft rounded-md px-3 py-2 outline-none text-sm"
              />
              {form.rules_image && (
                <button
                  type="button"
                  onClick={() => setForm({ ...form, rules_image: "" })}
                  className="px-2 py-1 text-xs text-destructive hover:bg-destructive/10 rounded"
                >
                  حذف الصورة
                </button>
              )}
            </div>
            {form.rules_image && (
              <img src={form.rules_image} alt="rules" className="mt-3 rounded max-h-44 border b-soft" />
            )}
          </div>
          <div className="flex items-center gap-2 justify-end">
            <button type="button" onClick={reset} className="px-3 py-2 rounded text-sm hover:bg-white/5">إلغاء</button>
            <button data-testid="league-submit" type="submit" disabled={busy} className="px-4 py-2 rounded bg-gold-500 text-black text-sm font-bold hover:bg-gold-400 disabled:opacity-50">
              {busy ? "..." : editing ? "حفظ" : "إنشاء الدوري"}
            </button>
          </div>
        </form>
      )}

      {recentSuperRivals.length > 0 && (
        <div className="mb-4 rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-4" data-testid="super-rivals-generated-list">
          <div className="text-sm font-bold text-emerald-300 mb-2">تم إنشاء بطولات السوبر رايفلز</div>
          <div className="space-y-2">
            {recentSuperRivals.map((item) => (
              <div key={`${item.league_id}-${item.tournament_id}`} className="flex items-center justify-between gap-2 text-xs">
                <div className="text-white/80">
                  دوري #{item.league_id.slice(0, 8)} • المتأهلون: {item.qualified_clan_ids?.length || 0}
                </div>
                <Link
                  to={`/tournaments/${item.tournament_id}`}
                  className="px-2 py-1 rounded bg-emerald-500/20 text-emerald-300 hover:bg-emerald-500/30"
                >
                  فتح شجرة السوبر رايفلز
                </Link>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="bg-surface border b-soft rounded-lg divide-y divide-white/5">
        {leagues.length === 0 && (
          <div className="p-6 text-center text-white/40 text-sm">لا توجد دوريات نشطة بعد</div>
        )}
        {leagues.map((lg) => (
          <div key={lg.id} data-testid={`league-row-${lg.id}`} className="p-3 flex items-center gap-3 flex-wrap">
            <div className="h-10 w-10 rounded-md bg-gold-500/10 grid place-items-center text-gold-500">
              <Trophy size={18} />
            </div>
            <div className="flex-1 min-w-0">
              <div className="font-bold truncate">{lg.name}</div>
              <div className="text-[10px] text-white/40">
                {lg.game} • {lg.is_custom ? "مخصص" : "شهري"}
                {lg.rules_image && <span className="text-gold-500"> • صورة قوانين ✓</span>}
                {lg.super_rivals_enabled && <span className="text-royalGold-400"> • سوبر رايفلز: مفعل</span>}
              </div>
            </div>
            <button data-testid={`edit-league-${lg.id}`} onClick={() => startEdit(lg)} className="px-2 py-1 rounded text-xs bg-white/5 hover:bg-white/10 flex items-center gap-1">
              <Edit3 size={12} /> تعديل
            </button>
            <button
              data-testid={`finish-league-${lg.id}`}
              onClick={() => finishLeague(lg.id)}
              disabled={completingLeagueId === lg.id}
              className="px-2 py-1 rounded text-xs bg-gold-500/10 text-gold-500 hover:bg-gold-500/20 disabled:opacity-50"
            >
              {completingLeagueId === lg.id ? "جاري الإنهاء..." : "تأكيد اكتمال الدوري"}
            </button>
          </div>
        ))}
      </div>
    </section>
  );
}

function OwnerPlusGrants() {
  const { user } = useAuth();
  const [userQuery, setUserQuery] = useState("");
  const [userResults, setUserResults] = useState([]);
  const [clanQuery, setClanQuery] = useState("");
  const [clanResults, setClanResults] = useState([]);
  const [days, setDays] = useState(30);

  useEffect(() => {
    if (user?.role === "owner") {
      api.get("/clans").then((r) => setClanResults(r.data.slice(0, 60))).catch(() => {});
    }
  }, [user]);

  const searchUser = async (q) => {
    setUserQuery(q);
    if (q.length < 2) return setUserResults([]);
    try {
      const { data } = await api.get("/users/search", { params: { q } });
      setUserResults(data.slice(0, 6));
    } catch {
      setUserResults([]);
    }
  };

  const searchClan = async (q) => {
    setClanQuery(q);
    try {
      const query = (q || "").trim();
      const { data } = await api.get("/clans", query ? { params: { q: query } } : undefined);
      setClanResults((data || []).slice(0, query ? 25 : 60));
    } catch {
      setClanResults([]);
    }
  };

  const grantUser = async (uid, action) => {
    try {
      await api.post(`/admin/users/${uid}/personal-plus`, { action, days });
      toast.success(action === "grant" ? "تم تفعيل Personal Plus" : "تم إلغاء Personal Plus");
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail));
    }
  };

  const grantClan = async (cid, action) => {
    try {
      await api.post(`/admin/clans/${cid}/plus`, { action, days });
      toast.success(action === "grant" ? "تم تفعيل Clan Plus" : "تم إلغاء Clan Plus");
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail));
    }
  };

  if (user?.role !== "owner") return null;

  return (
    <section data-testid="owner-plus-block" className="bg-gold-500/5 border border-gold-500/40 rounded-2xl p-6">
      <h2 className="font-display font-black text-2xl mb-1 flex items-center gap-2">
        <Zap className="text-gold-500" /> منح Plus يدوياً (المالك فقط)
      </h2>
      <p className="text-xs text-white/50 mb-4">تجاوز بوابة الدفع وامنح Personal Plus أو Clan Plus لأي حساب أو كلان.</p>

      <div className="grid md:grid-cols-2 gap-6">
        <div>
          <div className="text-xs uppercase tracking-widest text-gold-500 mb-2">Personal Plus لمستخدم</div>
          <div className="flex items-center gap-2 mb-2">
            <input
              data-testid="plus-days"
              type="number" min={1} max={3650}
              value={days}
              onChange={(e) => setDays(Number(e.target.value))}
              className="w-20 bg-background border b-soft rounded-md px-2 py-1 text-sm"
            />
            <span className="text-xs text-white/40">يوم</span>
          </div>
          <div className="relative">
            <Search size={14} className="absolute right-3 top-1/2 -translate-y-1/2 text-white/30" />
            <input
              data-testid="plus-user-search"
              value={userQuery}
              onChange={(e) => searchUser(e.target.value)}
              placeholder="ابحث باسم أو بريد..."
              className="w-full bg-surface border b-soft rounded-md pr-9 pl-3 py-2 outline-none text-sm"
            />
          </div>
          <div className="mt-2 space-y-1">
            {userResults.map((u) => (
              <div key={u.id} className="flex items-center gap-2 bg-background border b-soft rounded-md p-2 text-sm" data-testid={`plus-user-${u.id}`}>
                <div className="flex-1 min-w-0">
                  <div className="font-bold truncate">{u.username}</div>
                  <div className="text-[10px] text-white/40 truncate">{u.email}</div>
                </div>
                {u.is_personal_plus && <span className="text-[10px] uppercase bg-gold-500 text-black px-1.5 py-0.5 rounded">Plus</span>}
                <button data-testid={`grant-user-${u.id}`} onClick={() => grantUser(u.id, "grant")} className="px-2 py-1 rounded bg-gold-500/15 text-gold-500 hover:bg-gold-500/25 text-xs">منح</button>
                <button data-testid={`revoke-user-${u.id}`} onClick={() => grantUser(u.id, "revoke")} className="px-2 py-1 rounded bg-destructive/10 text-destructive hover:bg-destructive/20 text-xs">إلغاء</button>
              </div>
            ))}
          </div>
        </div>

        <div>
          <div className="text-xs uppercase tracking-widest text-emerald-400 mb-2">Clan Plus لكلان</div>
          <div className="relative mb-2">
            <Search size={14} className="absolute right-3 top-1/2 -translate-y-1/2 text-white/30" />
            <input
              data-testid="plus-clan-search"
              value={clanQuery}
              onChange={(e) => searchClan(e.target.value)}
              placeholder="ابحث باسم الكلان أو ID..."
              className="w-full bg-surface border b-soft rounded-md pr-9 pl-3 py-2 outline-none text-sm"
            />
          </div>
          <div className="max-h-[260px] overflow-y-auto space-y-1">
            {clanResults.map((c) => (
              <div key={c.id} className="flex items-center gap-2 bg-background border b-soft rounded-md p-2 text-sm" data-testid={`plus-clan-${c.id}`}>
                <Shield size={14} className="text-emerald-400" />
                <div className="flex-1 min-w-0">
                  <div className="font-bold truncate">{c.name} <span className="text-xs text-emerald-400">[{c.tag}]</span></div>
                  <div className="text-[10px] text-white/40 truncate">ID: {c.id}</div>
                </div>
                {c.is_plus && <span className="text-[10px] uppercase bg-emerald-400 text-black px-1.5 py-0.5 rounded">Plus</span>}
                <button data-testid={`grant-clan-${c.id}`} onClick={() => grantClan(c.id, "grant")} className="px-2 py-1 rounded bg-emerald-500/15 text-emerald-400 hover:bg-emerald-500/25 text-xs">منح</button>
                <button data-testid={`revoke-clan-${c.id}`} onClick={() => grantClan(c.id, "revoke")} className="px-2 py-1 rounded bg-destructive/10 text-destructive hover:bg-destructive/20 text-xs">إلغاء</button>
              </div>
            ))}
            {clanResults.length === 0 && (
              <div className="text-xs text-white/40 py-3 text-center">لا توجد نتائج كلانات</div>
            )}
          </div>
        </div>
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
    api.get("/matches/live")
      .then((r) => {
        setLive(r.data || []);
        setDisputes((r.data || []).filter((m) => (m.maps || []).some((mp) => mp.disputed)));
      })
      .catch(() => {
        setLive([]);
        setDisputes([]);
      });
    api.get("/matches/history").then((r) => setHistory(r.data || [])).catch(() => setHistory([]));
    api.get("/clans").then((r) => setClans(r.data || [])).catch(() => setClans([]));
    api.get("/tournaments").then((r) => setTournaments(r.data || [])).catch(() => setTournaments([]));
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
      <LeaguesManager />
      <OwnerPlusGrants />
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
