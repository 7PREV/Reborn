import { useEffect, useState, useMemo, useCallback } from "react";
import { useParams, Link } from "react-router-dom";
import api, { formatApiErrorDetail } from "../api";
import { useAuth } from "../AuthContext";
import { Shield, UserPlus, Swords, LogOut, Trash2, Sparkles } from "lucide-react";
import { toast } from "sonner";
import ChallengeModal from "../components/clan/ChallengeModal";
import InviteModal from "../components/clan/InviteModal";
import MembersList from "../components/clan/MembersList";

function ClanHeader({ clan }) {
  const isPlusClan = clan.max_members === 12;
  const remainingToReward = 7 - (clan.member_ids?.length || 0);

  return (
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
            {isPlusClan && (
              <span className="text-gold-500 mr-2 inline-flex items-center gap-1">
                <Sparkles size={10} /> Plus
              </span>
            )}
          </div>
          {!clan.founder_reward_given && remainingToReward > 0 && (
            <div className="mt-3 inline-flex items-center gap-2 px-3 py-1.5 rounded bg-gold-500/10 border border-gold-500/30 text-xs text-gold-500">
              <Sparkles size={12} />
              <span>اكمل {remainingToReward} لاعبين بعد لتحصل على Plus مجاناً 7 أيام!</span>
            </div>
          )}
        </div>
        <div className="flex gap-6 text-center">
          <Stat label="نقاط" value={clan.points} highlight />
          <Stat label="فوز" value={clan.wins || 0} />
          <Stat label="خسارة" value={clan.losses || 0} />
        </div>
      </div>
    </div>
  );
}

function Stat({ label, value, highlight }) {
  return (
    <div>
      <div className={`text-2xl font-display font-black ${highlight ? "text-gold-500" : ""}`}>{value}</div>
      <div className="text-[10px] uppercase tracking-widest text-white/40">{label}</div>
    </div>
  );
}

function ActionBar({ canJoin, isFull, isStaff, isMember, isLeader, onJoin, onChallenge, onInvite, onLeave, onDelete }) {
  return (
    <div className="mt-6 flex gap-2 flex-wrap">
      {canJoin && !isFull && (
        <button data-testid="request-join-btn" onClick={onJoin} className="px-4 py-2 rounded-md bg-gold-500 text-black font-bold hover:bg-gold-400 flex items-center gap-2">
          <UserPlus size={16} /> طلب انضمام
        </button>
      )}
      {canJoin && isFull && (
        <div className="px-4 py-2 rounded-md bg-destructive/10 text-destructive text-sm">الكلان ممتلئ</div>
      )}
      {isStaff && (
        <>
          <button data-testid="challenge-btn" onClick={onChallenge} className="px-4 py-2 rounded-md bg-destructive text-white font-bold hover:bg-destructive/90 flex items-center gap-2">
            <Swords size={16} /> تحدي كلان آخر
          </button>
          {!isFull && (
            <button data-testid="invite-btn" onClick={onInvite} className="px-4 py-2 rounded-md border b-soft hover:bg-white/5 flex items-center gap-2">
              <UserPlus size={16} /> دعوة لاعب
            </button>
          )}
        </>
      )}
      {isMember && !isLeader && (
        <button onClick={onLeave} className="px-4 py-2 rounded-md border b-soft hover:bg-white/5 flex items-center gap-2 text-white/70">
          <LogOut size={16} /> مغادرة
        </button>
      )}
      {isLeader && (
        <button onClick={onDelete} className="px-4 py-2 rounded-md border border-destructive/30 text-destructive hover:bg-destructive/10 flex items-center gap-2">
          <Trash2 size={16} /> حذف الكلان
        </button>
      )}
    </div>
  );
}

