import { useEffect, useState, useMemo, useCallback } from "react";
import { useParams, Link, useLocation } from "react-router-dom";
import api, { formatApiErrorDetail } from "../api";
import { useAuth } from "../AuthContext";
import { Shield, UserPlus, Swords, LogOut, Trash2, Sparkles, Power, Trophy, UserCheck, Crown, Image as ImageIcon } from "lucide-react";
import { toast } from "sonner";
import ChallengeModal from "../components/clan/ChallengeModal";
import InviteModal from "../components/clan/InviteModal";
import MembersList from "../components/clan/MembersList";
import ClanLogo from "../components/clan/ClanLogo";

function formatSuspensionRemaining(seconds) {
  const total = Math.max(0, Number(seconds || 0));
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  if (h <= 0) return `${Math.max(1, m)} دقيقة`;
  if (m <= 0) return `${h} ساعة`;
  return `${h} ساعة و${m} دقيقة`;
}

function ClanHeader({ clan }) {
  const isPlusClan = clan.max_members === 12;
  const remainingToReward = 7 - (clan.member_ids?.length || 0);

  return (
    <section className="bg-surface border b-soft rounded-2xl p-6 md:p-8 relative overflow-hidden">
      <div className="absolute inset-0 pointer-events-none bg-gradient-to-b from-gold-500/5 via-transparent to-transparent" />
      <div className="relative text-center">
        <div className="inline-flex items-center gap-2 text-xs uppercase tracking-[0.2em] text-gold-500">
          <ClanLogo
            clan={clan}
            className="h-[13px] w-[13px] rounded-sm overflow-hidden bg-gold-500/10 grid place-items-center"
            fallbackIconSize={13}
            fallbackIconClassName="text-gold-500"
          />
          [{clan.tag}]
          {isPlusClan && (
            <span className="inline-flex items-center gap-1 rounded-full border border-gold-500/30 bg-gold-500/10 px-2 py-0.5 tracking-normal normal-case">
              <Sparkles size={10} /> Plus
            </span>
          )}
        </div>

        <h1 className="mt-3 font-display font-black text-3xl md:text-5xl text-gold-500 leading-tight">
          {clan.name}
        </h1>

        <p className="mt-3 text-white/55 max-w-3xl mx-auto text-sm md:text-base">
          {clan.description || "—"}
        </p>

        <div className="mt-6 grid grid-cols-3 gap-3 md:gap-4 max-w-xl mx-auto">
          <Stat label="Points" value={clan.points} highlight />
          <Stat label="Wins" value={clan.wins || 0} />
          <Stat label="Losses" value={clan.losses || 0} />
        </div>

        <div className="mt-3 text-xs text-white/40">
          {clan.member_ids?.length || 0} / {clan.max_members || 7} لاعب
        </div>

        {!clan.founder_reward_given && remainingToReward > 0 && (
          <div className="mt-4 inline-flex items-center gap-2 px-3 py-1.5 rounded-lg bg-gold-500/10 border border-gold-500/30 text-xs text-gold-500">
            <Sparkles size={12} />
            <span>اكمل {remainingToReward} لاعبين بعد لتحصل على Plus مجاناً 7 أيام!</span>
          </div>
        )}

        {clan.suspension_active && (
          <div className="mt-4 rounded-lg bg-destructive/10 border border-destructive/30 px-3 py-2 text-xs text-destructive text-right max-w-2xl mx-auto">
            <div className="font-bold">الكلان موقوف مؤقتاً عن التسجيل في البطولات والدوريات</div>
            <div className="text-white/80 mt-1">
              المتبقي: {formatSuspensionRemaining(clan.suspension_remaining_seconds)}
              {clan.suspension_reason ? ` • السبب: ${clan.suspension_reason}` : ""}
            </div>
          </div>
        )}
      </div>
    </section>
  );
}

