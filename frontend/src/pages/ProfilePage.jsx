import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import api, { formatApiErrorDetail } from "../api";
import { useAuth } from "../AuthContext";
import { Shield, Trophy, Mail, Check, X, Sparkles, Tv, Save, RefreshCw, Lock } from "lucide-react";
import { toast } from "sonner";

const ACT_COOLDOWN_DAYS = 14;

function formatActCooldown(changedAt) {
  if (!changedAt) return null;
  try {
    const next = new Date(new Date(changedAt).getTime() + ACT_COOLDOWN_DAYS * 86400000);
    const diff = next - new Date();
    if (diff <= 0) return null;
    const days = Math.floor(diff / 86400000);
    const hrs = Math.floor((diff % 86400000) / 3600000);
    return `${days} يوم و${hrs} ساعة`;
  } catch {
    return null;
  }
}

export default function ProfilePage() {
  const { user, refresh } = useAuth();
  const [invites, setInvites] = useState([]);
  const [streamForm, setStreamForm] = useState({ twitch_url: "", kick_url: "", tiktok_url: "", act: "" });
  const [savingStreams, setSavingStreams] = useState(false);
  const [archivedClan, setArchivedClan] = useState(null);

  const load = async () => {
    const { data } = await api.get("/me/invites");
    setInvites(data);
  };
  useEffect(() => { load(); }, []);
  useEffect(() => {
    if (user) {
      setStreamForm({
        twitch_url: user.twitch_url || "",
        kick_url: user.kick_url || "",
        tiktok_url: user.tiktok_url || "",
        act: user.act || "",
      });
      api.get("/me/archived-clan").then((r) => setArchivedClan(r.data)).catch(() => setArchivedClan(null));
    }
  }, [user]);

  const saveStreams = async (e) => {
    e.preventDefault();
    setSavingStreams(true);
    try {
      await api.put("/me/profile", streamForm);
      toast.success("تم حفظ الملف الشخصي");
      await refresh();
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail));
    } finally {
      setSavingStreams(false);
    }
  };

  const restoreClan = async () => {
    if (!archivedClan) return;
    // eslint-disable-next-line no-alert
    if (!confirm(`استعادة كلان "${archivedClan.name}" من الأرشيف؟`)) return;
    try {
      await api.post(`/clans/${archivedClan.id}/restore`);
      toast.success("تم استعادة الكلان بنجاح");
      await refresh();
      setArchivedClan(null);
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail));
    }
  };

  const respond = async (inv, action) => {
    try {
      const { data } = await api.post(`/invites/${inv.id}`, { action });
      if (data?.reward_granted) {
        toast.success("🎁 امتلأ كلانك! حصلت على Plus 7 أيام!", { duration: 6000 });
      } else {
        toast.success(action === "accept" ? "انضممت للكلان" : "رفضت الدعوة");
      }
      await refresh();
      load();
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail));
    }
  };

  const togglePlus = async () => {
    try {
      await api.post("/me/plus");
      await refresh();
      toast.success("تم تحديث Plus");
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail));
    }
  };

  if (!user) return null;

  return (
    <div className="space-y-8">
      <div className="bg-surface border b-soft rounded-xl p-6 md:p-8 flex items-center gap-5 flex-wrap">
        <div className="h-20 w-20 rounded-lg bg-gold-500/10 text-gold-500 grid place-items-center font-display font-black text-3xl">
          {user.username[0].toUpperCase()}
        </div>
        <div className="flex-1 min-w-0">
          <div className="text-xs uppercase tracking-widest text-gold-500 flex items-center gap-2">
            {user.role === "admin" ? "منظم" : user.is_plus ? "Plus" : "لاعب"}
            {user.is_plus && <Sparkles size={12} />}
          </div>
          <h1 className="font-display font-black text-3xl">{user.username}</h1>
          <div className="text-white/50 text-sm">{user.email}</div>
          {user.act && (
            <div className="mt-2 inline-flex items-center gap-1 text-xs bg-white/5 border b-soft rounded px-2 py-1" data-testid="profile-act">
              <span className="text-white/40">Activision ID:</span>
              <span className="text-gold-400 font-bold">{user.act}</span>
            </div>
          )}
        </div>
        <div className="text-center">
          <div className="text-3xl font-display font-black text-gold-500 flex items-center gap-1">
            <Trophy size={20} /> {user.points}
          </div>
          <div className="text-[10px] uppercase tracking-widest text-white/40">النقاط</div>
        </div>
      </div>

      <div className={`rounded-xl p-6 border ${user.is_plus ? "border-gold-500/40 bg-gold-500/5" : "border-white/5 bg-surface"}`}>
        <div className="flex items-center gap-3 mb-3">
          <Sparkles className="text-gold-500" />
          <h2 className="font-display font-black text-xl">RIVALS Plus</h2>
          {user.is_plus && <span className="text-[10px] uppercase tracking-widest bg-gold-500 text-black px-2 py-0.5 rounded">مفعل</span>}
        </div>
        {user.plus_expires_at && (
          <div className="text-xs text-gold-500 mb-3" data-testid="plus-expiry">
            ينتهي خلال: {Math.max(0, Math.ceil((new Date(user.plus_expires_at) - new Date()) / 86400000))} يوم
          </div>
        )}
        <ul className="text-sm text-white/70 space-y-1 mb-4 list-disc pr-5">
          <li>زيادة سعة الكلان من 7 إلى 12 لاعب</li>
          <li>تعيين نائبَين للقائد بدل نائب واحد</li>
          <li>دعم أولوية في النزاعات</li>
          <li className="text-gold-500">🎁 املأ كلانك بـ 6 لاعبين تحصل على Plus مجاناً لمدة 7 أيام</li>
        </ul>
        <button data-testid="toggle-plus-btn" onClick={togglePlus} className={`px-4 py-2 rounded-md font-bold ${
          user.is_plus ? "bg-white/5 hover:bg-white/10" : "bg-gold-500 text-black hover:bg-gold-400"
        }`}>
          {user.is_plus ? "إلغاء Plus" : "تفعيل Plus (مجاناً للتجربة)"}
        </button>
      </div>

      <section data-testid="streams-section" className="bg-surface border b-soft rounded-xl p-6">
        <h2 className="font-display font-black text-xl mb-3 flex items-center gap-2">
          <Tv className="text-gold-500" size={20} /> روابط البث المباشر و Activision
        </h2>
        <form onSubmit={saveStreams} className="space-y-3">
          <div>
            <label className="text-xs uppercase tracking-widest text-white/50 mb-1 block flex items-center gap-1">
              Activision ID
              {formatActCooldown(user.act_changed_at) && <Lock size={12} className="text-destructive" />}
            </label>
            <input
              data-testid="profile-act-input"
              value={streamForm.act}
              onChange={(e) => setStreamForm({ ...streamForm, act: e.target.value })}
              minLength={2}
              maxLength={40}
              disabled={!!formatActCooldown(user.act_changed_at)}
              placeholder="YourName#1234"
              className="w-full bg-background border b-soft rounded-md px-3 py-2 outline-none focus:border-gold-500/40 text-sm disabled:opacity-50 disabled:cursor-not-allowed"
            />
            {formatActCooldown(user.act_changed_at) ? (
              <div data-testid="act-cooldown-msg" className="text-[11px] text-destructive mt-1">
                لا يمكنك تغيير الـ Activision ID إلا مرة كل أسبوعين. المتبقي: {formatActCooldown(user.act_changed_at)}
              </div>
            ) : (
              <div className="text-[10px] text-white/40 mt-1">⚠️ بعد التغيير يصبح مغلقًا لمدة 14 يومًا.</div>
            )}
          </div>
          <div>
            <label className="text-xs uppercase tracking-widest text-white/50 mb-1 block">Twitch URL</label>
            <input
              data-testid="profile-twitch-input"
              value={streamForm.twitch_url}
              onChange={(e) => setStreamForm({ ...streamForm, twitch_url: e.target.value })}
              placeholder="https://twitch.tv/yourname"
              className="w-full bg-background border b-soft rounded-md px-3 py-2 outline-none focus:border-gold-500/40 text-sm"
            />
          </div>
          <div>
            <label className="text-xs uppercase tracking-widest text-white/50 mb-1 block">Kick URL</label>
            <input
              data-testid="profile-kick-input"
              value={streamForm.kick_url}
              onChange={(e) => setStreamForm({ ...streamForm, kick_url: e.target.value })}
              placeholder="https://kick.com/yourname"
              className="w-full bg-background border b-soft rounded-md px-3 py-2 outline-none focus:border-gold-500/40 text-sm"
            />
          </div>
          <div>
            <label className="text-xs uppercase tracking-widest text-white/50 mb-1 block">TikTok URL (رابط فقط)</label>
            <input
              data-testid="profile-tiktok-input"
              value={streamForm.tiktok_url}
              onChange={(e) => setStreamForm({ ...streamForm, tiktok_url: e.target.value })}
              placeholder="https://tiktok.com/@yourname"
              className="w-full bg-background border b-soft rounded-md px-3 py-2 outline-none focus:border-gold-500/40 text-sm"
            />
            <div className="text-[10px] text-white/40 mt-1">TikTok يظهر كرابط في الملف الشخصي فقط (لا يدعم كشف البث المباشر).</div>
          </div>
          <button
            data-testid="save-profile-btn"
            type="submit"
            disabled={savingStreams}
            className="px-4 py-2 rounded-md bg-gold-500 text-black font-bold hover:bg-gold-400 disabled:opacity-50 flex items-center gap-2"
          >
            <Save size={14} /> {savingStreams ? "..." : "حفظ"}
          </button>
        </form>
      </section>

      {archivedClan && !user.clan_id && (
        <div data-testid="restore-clan-card" className="bg-gold-500/5 border border-gold-500/30 rounded-xl p-5 flex items-center gap-3 flex-wrap">
          <Shield className="text-gold-500" />
          <div className="flex-1 min-w-0">
            <div className="font-display font-bold">كلانك في الأرشيف: {archivedClan.name}</div>
            <div className="text-xs text-white/50 mt-0.5">[{archivedClan.tag}] • مؤرشف منذ {new Date(archivedClan.archived_at).toLocaleDateString("ar")}</div>
          </div>
          <button
            data-testid="restore-clan-btn"
            onClick={restoreClan}
            className="px-4 py-2 rounded-md bg-gold-500 text-black font-bold hover:bg-gold-400 flex items-center gap-2"
          >
            <RefreshCw size={14} /> استعادة الكلان من الأرشفة
          </button>
        </div>
      )}

      {user.clan_cooldown_until && new Date(user.clan_cooldown_until) > new Date() && (
        <div data-testid="cooldown-banner" className="bg-destructive/10 border border-destructive/30 rounded-xl p-5 flex items-center gap-3">
          <X className="text-destructive" />
          <div className="flex-1">
            <div className="font-bold text-destructive">في فترة انتظار</div>
            <div className="text-xs text-white/60 mt-1">
              لا يمكنك الانضمام لكلان جديد قبل: {new Date(user.clan_cooldown_until).toLocaleString("ar")}
            </div>
          </div>
        </div>
      )}

      {user.clan_id && (
        <div className="bg-surface border b-soft rounded-xl p-5 flex items-center gap-3">
          <Shield className="text-gold-500" />
          <span>أنت عضو في كلان</span>
          <Link to={`/clans/${user.clan_id}`} className="mr-auto px-3 py-1.5 rounded bg-gold-500 text-black text-sm font-bold hover:bg-gold-400">
            عرض الكلان
          </Link>
        </div>
      )}

      <section>
        <h2 className="font-display font-black text-2xl mb-4 flex items-center gap-2">
          <Mail size={20} className="text-gold-500" /> دعوات الانضمام
        </h2>
        {invites.length === 0 ? (
          <div className="bg-surface border b-soft rounded-lg p-8 text-center text-white/40">لا توجد دعوات</div>
        ) : (
          <div className="space-y-2">
            {invites.map((inv) => (
              <div key={inv.id} className="bg-surface border b-soft rounded-lg p-4 flex items-center gap-3" data-testid={`invite-${inv.id}`}>
                <Shield className="text-gold-500" />
                <div className="flex-1">
                  <div className="font-bold">{inv.clan_name}</div>
                  <div className="text-xs text-white/40">[{inv.clan_tag}]</div>
                </div>
                <button data-testid={`invite-accept-${inv.id}`} onClick={() => respond(inv, "accept")} className="p-2 rounded bg-gold-500 text-black hover:bg-gold-400"><Check size={16} /></button>
                <button onClick={() => respond(inv, "reject")} className="p-2 rounded border b-soft hover:bg-destructive/10 text-destructive"><X size={16} /></button>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