function ChallengesList({ challenges, currentClanId, onAccept, onReject }) {
  if (!challenges || challenges.length === 0) return null;
  return (
    <section>
      <h2 className="font-display font-black text-2xl mb-4">تحديات المباريات ({challenges.length})</h2>
      <div className="bg-surface border b-soft rounded-lg divide-y divide-white/5">
        {challenges.map((c) => {
          const incoming = c.opponent_clan_id === currentClanId;
          return (
            <div key={c.id} className="p-4 flex items-center gap-3 flex-wrap" data-testid={`challenge-${c.id}`}>
              <div className="h-9 w-9 rounded-md bg-destructive/10 grid place-items-center text-destructive">
                <Swords size={16} />
              </div>
              <div className="flex-1 min-w-0">
                <div className="font-bold">
                  {incoming ? `تحدٍ وارد من ${c.challenger_name}` : `بانتظار رد ${c.opponent_name}`}
                </div>
                <div className="text-[10px] uppercase tracking-widest text-white/40">
                  [{incoming ? c.challenger_tag : c.opponent_tag}] • BO3 Call of Duty
                </div>
                {c.notes && <div className="text-xs text-white/50 mt-1">{c.notes}</div>}
              </div>
              {incoming ? (
                <>
                  <button data-testid={`ch-accept-${c.id}`} onClick={() => onAccept(c.id)} className="px-3 py-1.5 rounded bg-gold-500 text-black text-sm font-bold hover:bg-gold-400">قبول التحدي</button>
                  <button data-testid={`ch-reject-${c.id}`} onClick={() => onReject(c.id)} className="px-3 py-1.5 rounded border b-soft text-sm hover:bg-white/5">رفض</button>
                </>
              ) : (
                <span className="text-xs text-white/40">قيد الانتظار...</span>
              )}
            </div>
          );
        })}
      </div>
    </section>
  );
}

function RequestsList({ requests, onAccept, onReject }) {  if (requests.length === 0) return null;
  return (
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
            <button data-testid={`accept-${r.id}`} onClick={() => onAccept(r.id)} className="px-3 py-1.5 rounded bg-gold-500 text-black text-sm font-bold hover:bg-gold-400">قبول</button>
            <button data-testid={`reject-${r.id}`} onClick={() => onReject(r.id)} className="px-3 py-1.5 rounded border b-soft text-sm hover:bg-white/5">رفض</button>
          </div>
        ))}
      </div>
    </section>
  );
}

