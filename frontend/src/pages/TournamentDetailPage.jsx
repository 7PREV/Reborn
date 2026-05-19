import { useEffect, useState, useCallback, useMemo } from "react";
import { useParams, Link } from "react-router-dom";
import api, { formatApiErrorDetail } from "../api";
import { useAuth } from "../AuthContext";
import { Trophy, Play, Crown, ScrollText, Trash2, Sparkles, Shield, ArrowRight } from "lucide-react";
import { toast } from "sonner";

function Bracket({ bracket, clans, champion }) {
  if (!bracket || bracket.length === 0) {
    return <div className="text-white/40 text-center py-10">سيظهر السلم بعد بدء البطولة</div>;
  }
  return (
    <div className="overflow-x-auto pb-4">
      <div className="flex gap-4 min-w-max">
        {bracket.map((round, ri) => (
          <div key={ri} className="flex flex-col gap-4 justify-around min-w-[200px]">
            <div className="text-xs uppercase tracking-widest text-gold-500 text-center mb-2">
              {ri === bracket.length - 1 ? "النهائي" : `الجولة ${ri + 1}`}
            </div>
            {round.map((slot, si) => {
              const a = slot.clan_a_id ? clans?.[slot.clan_a_id] : null;
              const b = slot.clan_b_id ? clans?.[slot.clan_b_id] : null;
              const winA = slot.winner_id === slot.clan_a_id;
              const winB = slot.winner_id === slot.clan_b_id;
              return (
                <div key={si} className="bg-surface border b-soft rounded-md overflow-hidden" data-testid={`bracket-${ri}-${si}`}>
                  <SlotLine clan={a} win={winA} bye={!a} />
                  <div className="border-t b-soft" />
                  <SlotLine clan={b} win={winB} bye={!b} />
                  {slot.match_id && (
                    <Link to={`/matches/${slot.match_id}`} className="block bg-gold-500/5 text-center py-1 text-[10px] uppercase tracking-widest text-gold-500 hover:bg-gold-500/10">
                      عرض المباراة <ArrowRight size={10} className="inline" />
                    </Link>
                  )}
                </div>
              );
            })}
          </div>
        ))}
      </div>
      {champion && clans?.[champion] && (
        <div className="mt-6 mx-auto max-w-md bg-gold-500/10 border border-gold-500/40 rounded-lg p-5 text-center">
          <Crown className="mx-auto text-gold-500" size={32} />
          <div className="text-[10px] uppercase tracking-widest text-gold-500 mt-2">البطل</div>
          <div className="font-display font-black text-2xl text-gold-500">{clans[champion].name}</div>
        </div>
      )}
    </div>
  );
}

function SlotLine({ clan, win, bye }) {
  if (bye) {
    return <div className="px-3 py-2 text-xs text-white/30 italic">— BYE —</div>;
  }
  if (!clan) {
    return <div className="px-3 py-2 text-xs text-white/30">في الانتظار...</div>;
  }
  return (
    <div className={`px-3 py-2 text-sm flex items-center gap-2 ${win ? "bg-gold-500/10 text-gold-500 font-bold" : ""}`}>
      <Shield size={12} className="opacity-50" />
      <span className="truncate">{clan.name}</span>
      <span className="text-[10px] opacity-60 mr-auto">[{clan.tag}]</span>
    </div>
  );
}