function Stat({ label, value, highlight }) {
  return (
    <div className="rounded-xl border border-white/10 bg-background/50 px-3 py-3">
      <div className={`text-2xl font-display font-black ${highlight ? "text-gold-500" : "text-white"}`}>{value}</div>
      <div className="text-[10px] uppercase tracking-widest text-white/40 mt-1">{label}</div>
    </div>
  );
}

function ActionBar({ canJoin, isFull, isStaff, isMember, isLeader, canSearchChallenge, isPlusClan, clanId, onJoin, onChallenge, onInvite, onLeave, onDelete, onArchive, leaving = false }) {
  return (
    <div className="flex gap-2 flex-wrap items-center">
      {canJoin && !isFull && (
        <button data-testid="request-join-btn" onClick={onJoin} className="px-4 py-2 rounded-lg bg-gold-500 text-black font-bold hover:bg-gold-400 flex items-center gap-2 text-sm">
          <UserPlus size={15} /> طلب انضمام
        </button>
      )}
      {canJoin && isFull && (
        <div className="px-4 py-2 rounded-lg bg-destructive/10 text-destructive text-sm border border-destructive/20">الكلان ممتلئ</div>
      )}
      {isStaff && (
        <>
          <button
            data-testid="challenge-btn"
            onClick={onChallenge}
            disabled={!canSearchChallenge}
            className="px-4 py-2 rounded-lg bg-destructive text-white font-bold hover:bg-destructive/90 disabled:opacity-40 disabled:cursor-not-allowed flex items-center gap-2 text-sm"
          >
            <Swords size={15} /> البحث عن تحدي
          </button>
          {!isFull && (
            <button data-testid="invite-btn" onClick={onInvite} className="px-4 py-2 rounded-lg border b-soft hover:bg-white/5 flex items-center gap-2 text-sm">
              <UserPlus size={15} /> دعوة لاعب
            </button>
          )}
        </>
      )}
      {isMember && !isLeader && (
        <button
          onClick={onLeave}
          disabled={leaving}
          data-testid="leave-clan-btn"
          className="px-4 py-2 rounded-lg border border-red-500/40 bg-gradient-to-b from-red-600/30 to-red-700/20 text-red-200 hover:text-white hover:border-red-400 hover:from-red-600/45 hover:to-red-700/35 active:scale-[0.98] transition-all duration-200 shadow-[0_0_0_rgba(239,68,68,0)] hover:shadow-[0_0_18px_rgba(239,68,68,0.35)] disabled:opacity-60 disabled:cursor-not-allowed flex items-center gap-2 text-sm font-semibold"
        >
          <LogOut size={15} className={leaving ? "animate-pulse" : ""} /> {leaving ? "جاري المغادرة..." : "مغادرة"}
        </button>
      )}
      {isLeader && (
        <>
          <button data-testid="archive-clan-btn" onClick={onArchive} className="px-4 py-2 rounded-lg border border-white/20 text-white/60 hover:bg-white/5 flex items-center gap-2 text-sm">
            <Power size={15} /> أرشفة الكلان
          </button>
          <button onClick={onDelete} className="px-4 py-2 rounded-lg border border-destructive/30 text-destructive hover:bg-destructive/10 flex items-center gap-2 text-sm">
            <Trash2 size={15} /> حذف الكلان
          </button>
        </>
      )}
      {isStaff && !canSearchChallenge && (
        <div className="w-full text-xs text-amber-400/80 mt-1 pr-1">
          ⚠ يتطلب التحضير 6 لاعبين على الأقل مع حضور القائد لتفعيل البحث عن تحدي
        </div>
      )}
    </div>
  );
}