export default function ClanDetailPage() {
  const { id } = useParams();
  const { user, refresh } = useAuth();
  const [clan, setClan] = useState(null);
  const [requests, setRequests] = useState([]);
  const [allClans, setAllClans] = useState([]);
  const [challenges, setChallenges] = useState([]);
  const [showChallenge, setShowChallenge] = useState(false);
  const [showInvite, setShowInvite] = useState(false);
  const [inviteSearch, setInviteSearch] = useState("");
  const [inviteResults, setInviteResults] = useState([]);
  const [opponent, setOpponent] = useState("");

  const handleErr = (err) => toast.error(formatApiErrorDetail(err.response?.data?.detail));

  const load = useCallback(async () => {
    try {
      const { data } = await api.get(`/clans/${id}`);
      setClan(data);
      const isStaff = user && (
        user.role === "admin" ||
        user.id === data.leader_id ||
        data.vice_leader_ids?.includes(user.id)
      );
      if (isStaff) {
        try {
          const r = await api.get(`/clans/${id}/requests`);
          setRequests(r.data);
        } catch {
          // 403 means not staff anymore; benign
        }
        try {
          const ch = await api.get(`/clans/${id}/challenges`);
          setChallenges(ch.data);
        } catch {
          // benign
        }
      }
    } catch (err) {
      handleErr(err);
    }
  }, [id, user]);

  useEffect(() => {
    load();
    api.get("/clans").then((r) => setAllClans(r.data)).catch(() => {});
  }, [load]);

  // Roles / states derived from clan + user
  const flags = useMemo(() => {
    if (!clan) return {};
    const isLeader = user?.id === clan.leader_id;
    const isViceLeader = clan.vice_leader_ids?.includes(user?.id);
    const isStaff = isLeader || isViceLeader || user?.role === "admin";
    const isMember = clan.member_ids?.includes(user?.id);
    const canJoin = !!user && !user.clan_id && !isMember;
    const isFull = (clan.member_ids?.length || 0) >= (clan.max_members || 7);
    return { isLeader, isViceLeader, isStaff, isMember, canJoin, isFull };
  }, [clan, user]);

  // Filtered opponents list memo
  const availableOpponents = useMemo(
    () => allClans.filter((c) => clan && c.id !== clan.id),
    [allClans, clan?.id]
  );

  if (!clan) return <div className="text-white/40">جارٍ التحميل...</div>;

  const join = async () => {
    try { await api.post(`/clans/${id}/join-request`); toast.success("تم إرسال طلب الانضمام"); }
    catch (err) { handleErr(err); }
  };

  const accept = async (rid) => {
    try {
      const { data } = await api.post(`/clans/${id}/requests/${rid}`, { action: "accept" });
      if (data?.reward_granted) {
        toast.success("🎁 مبروك! كلانك امتلأ، حصلت على Plus مجاناً لمدة 7 أيام!", { duration: 6000 });
        await refresh();
      } else {
        toast.success("تم القبول");
      }
      load();
    } catch (err) { handleErr(err); }
  };

  const reject = async (rid) => {
    try {
      await api.post(`/clans/${id}/requests/${rid}`, { action: "reject" });
      toast.success("تم الرفض");
      load();
    } catch (err) { handleErr(err); }
  };

  const kick = async (mid) => {
    // eslint-disable-next-line no-alert
    if (!confirm("طرد هذا اللاعب؟")) return;
    await api.post(`/clans/${id}/kick/${mid}`);
    toast.success("تم الطرد");
    load();
  };

  const promote = async (mid) => {
    try { await api.post(`/clans/${id}/promote/${mid}`); load(); }
    catch (err) { handleErr(err); }
  };

  const leave = async () => {
    // eslint-disable-next-line no-alert
    if (!confirm("مغادرة الكلان؟")) return;
    await api.post(`/clans/${id}/leave`);
    await refresh();
    toast.success("غادرت الكلان");
    load();
  };

  const delClan = async () => {
    // eslint-disable-next-line no-alert
    if (!confirm("حذف الكلان نهائياً؟")) return;
    await api.delete(`/clans/${id}`);
    await refresh();
    window.location.href = "/clans";
  };

  const challenge = async (e) => {
    e.preventDefault();
    if (!opponent) return toast.error("اختر خصماً");
    if (!user?.clan_id) return toast.error("يجب أن تكون في كلان لإرسال تحدٍ");
    try {
      await api.post(`/clans/${user.clan_id}/challenge`, { opponent_clan_id: opponent });
      toast.success("تم إرسال طلب التحدي. ينتظر قبول الخصم.");
      setShowChallenge(false);
      setOpponent("");
      load();
    } catch (err) { handleErr(err); }
  };

  const respondChallenge = async (chId, action) => {
    try {
      const { data } = await api.post(`/challenges/${chId}`, { action });
      if (action === "accept" && data?.match?.id) {
        toast.success("تم قبول التحدي. بدأت المباراة!");
        window.location.href = `/matches/${data.match.id}`;
      } else {
        toast.success(action === "accept" ? "تم القبول" : "تم رفض التحدي");
        load();
      }
    } catch (err) { handleErr(err); }
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
    } catch (err) { handleErr(err); }
  };

  return (
    <div className="space-y-8">
      <ClanHeader clan={clan} />
      <ActionBar
        canJoin={flags.canJoin}
        isFull={flags.isFull}
        isStaff={flags.isStaff}
        isMember={flags.isMember}
        isLeader={flags.isLeader}
        onJoin={join}
        onChallenge={() => setShowChallenge(true)}
        onInvite={() => setShowInvite(true)}
        onLeave={leave}
        onDelete={delClan}
      />

      <section>
        <h2 className="font-display font-black text-2xl mb-4">
          الأعضاء ({clan.members?.length || 0}/{clan.max_members || 7})
        </h2>
        <MembersList
          members={clan.members || []}
          leaderId={clan.leader_id}
          viceLeaderIds={clan.vice_leader_ids || []}
          canManage={flags.isLeader || user?.role === "admin"}
          onPromote={promote}
          onKick={kick}
        />
        {flags.isLeader && (
          <div className="mt-3 text-xs text-white/40">
            النواب: {clan.vice_leader_ids?.length || 0} / {clan.max_vices || 1}
            {clan.max_vices === 1 && (
              <Link to="/me" className="text-gold-500 mr-2 hover:underline">ترقى لـ Plus لزيادة الحد</Link>
            )}
          </div>
        )}
      </section>

      {flags.isStaff && <RequestsList requests={requests} onAccept={accept} onReject={reject} />}
      {flags.isStaff && (
        <ChallengesList
          challenges={challenges}
          currentClanId={clan.id}
          onAccept={(cid) => respondChallenge(cid, "accept")}
          onReject={(cid) => respondChallenge(cid, "reject")}
        />
      )}

      {showChallenge && (
        <ChallengeModal
          clan={clan}
          allClans={availableOpponents}
          opponent={opponent}
          onOpponentChange={setOpponent}
          onClose={() => setShowChallenge(false)}
          onSubmit={challenge}
        />
      )}

      {showInvite && (
        <InviteModal
          search={inviteSearch}
          results={inviteResults}
          onSearch={searchInvite}
          onInvite={sendInvite}
          onClose={() => setShowInvite(false)}
        />
      )}
    </div>
  );
}