export default function TournamentDetailPage() {
  const { id } = useParams();
  const { user } = useAuth();
  const [t, setT] = useState(null);

  const load = useCallback(async () => {
    try {
      const { data } = await api.get(`/tournaments/${id}`);
      setT(data);
    } catch {/* polling will retry */}
  }, [id]);

  useEffect(() => {
    load();
    const iv = setInterval(load, 5000);
    return () => clearInterval(iv);
  }, [load]);

  const isStaff = user && (user.role === "admin" || user.role === "owner");

  const myClanRegistered = useMemo(
    () => !!(user?.clan_id && t?.participants?.includes(user.clan_id)),
    [user?.clan_id, t?.participants]
  );

  const plusOnlyNow = useMemo(() => {
    if (!t) return false;
    if (t.status !== "registration") return false;
    try {
      return new Date() < new Date(t.plus_window_until);
    } catch { return false; }
  }, [t?.status, t?.plus_window_until]);

  const handleErr = (err) => toast.error(formatApiErrorDetail(err.response?.data?.detail));

  const join = async () => {
    try { await api.post(`/tournaments/${id}/join`); toast.success("تم تسجيل كلانك"); load(); }
    catch (err) { handleErr(err); }
  };

  const start = async () => {
    // eslint-disable-next-line no-alert
    if (!confirm("بدء البطولة؟ لن تُقبل تسجيلات جديدة.")) return;
    try { await api.post(`/tournaments/${id}/start`); toast.success("انطلقت البطولة!"); load(); }
    catch (err) { handleErr(err); }
  };

  const remove = async () => {
    // eslint-disable-next-line no-alert
    if (!confirm("حذف البطولة نهائياً؟")) return;
    try { await api.delete(`/tournaments/${id}`); window.location.href = "/tournaments"; }
    catch (err) { handleErr(err); }
  };

  if (!t) return <div className="text-white/40">جارٍ التحميل...</div>;

  const canJoin = t.status === "registration" && user?.clan_id && !myClanRegistered &&
    t.participants.length < t.max_participants;

  const plusUntil = new Date(t.plus_window_until);
  const hoursLeft = Math.max(0, Math.ceil((plusUntil - new Date()) / 3600000));

  return (
    <div className="space-y-6">
      <div className="bg-surface border b-soft rounded-xl p-6 md:p-8">
        <div className="flex items-start gap-5 flex-wrap">
          <div className="h-16 w-16 rounded-lg bg-gold-500/10 text-gold-500 grid place-items-center">
            <Trophy size={32} />
          </div>
          <div className="flex-1 min-w-0">
            <div className="text-xs uppercase tracking-widest text-gold-500">خروج المغلوب • COD</div>
            <h1 className="font-display font-black text-3xl md:text-4xl">{t.name}</h1>
            {t.description && <p className="text-white/60 mt-2">{t.description}</p>}
            <div className="mt-3 flex flex-wrap gap-3 text-xs text-white/50">
              <span>{t.participants?.length || 0} / {t.max_participants} كلان</span>
              <span>•</span>
              <span>{t.status === "registration" ? "تسجيل مفتوح" : t.status === "live" ? "جارية" : "منتهية"}</span>
              {plusOnlyNow && (
                <>
                  <span>•</span>
                  <span className="text-gold-500 inline-flex items-center gap-1">
                    <Sparkles size={10} /> Plus فقط ({hoursLeft} ساعة متبقية)
                  </span>
                </>
              )}
            </div>
          </div>

          <div className="flex gap-2 flex-wrap">
            {canJoin && (
              <button data-testid="join-tournament" onClick={join} className="px-4 py-2 rounded-md bg-gold-500 text-black font-bold hover:bg-gold-400">
                سجّل كلانك
              </button>
            )}
            {myClanRegistered && (
              <div className="px-4 py-2 rounded-md bg-emerald-500/10 text-emerald-400 text-sm">✓ مسجل</div>
            )}
            {isStaff && t.status === "registration" && t.participants.length >= 2 && (
              <button data-testid="start-tournament" onClick={start} className="px-4 py-2 rounded-md bg-destructive text-white font-bold hover:bg-destructive/90 flex items-center gap-2">
                <Play size={16} /> ابدأ البطولة
              </button>
            )}
            {isStaff && (
              <button data-testid="delete-tournament" onClick={remove} className="px-3 py-2 rounded-md border border-destructive/30 text-destructive hover:bg-destructive/10">
                <Trash2 size={16} />
              </button>
            )}
          </div>
        </div>
      </div>

      {t.rules && (
        <section className="bg-surface border b-soft rounded-xl p-6">
          <h2 className="font-display font-black text-xl mb-3 flex items-center gap-2"><ScrollText size={18} className="text-gold-500" /> قوانين البطولة</h2>
          <p className="text-white/70 whitespace-pre-wrap leading-relaxed">{t.rules}</p>
        </section>
      )}

      <section className="bg-surface border b-soft rounded-xl p-6">
        <h2 className="font-display font-black text-xl mb-4">السلم</h2>
        <Bracket bracket={t.bracket} clans={t.clans} champion={t.champion_clan_id} />
      </section>

      {t.status === "registration" && (
        <section className="bg-surface border b-soft rounded-xl p-6">
          <h2 className="font-display font-black text-xl mb-4">المسجّلون ({t.participants?.length || 0})</h2>
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {(t.participants || []).map((cid) => {
              const c = t.clans?.[cid];
              return (
                <Link key={cid} to={`/clans/${cid}`} className="bg-background border b-soft rounded p-3 flex items-center gap-3 hover:border-gold-500/30">
                  <Shield className="text-gold-500" size={18} />
                  <div>
                    <div className="font-bold text-sm">{c?.name || "—"}</div>
                    <div className="text-[10px] text-white/40">[{c?.tag}]</div>
                  </div>
                </Link>
              );
            })}
            {(t.participants || []).length === 0 && (
              <div className="col-span-full text-center text-white/40 py-6">لا مسجّلين بعد</div>
            )}
          </div>
        </section>
      )}
    </div>
  );
}
