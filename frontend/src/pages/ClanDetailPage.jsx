import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import api, { formatApiErrorDetail } from "../api";
import { useAuth } from "../AuthContext";
import { Shield, Crown, Star, UserMinus, UserPlus, Swords, LogOut, Trash2, Sparkles } from "lucide-react";
import { toast } from "sonner";

export default function ClanDetailPage() {
  const { id } = useParams();
  const { user, refresh } = useAuth();
  const [clan, setClan] = useState(null);
  const [requests, setRequests] = useState([]);
  const [allClans, setAllClans] = useState([]);
  const [showChallenge, setShowChallenge] = useState(false);
  const [showInvite, setShowInvite] = useState(false);
  const [inviteSearch, setInviteSearch] = useState("");
  const [inviteResults, setInviteResults] = useState([]);
  const [opponent, setOpponent] = useState("");

  const load = async () => {
    const { data } = await api.get(`/clans/${id}`);
    setClan(data);
    if (user && (user.role === "admin" || user.id === data.leader_id || data.vice_leader_ids?.includes(user.id))) {
      try {
        const r = await api.get(`/clans/${id}/requests`);
        setRequests(r.data);
      } catch {/* ignore */}
    }
  };

  useEffect(() => {
    load();
    api.get("/clans").then((r) => setAllClans(r.data));
  }, [id, user?.id]);

  if (!clan) return <div className="text-white/40">جارٍ التحميل...</div>;

  const isLeader = user?.id === clan.leader_id;
  const isStaff = isLeader || clan.vice_leader_ids?.includes(user?.id) || user?.role === "admin";
  const isMember = clan.member_ids?.includes(user?.id);
  const canJoin = user && !user.clan_id && !isMember;
  const isFull = clan.member_ids?.length >= (clan.max_members || 7);

  const join = async () => {
    try {
      await api.post(`/clans/${id}/join-request`);
      toast.success("تم إرسال طلب الانضمام");
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail));
    }
  };

  const handleReq = async (rid, action) => {
    try {
      const { data } = await api.post(`/clans/${id}/requests/${rid}`, { action });
      if (data?.reward_granted) {
        toast.success("🎁 مبروك! كلانك امتلأ، حصلت على Plus مجاناً لمدة 7 أيام!", { duration: 6000 });
        await refresh();
      } else {
        toast.success(action === "accept" ? "تم القبول" : "تم الرفض");
      }
      load();
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail));
    }
  };

  const kick = async (mid) => {
    if (!confirm("طرد هذا اللاعب؟")) return;
    await api.post(`/clans/${id}/kick/${mid}`);
    toast.success("تم الطرد");
    load();
  };

  const promote = async (mid) => {
    try {
      await api.post(`/clans/${id}/promote/${mid}`);
      load();
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail));
    }
  };

  const leave = async () => {
    if (!confirm("مغادرة الكلان؟")) return;
    await api.post(`/clans/${id}/leave`);
    await refresh();
    toast.success("غادرت الكلان");
    load();
  };

  const delClan = async () => {
    if (!confirm("حذف الكلان نهائياً؟")) return;
    await api.delete(`/clans/${id}`);
    await refresh();
    window.location.href = "/clans";
  };

  const challenge = async (e) => {
    e.preventDefault();
    if (!opponent) return toast.error("اختر خصماً");
    try {
      const { data } = await api.post("/matches", {
        clan_a_id: clan.id,
        clan_b_id: opponent,
      });
      toast.success("تم إنشاء التحدي");
      window.location.href = `/matches/${data.id}`;
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail));
    }
  };

  const searchInvite = async (val) => {
    setInviteSearch(val);
    if (!val) return setInviteResults([]);
    const { data } = await api.get("/users/search", { params: { q: val } });
    setInviteResults(data.filter((u) => !u.clan_id && u.role !== "admin"));
  };

  const sendInvite = async (uid) => {
    try {
      await api.post(`/clans/${id}/invite`, { user_id: uid });
      toast.success("تم إرسال الدعوة");
      setInviteResults(inviteResults.filter((u) => u.id !== uid));
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail));
    }
  };

  return (
    <div className="space-y-8">
      <div className="bg-surface border b-soft rounded-xl p-6 md:p-8 relative overflow-hidden">
        <div className="flex items-start gap-5 flex-wrap">
          <div className="h-20 w-20 rounded-lg bg-gold-500/10 text-gold-500 grid place-items-center">
            <Shield size={40} />
          </div>
          <div className="flex-1 min-w-0">
            <div className="text-xs uppercase tracking-widest text-gold-500">[{clan.tag}]</div>
            <h1 className="font-display font-black text-3xl md:text-4xl">{clan.name}</h1>
            <p className="text-white/50 mt-2 max-w-2xl">{clan.description || "—"}</p>
            <div className="mt-2 text-xs text-white/40">
              {clan.member_ids?.length || 0} / {clan.max_members || 7} لاعب
              {clan.max_members === 12 && <span className="text-gold-500 mr-2 inline-flex items-center gap-1"><Sparkles size={10} /> Plus</span>}
            </div>
            {!clan.founder_reward_given && (clan.member_ids?.length || 0) < 7 && (
              <div className="mt-3 inline-flex items-center gap-2 px-3 py-1.5 rounded bg-gold-500/10 border border-gold-500/30 text-xs text-gold-500">
                <Sparkles size={12} />
                <span>اكمل {7 - (clan.member_ids?.length || 0)} لاعبين بعد لتحصل على Plus مجاناً 7 أيام!</span>
              </div>
            )}
          </div>
          <div className="flex gap-6 text-center">
            <div>
              <div className="text-2xl font-display font-black text-gold-500">{clan.points}</div>
              <div className="text-[10px] uppercase tracking-widest text-white/40">نقاط</div>
            </div>
            <div>
              <div className="text-2xl font-display font-black">{clan.wins || 0}</div>
              <div className="text-[10px] uppercase tracking-widest text-white/40">فوز</div>
            </div>
            <div>
              <div className="text-2xl font-display font-black">{clan.losses || 0}</div>
              <div className="text-[10px] uppercase tracking-widest text-white/40">خسارة</div>
            </div>
          </div>
        </div>

        <div className="mt-6 flex gap-2 flex-wrap">
          {canJoin && !isFull && (
            <button data-testid="request-join-btn" onClick={join} className="px-4 py-2 rounded-md bg-gold-500 text-black font-bold hover:bg-gold-400 flex items-center gap-2">
              <UserPlus size={16} /> طلب انضمام
            </button>
          )}
          {canJoin && isFull && (
            <div className="px-4 py-2 rounded-md bg-destructive/10 text-destructive text-sm">الكلان ممتلئ</div>
          )}
          {isStaff && (
            <>
              <button data-testid="challenge-btn" onClick={() => setShowChallenge(true)} className="px-4 py-2 rounded-md bg-destructive text-white font-bold hover:bg-destructive/90 flex items-center gap-2">
                <Swords size={16} /> تحدي كلان آخر
              </button>
              {!isFull && (
                <button data-testid="invite-btn" onClick={() => setShowInvite(true)} className="px-4 py-2 rounded-md border b-soft hover:bg-white/5 flex items-center gap-2">
                  <UserPlus size={16} /> دعوة لاعب
                </button>
              )}
            </>
          )}
          {isMember && !isLeader && (
            <button onClick={leave} className="px-4 py-2 rounded-md border b-soft hover:bg-white/5 flex items-center gap-2 text-white/70">
              <LogOut size={16} /> مغادرة
            </button>
          )}
          {isLeader && (
            <button onClick={delClan} className="px-4 py-2 rounded-md border border-destructive/30 text-destructive hover:bg-destructive/10 flex items-center gap-2">
              <Trash2 size={16} /> حذف الكلان
            </button>
          )}
        </div>
      </div>

      <section>
        <h2 className="font-display font-black text-2xl mb-4">الأعضاء ({clan.members?.length || 0}/{clan.max_members || 7})</h2>
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {clan.members?.map((m) => {
            const isClanLeader = m.id === clan.leader_id;
            const isVice = clan.vice_leader_ids?.includes(m.id);
            return (
              <div key={m.id} data-testid={`member-${m.id}`} className="bg-surface border b-soft rounded-lg p-4 flex items-center gap-3">
                <div className="h-10 w-10 rounded-md bg-white/5 grid place-items-center font-display text-gold-500">
                  {m.username[0].toUpperCase()}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="font-bold truncate flex items-center gap-1">
                    {m.username}
                    {isClanLeader && <Crown size={14} className="text-gold-500" />}
                    {isVice && <Star size={14} className="text-gold-500/70" />}
                  </div>
                  <div className="text-[10px] uppercase tracking-widest text-white/40">
                    {isClanLeader ? "القائد" : isVice ? "نائب القائد" : "لاعب"}
                  </div>
                </div>
                {(isLeader || user?.role === "admin") && !isClanLeader && (
                  <div className="flex gap-1">
                    <button onClick={() => promote(m.id)} title={isVice ? "إزالة نائب" : "ترقية نائب"} className="p-1.5 rounded hover:bg-white/5 text-gold-500">
                      <Star size={14} />
                    </button>
                    <button onClick={() => kick(m.id)} title="طرد" className="p-1.5 rounded hover:bg-destructive/10 text-destructive">
                      <UserMinus size={14} />
                    </button>
                  </div>
                )}
              </div>
            );
          })}
        </div>
        {isLeader && (
          <div className="mt-3 text-xs text-white/40">
            النواب: {clan.vice_leader_ids?.length || 0} / {clan.max_vices || 1}
            {clan.max_vices === 1 && (
              <Link to="/me" className="text-gold-500 mr-2 hover:underline">ترقى لـ Plus لزيادة الحد</Link>
            )}
          </div>
        )}
      </section>

      {isStaff && requests.length > 0 && (
        <section>
          <h2 className="font-display font-black text-2xl mb-4">طلبات الانضمام ({requests.length})</h2>
          <div className="bg-surface border b-soft rounded-lg divide-y divide-white/5">
            {requests.map((r) => (
              <div key={r.id} className="p-4 flex items-center gap-3" data-testid={`request-${r.id}`}>
                <div className="h-9 w-9 rounded-md bg-white/5 grid place-items-center font-display text-gold-500">
                  {r.username[0].toUpperCase()}
                </div>
                <div className="flex-1">
                  <div className="font-bold">{r.username}</div>
                  <div className="text-[10px] uppercase tracking-widest text-white/40">{r.type === "invite" ? "دعوة" : "طلب"}</div>
                </div>
                <button data-testid={`accept-${r.id}`} onClick={() => handleReq(r.id, "accept")} className="px-3 py-1.5 rounded bg-gold-500 text-black text-sm font-bold hover:bg-gold-400">قبول</button>
                <button data-testid={`reject-${r.id}`} onClick={() => handleReq(r.id, "reject")} className="px-3 py-1.5 rounded border b-soft text-sm hover:bg-white/5">رفض</button>
              </div>
            ))}
          </div>
        </section>
      )}

      {showChallenge && (
        <div className="fixed inset-0 z-50 grid place-items-center bg-black/70 backdrop-blur-xl p-4">
          <form onSubmit={challenge} className="bg-surface border b-soft rounded-xl p-6 w-full max-w-md space-y-4" data-testid="challenge-form">
            <h2 className="font-display font-black text-2xl">تحدي كلان (Call of Duty • BO3)</h2>
            <select value={opponent} onChange={(e) => setOpponent(e.target.value)} required data-testid="opponent-select" className="w-full bg-background border b-soft rounded-md px-4 py-3 outline-none">
              <option value="">— اختر الكلان الخصم —</option>
              {allClans.filter((c) => c.id !== clan.id).map((c) => (
                <option key={c.id} value={c.id}>{c.name} [{c.tag}]</option>
              ))}
            </select>
            <p className="text-xs text-white/50">المباراة تتكون من 3 خرائط، أول كلان يفوز بخريطتين يربح المباراة.</p>
            <div className="flex gap-2 justify-end">
              <button type="button" onClick={() => setShowChallenge(false)} className="px-4 py-2 rounded-md hover:bg-white/5">إلغاء</button>
              <button data-testid="submit-challenge" type="submit" className="px-5 py-2 rounded-md bg-destructive text-white font-bold hover:bg-destructive/90">إطلاق التحدي</button>
            </div>
          </form>
        </div>
      )}

      {showInvite && (
        <div className="fixed inset-0 z-50 grid place-items-center bg-black/70 backdrop-blur-xl p-4">
          <div className="bg-surface border b-soft rounded-xl p-6 w-full max-w-md space-y-4">
            <h2 className="font-display font-black text-2xl">دعوة لاعب</h2>
            <input value={inviteSearch} onChange={(e) => searchInvite(e.target.value)} placeholder="ابحث باسم المستخدم..." data-testid="invite-search" className="w-full bg-background border b-soft rounded-md px-4 py-3 outline-none" />
            <div className="max-h-64 overflow-y-auto space-y-2">
              {inviteResults.map((u) => (
                <div key={u.id} className="flex items-center gap-3 p-2 rounded hover:bg-white/5">
                  <div className="h-8 w-8 rounded bg-white/5 grid place-items-center text-gold-500">{u.username[0].toUpperCase()}</div>
                  <div className="flex-1">{u.username}</div>
                  <button data-testid={`invite-user-${u.id}`} onClick={() => sendInvite(u.id)} className="px-3 py-1 rounded bg-gold-500 text-black text-sm font-bold">دعوة</button>
                </div>
              ))}
              {inviteSearch && inviteResults.length === 0 && <div className="text-center text-white/40 py-4 text-sm">لا توجد نتائج</div>}
            </div>
            <div className="text-right">
              <button onClick={() => setShowInvite(false)} className="px-4 py-2 rounded-md hover:bg-white/5">إغلاق</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