function LeaguesJoin({ clanId, clanLeagueIds, leagues, reload, clanMembersCount }) {
  const canParticipate = (clanMembersCount || 0) >= 6;
  const join = async (lid) => {
    if (!canParticipate) {
      return toast.error("لا يمكنك المشاركة في الدوري إلا بعد وصول عدد أعضاء الكلان إلى 6 لاعبين على الأقل.");
    }
    try {
      await api.post(`/leagues/${lid}/join`);
      toast.success("تم التسجيل في الدوري");
      reload();
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail) || "تعذّر التسجيل في الدوري");
    }
  };
  if (!leagues || leagues.length === 0) return null;
  return (
    <section data-testid="leagues-join" className="bg-surface border b-soft rounded-xl p-6">
      <h2 className="font-display font-black text-2xl mb-3 flex items-center gap-2">
        <Trophy className="text-gold-500" /> الدوريات المتاحة
      </h2>
      {!canParticipate && (
        <div className="mb-3 text-xs text-destructive">
          لا يمكنك المشاركة في الدوري إلا بعد وصول عدد أعضاء الكلان إلى 6 لاعبين على الأقل.
        </div>
      )}
      <div className="grid sm:grid-cols-2 gap-3">
        {leagues.map((lg) => {
          const isJoined = clanLeagueIds.includes(lg.id);
          return (
            <div key={lg.id} className="bg-background border b-soft rounded-lg p-3 flex items-center gap-3" data-testid={`league-${lg.id}`}>
              <Trophy size={16} className="text-gold-500" />
              <div className="flex-1 min-w-0">
                <div className="font-display font-bold text-sm truncate">{lg.name}</div>
                <div className="text-[10px] text-white/40">{lg.game} • {lg.is_custom ? "مخصص" : "شهري"}</div>
              </div>
              {isJoined ? (
                <span className="text-[10px] uppercase bg-emerald-500/10 text-emerald-400 px-2 py-1 rounded">مسجّل</span>
              ) : (
                <button
                  data-testid={`join-league-${lg.id}`}
                  onClick={() => join(lg.id)}
                  disabled={!canParticipate}
                  title={!canParticipate ? "يتطلب 6 لاعبين على الأقل في الكلان" : ""}
                  className="px-2 py-1 rounded text-xs bg-gold-500 text-black font-bold hover:bg-gold-400 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  سجّل الكلان
                </button>
              )}
            </div>
          );
        })}
      </div>
    </section>
  );
}

function TrophyRoom({ trophies }) {
  if (!trophies || trophies.length === 0) {
    return (
      <section data-testid="trophy-room-empty" className="bg-surface border b-soft rounded-2xl overflow-hidden">
        <div className="px-6 py-4 border-b border-white/10 flex items-center gap-2 bg-gold-500/5">
          <Trophy size={18} className="text-gold-500" />
          <h2 className="font-display font-black text-xl">غرفة الكؤوس</h2>
        </div>
        <div className="px-6 py-8 text-center">
          <Trophy size={32} className="mx-auto mb-3 text-white/15" />
          <p className="text-white/40 text-sm">لم يحقق هذا الكلان بطولات بعد. كن أول من يرفع الكأس!</p>
        </div>
      </section>
    );
  }
  return (
    <section data-testid="trophy-room" className="bg-surface border b-soft rounded-2xl overflow-hidden">
      <div className="px-6 py-4 border-b border-white/10 flex items-center gap-2 bg-gold-500/5">
        <Trophy size={18} className="text-gold-500" />
        <h2 className="font-display font-black text-xl">غرفة الكؤوس</h2>
        <span className="mr-auto text-xs text-white/40 font-mono">{trophies.length} كأس</span>
      </div>
      <div className="p-6 grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {trophies.map((t) => (
          <div
            key={t.id}
            data-testid={`trophy-${t.id}`}
            className="bg-gold-500/5 border border-gold-500/25 rounded-xl p-4 flex items-center gap-3"
          >
            <div className="h-11 w-11 rounded-lg bg-gold-500/15 grid place-items-center text-gold-500 flex-shrink-0">
              <Trophy size={22} />
            </div>
            <div className="flex-1 min-w-0">
              <div className="font-display font-black text-sm text-gold-500 truncate">{t.label}</div>
              <div className="text-[10px] text-white/40 mt-0.5">
                {t.kind === "league" ? "بطولة شهرية" : "بطولة"} • {new Date(t.awarded_at).toLocaleDateString("ar")}
              </div>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

function AttendancePanel({ clan, attendance, canInteract, isCheckedIn, onCheckIn, onCheckOut, highlightCheckIn }) {
  const summary = attendance?.summary || clan?.attendance || {};
  const checked = attendance?.checked_in || [];
  const count = summary.count || 0;
  const required = summary.required || 6;
  const green = !!summary.is_green;

  return (
    <section data-testid="attendance-panel" className="bg-surface border b-soft rounded-2xl overflow-hidden">
      {/* Card header */}
      <div className={`px-6 py-4 border-b border-white/10 flex items-center justify-between gap-3 flex-wrap ${green ? "bg-emerald-500/5" : ""}`}>
        <h2 className="font-display font-black text-xl flex items-center gap-2">
          <UserCheck size={18} className={green ? "text-emerald-400" : "text-white/50"} />
          تحضير الكلان
        </h2>
        <div className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-sm font-bold ${
          green ? "bg-emerald-500/15 text-emerald-400 ring-1 ring-emerald-500/30" : "bg-white/10 text-white/60"
        }`}>
          <span className={`h-2 w-2 rounded-full flex-shrink-0 ${green ? "bg-emerald-400" : "bg-white/30"}`} />
          {count} / {required}
        </div>
      </div>

      <div className="px-6 py-5 space-y-4">
        <p className="text-xs text-white/45">القائمة مرئية للجميع. يمكن لأعضاء الكلان فقط تعديل التحضير، والتحضير المتأخر مسموح دائماً.</p>

        {/* Check-in / check-out button */}
        {canInteract ? (
          isCheckedIn ? (
            <button onClick={onCheckOut} className={`px-5 py-2.5 rounded-lg border b-soft hover:bg-white/5 text-sm font-medium ${highlightCheckIn ? "ring-2 ring-emerald-400/60 shadow-[0_0_18px_rgba(16,185,129,0.45)]" : ""}`}>
              إلغاء التحضير
            </button>
          ) : (
            <button onClick={onCheckIn} className={`px-5 py-2.5 rounded-lg bg-emerald-500 text-black font-bold hover:bg-emerald-400 text-sm ${highlightCheckIn ? "ring-2 ring-emerald-300 shadow-[0_0_22px_rgba(16,185,129,0.55)] animate-pulse" : ""}`}>
              تحضير الآن
            </button>
          )
        ) : (
          <div className="text-xs text-white/35 italic">التفاعل متاح لأعضاء الكلان فقط.</div>
        )}

        {/* Checked-in player chips */}
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
          {checked.length === 0 ? (
            <div className="col-span-full text-xs text-white/35 py-2">لا يوجد محضرون حالياً.</div>
          ) : checked.map((p) => (
            <div key={p.id} className="rounded-lg border border-emerald-500/20 bg-emerald-500/5 px-3 py-2 flex items-center gap-2">
              <span className="h-2 w-2 rounded-full bg-emerald-400 flex-shrink-0" />
              <div className="min-w-0">
                <div className="font-semibold text-white truncate text-xs">{p.username}</div>
                <div className="text-[10px] text-white/40 truncate">{p.act || "—"}</div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function TopMvpWidget({ rows }) {
  const rankStyle = [
    { bg: "bg-gold-500/10 border-gold-500/25", num: "text-gold-500" },
    { bg: "bg-white/5 border-white/10",        num: "text-white/50" },
    { bg: "bg-amber-700/10 border-amber-700/20", num: "text-amber-600" },
  ];

  return (
    <section data-testid="top-mvp-widget" className="bg-surface border b-soft rounded-2xl overflow-hidden">
      {/* Card header */}
      <div className="px-6 py-4 border-b border-white/10 flex items-center gap-2 bg-gold-500/5">
        <Crown size={18} className="text-gold-500" />
        <h2 className="font-display font-black text-xl">Top MVP Players</h2>
        {rows?.length > 0 && (
          <span className="mr-auto text-xs text-white/40 font-mono">{rows.length} لاعب</span>
        )}
      </div>

      <div className="px-6 py-5">
        {rows?.length ? (
          <div className="space-y-2">
            {rows.map((r, idx) => {
              const s = rankStyle[idx] || { bg: "bg-background/40 border-white/10", num: "text-white/30" };
              return (
                <div key={r.id} className={`rounded-xl border px-4 py-3 flex items-center gap-3 ${s.bg}`}>
                  <div className={`text-sm font-display font-black w-6 text-center ${s.num}`}>#{idx + 1}</div>
                  <div className="flex-1 min-w-0">
                    <div className="font-bold text-sm truncate">{r.username}</div>
                    <div className="text-[11px] text-white/45 mt-0.5">
                      <span className="text-gold-500">★ {r.mvp_count} MVP</span>
                      <span className="mx-1.5 text-white/20">•</span>
                      <span>{r.attendances || 0} حضور</span>
                    </div>
                  </div>
                  {idx === 0 && <Crown size={14} className="text-gold-500 flex-shrink-0" />}
                </div>
              );
            })}
          </div>
        ) : (
          <div className="py-6 text-center text-sm text-white/35">
            <Crown size={28} className="mx-auto mb-2 text-white/15" />
            لا توجد نتائج MVP بعد.
          </div>
        )}
      </div>
    </section>
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
  const location = useLocation();
  const { user, refresh } = useAuth();
  const [clan, setClan] = useState(null);
  const [requests, setRequests] = useState([]);
  const [allClans, setAllClans] = useState([]);
  const [challenges, setChallenges] = useState([]);
  const [leagues, setLeagues] = useState([]);
  const [attendance, setAttendance] = useState(null);
  const [myClan, setMyClan] = useState(null);
  const [myClanAttendance, setMyClanAttendance] = useState(null);
  const [mvpRows, setMvpRows] = useState([]);
  const [showChallenge, setShowChallenge] = useState(false);
  const [showInvite, setShowInvite] = useState(false);
  const [inviteSearch, setInviteSearch] = useState("");
  const [inviteResults, setInviteResults] = useState([]);
  const [opponent, setOpponent] = useState("");
  const [logoUploading, setLogoUploading] = useState(false);
  const [leaving, setLeaving] = useState(false);

  const handleErr = (err) => toast.error(formatApiErrorDetail(err.response?.data?.detail));

  const load = useCallback(async () => {
    try {
      const { data } = await api.get(`/clans/${id}`);
      setClan(data);
      api.get(`/clans/${id}/attendance`).then((r) => setAttendance(r.data)).catch(() => setAttendance(null));
      api.get(`/clans/${id}/mvp-leaderboard`).then((r) => setMvpRows(r.data || [])).catch(() => setMvpRows([]));
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
    api.get("/online-clans").then((r) => setAllClans(r.data)).catch(() => {});
    api.get("/leagues/active").then((r) => setLeagues(r.data)).catch(() => {});
  }, [load]);

  useEffect(() => {
    if (!user?.clan_id) {
      setMyClan(null);
      setMyClanAttendance(null);
      return;
    }
    api.get(`/clans/${user.clan_id}`).then((r) => setMyClan(r.data)).catch(() => setMyClan(null));
    api.get(`/clans/${user.clan_id}/attendance`).then((r) => setMyClanAttendance(r.data)).catch(() => setMyClanAttendance(null));
  }, [user?.clan_id, clan?.id]);

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
    [allClans, clan]
  );

  const ownAttendanceReady = !!myClanAttendance?.summary?.ready_for_challenge;
  const isExternalLeader = !!(user && clan && user.clan_id && user.clan_id !== clan.id && myClan && myClan.leader_id === user.id);
  const targetIsGreen = !!(attendance?.summary?.is_green || clan?.attendance?.is_green);
  const canInstantChallenge = isExternalLeader && targetIsGreen;
  const isCheckedIn = !!attendance?.checked_in?.some((p) => p.id === user?.id);
  const highlightCheckIn = useMemo(() => {
    const params = new URLSearchParams(location.search || "");
    return params.get("highlight_checkin") === "1";
  }, [location.search]);

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
      setLeaving(true);
      try {
        const { data } = await api.post(`/clans/${id}/leave`);
        await refresh();
        const cdHours = Number(data?.cooldown_hours || 3);
        toast.success(`غادرت الكلان. يمكنك الانضمام مجددًا بعد ${cdHours} ساعات`);
        load();
      } catch (err) {
        handleErr(err);
      } finally {
        setLeaving(false);
      }
  };

  const delClan = async () => {
    // eslint-disable-next-line no-alert
    if (!confirm("حذف الكلان نهائياً؟")) return;
    await api.delete(`/clans/${id}`);
    await refresh();
    window.location.href = "/clans";
  };

  const archive = async () => {
    // eslint-disable-next-line no-alert
    if (!confirm("أرشفة الكلان؟ سيتم طرد جميع الأعضاء وإيقاف الكلان.")) return;
    try {
      await api.post(`/clans/${id}/archive`);
      toast.success("تم إيقاف الكلان وطرد جميع الأعضاء");
      await refresh();
      window.location.href = "/clans";
    } catch (err) { handleErr(err); }
  };

  const challenge = async (e) => {
    e.preventDefault();
    if (!opponent) return toast.error("اختر خصماً");
    if (!user?.clan_id) return toast.error("يجب أن تكون في كلان لإرسال تحدٍ");
    if (!ownAttendanceReady) return toast.error("البحث عن تحدي يتطلب تحضير 6 لاعبين على الأقل مع حضور القائد");
    try {
      await api.post(`/clans/${user.clan_id}/challenge`, { opponent_clan_id: opponent });
      toast.success("تم إرسال طلب التحدي. ينتظر قبول الخصم.");
      setShowChallenge(false);
      setOpponent("");
      load();
    } catch (err) { handleErr(err); }
  };

  const instantChallenge = async () => {
    if (!canInstantChallenge) return;
    try {
      await api.post(`/clans/${id}/instant-challenge`);
      toast.success("تم إرسال التحدي المباشر بنجاح");
      load();
    } catch (err) { handleErr(err); }
  };

  const checkIn = async () => {
    try {
      const { data } = await api.post(`/clans/${id}/attendance/checkin`);
      setAttendance(data);
      if (user?.clan_id) {
        api.get(`/clans/${user.clan_id}/attendance`).then((r) => setMyClanAttendance(r.data)).catch(() => {});
      }
      toast.success("تم تسجيل تحضيرك");
    } catch (err) { handleErr(err); }
  };

  const checkOut = async () => {
    try {
      const { data } = await api.post(`/clans/${id}/attendance/checkout`);
      setAttendance(data);
      if (user?.clan_id) {
        api.get(`/clans/${user.clan_id}/attendance`).then((r) => setMyClanAttendance(r.data)).catch(() => {});
      }
      toast.success("تم إلغاء التحضير");
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

  const onUploadClanLogo = async (e) => {
    const f = e.target.files?.[0];
    e.target.value = "";
    if (!f || !clan) return;

    const isPlusClan = !!(clan.isPlusClan || clan.is_plus || (clan.max_members || 0) >= 12);
    const lowerName = (f.name || "").toLowerCase();
    const isGif = (f.type || "").toLowerCase() === "image/gif" || lowerName.endsWith(".gif");
    const allowed = ["image/gif", "image/png", "image/jpeg", "image/jpg"];
    if (!allowed.includes((f.type || "").toLowerCase())) {
      return toast.error("صيغة الشعار غير مدعومة. المسموح: GIF, PNG, JPG");
    }
    if (isGif && !isPlusClan) {
      return toast.error("عذراً، ميزة الشعار المتحرك GIF حصرية لكلانات البلس!");
    }

    setLogoUploading(true);
    try {
      let data;
      const primary = `/clans/${id}/logo/upload`;
      const legacy = `/clans/upload-logo`;
      const multipartHeaders = { "Content-Type": "multipart/form-data" };

      const primaryMethods = [api.post, api.put];
      let primaryErr = null;
      for (const sender of primaryMethods) {
        try {
          const fd = new FormData();
          fd.append("file", f);
          const res = await sender(primary, fd, { headers: multipartHeaders });
          data = res.data;
          primaryErr = null;
          break;
        } catch (err) {
          primaryErr = err;
          const status = err?.response?.status;
          if (status !== 404 && status !== 405) {
            throw err;
          }
        }
      }

      if (!data) {
        const legacyMethods = [api.post, api.put];
        let legacyErr = primaryErr;
        for (const sender of legacyMethods) {
          try {
            const fdLegacy = new FormData();
            fdLegacy.append("file", f);
            fdLegacy.append("clan_id", id);
            const resLegacy = await sender(legacy, fdLegacy, { headers: multipartHeaders });
            data = resLegacy.data;
            legacyErr = null;
            break;
          } catch (err) {
            legacyErr = err;
            const status = err?.response?.status;
            if (status !== 404 && status !== 405) {
              throw err;
            }
          }
        }
        if (!data && legacyErr) throw legacyErr;
      }

      if (data?.url) {
        setClan((prev) => (prev ? { ...prev, logo: data.url } : prev));
      }
      toast.success("تم تحديث شعار الكلان");
      load();
    } catch (err) {
      handleErr(err);
    } finally {
      setLogoUploading(false);
    }
  };

  return (
    <div className="space-y-6">

      {/* ── Hero header ── */}
      <ClanHeader clan={clan} />

      {/* ── Action buttons ── */}
      <div className="px-1">
        <ActionBar
          canJoin={flags.canJoin}
          isFull={flags.isFull}
          isStaff={flags.isStaff}
          isMember={flags.isMember}
          isLeader={flags.isLeader}
          canSearchChallenge={ownAttendanceReady}
          isPlusClan={!!clan?.isPlusClan}
          clanId={id}
          onJoin={join}
          onChallenge={() => setShowChallenge(true)}
          onInvite={() => setShowInvite(true)}
          onLeave={leave}
          onDelete={delClan}
          onArchive={archive}
          leaving={leaving}
        />
      </div>

      {flags.isStaff && (
        <section className="bg-surface border b-soft rounded-2xl p-5 md:p-6" data-testid="clan-logo-settings">
          <div className="flex items-center gap-2 mb-3">
            <ImageIcon size={17} className="text-gold-500" />
            <h2 className="font-display font-black text-xl">إعدادات شعار الكلان</h2>
          </div>

          <div className="flex items-center gap-4 flex-wrap">
            <ClanLogo
              clan={clan}
              className="h-16 w-16 rounded-xl border border-white/15 bg-background/50 overflow-hidden grid place-items-center"
              fallbackIconSize={24}
              fallbackIconClassName="text-white/30"
            />

            <div className="flex-1 min-w-[240px]">
              <label className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-gold-500 text-black font-bold hover:bg-gold-400 cursor-pointer text-sm">
                <ImageIcon size={15} /> {logoUploading ? "جاري الرفع..." : "رفع شعار الكلان"}
                <input
                  type="file"
                  accept=".gif,.png,.jpg,.jpeg,image/gif,image/png,image/jpeg"
                  onChange={onUploadClanLogo}
                  className="hidden"
                  disabled={logoUploading}
                />
              </label>
              <div className="mt-2 text-xs text-white/45">
                المسموح: PNG, JPG{(clan.isPlusClan || clan.is_plus || (clan.max_members || 0) >= 12) ? ", GIF" : ""}
              </div>
              {!(clan.isPlusClan || clan.is_plus || (clan.max_members || 0) >= 12) && (
                <div className="mt-1 text-xs text-amber-400">ميزة الشعار المتحرك GIF حصرية لكلانات البلس!</div>
              )}
            </div>
          </div>

        </section>
      )}

      {/* ── Instant challenge bar (external leader only) ── */}
      {isExternalLeader && (
        <div
          className="rounded-2xl border b-soft bg-surface px-6 py-4 flex items-center justify-between gap-4 flex-wrap"
          data-testid="instant-challenge-bar"
        >
          <div className="flex items-center gap-3">
            <Swords size={18} className={canInstantChallenge ? "text-destructive" : "text-white/30"} />
            <p className="text-sm text-white/65">
              التحدي المباشر متاح عندما يكون تحضير هذا الكلان أخضر (٦+).
            </p>
          </div>
          <button
            onClick={instantChallenge}
            disabled={!canInstantChallenge}
            className="px-5 py-2.5 rounded-lg bg-destructive text-white font-bold hover:bg-destructive/90 disabled:opacity-40 disabled:cursor-not-allowed text-sm"
          >
            تحدي هذا الكلان الآن
          </button>
        </div>
      )}

      {/* ── Attendance + Top MVP — side by side on desktop ── */}
      <div className="grid lg:grid-cols-2 gap-6">
        <AttendancePanel
          clan={clan}
          attendance={attendance}
          canInteract={!!flags.isMember}
          isCheckedIn={isCheckedIn}
          highlightCheckIn={highlightCheckIn}
          onCheckIn={checkIn}
          onCheckOut={checkOut}
        />
        <TopMvpWidget rows={mvpRows} />
      </div>

      {/* ── Trophy room ── */}
      <TrophyRoom trophies={clan.trophies || []} />

      {/* ── Available leagues (staff only) ── */}
      {flags.isStaff && (
        <LeaguesJoin
          clanId={clan.id}
          clanLeagueIds={clan.league_ids || []}
          leagues={leagues}
          reload={load}
          clanMembersCount={(clan.member_ids || []).length}
        />
      )}

      {/* ── Roster footer ── */}
      <section className="bg-surface border b-soft rounded-2xl overflow-hidden mt-2">
        <div className="px-6 py-4 border-b border-white/10 flex items-center justify-between gap-3 bg-white/[0.02]">
          <h2 className="font-display font-black text-xl flex items-center gap-2">
            <Shield size={18} className="text-white/50" />
            الأعضاء ({clan.members?.length || 0}/{clan.max_members || 7})
          </h2>
          <span className="text-xs text-white/35">قسم الشبكة</span>
        </div>
        <div className="p-5">
          <MembersList
            members={clan.members || []}
            leaderId={clan.leader_id}
            viceLeaderIds={clan.vice_leader_ids || []}
            canManage={flags.isLeader || user?.role === "admin"}
            onPromote={promote}
            onKick={kick}
          />
          {flags.isLeader && (
            <div className="mt-4 text-xs text-white/35">
              النواب: {clan.vice_leader_ids?.length || 0} / {clan.max_vices || 1}
              {clan.max_vices === 1 && (
                <Link to="/me" className="text-gold-500 mr-2 hover:underline">ترقى لـ Plus لزيادة الحد</Link>
              )}
            </div>
          )}
        </div>
      </section>

      {/* ── Join requests (staff) ── */}
      {flags.isStaff && <RequestsList requests={requests} onAccept={accept} onReject={reject} />}

      {/* ── Pending challenges (staff) ── */}
      {flags.isStaff && (
        <ChallengesList
          challenges={challenges}
          currentClanId={clan.id}
          onAccept={(cid) => respondChallenge(cid, "accept")}
          onReject={(cid) => respondChallenge(cid, "reject")}
        />
      )}

      {/* ── Modals ── */}
      {showChallenge && (
        <ChallengeModal
          clan={clan}
          allClans={availableOpponents.filter((c) => c.attendance?.is_green)}
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
