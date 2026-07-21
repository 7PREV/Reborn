import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import api, { billingSubscription, formatApiErrorDetail } from "../api";
import { useAuth } from "../AuthContext";
import { Shield, Trophy, Mail, Check, X, Sparkles, Save, RefreshCw, Lock, Flame, Swords, Copy, Pencil } from "lucide-react";
import { FaTwitch, FaYoutube, FaTiktok, FaInstagram, FaXTwitter, FaDiscord } from "react-icons/fa6";
import { FaPenToSquare } from "react-icons/fa6";
import { SiKick } from "react-icons/si";
import { toast } from "sonner";

const ACT_COOLDOWN_DAYS = 14;
const PROFILE_DRAFT_FIELDS = [
  "act",
  "discord_username",
  "twitch_url",
  "kick_url",
  "youtube_url",
  "tiktok_url",
  "instagram_link",
  "x_link",
  "accent_color",
  "avatar",
  "banner",
];

function toProfileDraft(u) {
  if (!u) return null;
  return {
    act: u.act || "",
    discord_username: u.discord_username || "",
    twitch_url: u.twitch_url || "",
    kick_url: u.kick_url || "",
    youtube_url: u.youtube_url || "",
    tiktok_url: u.tiktok_url || "",
    instagram_link: u.instagram_link || "",
    x_link: u.x_link || "",
    accent_color: u.accent_color || "#FFCC00",
    avatar: u.avatar || null,
    banner: u.banner || null,
  };
}

function isProfileDraftDirty(user, draft) {
  if (!user || !draft) return false;
  const base = toProfileDraft(user);
  return PROFILE_DRAFT_FIELDS.some((k) => (draft?.[k] ?? null) !== (base?.[k] ?? null));
}

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
  const [draft, setDraft] = useState(null);
  const [savingDraft, setSavingDraft] = useState(false);
  const [archivedClan, setArchivedClan] = useState(null);
  const [clanMembersCount, setClanMembersCount] = useState(0);
  const [billingStatus, setBillingStatus] = useState(null);
  const [referralStats, setReferralStats] = useState(null);
  const [copiedReferral, setCopiedReferral] = useState(false);

  const load = async () => {
    try {
      const { data } = await api.get("/me/invites");
      setInvites(data);
    } catch (err) {
      setInvites([]);
      if (err?.response?.status !== 401) {
        toast.error(formatApiErrorDetail(err.response?.data?.detail));
      }
    }
  };
  useEffect(() => {
    if (!user) return;
    load();
  }, [user]);
  useEffect(() => {
    if (user) {
      setDraft(toProfileDraft(user));
      api.get("/me/archived-clan").then((r) => setArchivedClan(r.data)).catch(() => setArchivedClan(null));
      billingSubscription().then((r) => setBillingStatus(r.data)).catch(() => setBillingStatus(null));
      api.get("/me/referrals").then((r) => setReferralStats(r.data)).catch(() => setReferralStats(null));
      if (user.clan_id) {
        api.get(`/clans/${user.clan_id}`)
          .then((r) => {
            const c = r.data || {};
            const count = Array.isArray(c.member_ids)
              ? c.member_ids.length
              : (Array.isArray(c.members) ? c.members.length : 0);
            setClanMembersCount(count);
          })
          .catch(() => setClanMembersCount(0));
      } else {
        setClanMembersCount(0);
      }
    }
  }, [user]);

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

  const copyReferralLink = async () => {
    const link = referralStats?.referral_link;
    if (!link) return;
    try {
      await navigator.clipboard.writeText(link);
      setCopiedReferral(true);
      toast.success("Copied!");
      setTimeout(() => setCopiedReferral(false), 2000);
    } catch {
      toast.error("تعذر نسخ الرابط");
    }
  };

  const onFieldChange = (key, value) => {
    setDraft((prev) => ({ ...(prev || {}), [key]: value }));
  };

  const discardDraft = () => {
    if (!user) return;
    setDraft(toProfileDraft(user));
    toast.success("تم تجاهل التعديلات");
  };

  const saveDraft = async () => {
    if (!user || !draft || savingDraft) return;
    const base = toProfileDraft(user);
    const payload = {};
    for (const k of PROFILE_DRAFT_FIELDS) {
      if ((draft?.[k] ?? null) !== (base?.[k] ?? null)) {
        payload[k] = draft?.[k];
      }
    }
    if (Object.keys(payload).length === 0) return;
    setSavingDraft(true);
    try {
      const { data } = await api.put("/me/profile", payload);
      setDraft(toProfileDraft(data));
      await refresh();
      toast.success("✅ تم حفظ التغييرات");
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail));
    } finally {
      setSavingDraft(false);
    }
  };

  const togglePlus = async () => {
    const activating = !user.is_plus;
    if (activating && clanMembersCount < 6) {
      return toast.error("يجب أن يحتوي الكلان على 6 لاعبين على الأقل لتفعيل التجربة المجانية");
    }
    try {
      await api.post("/me/plus");
      await refresh();
      toast.success("تم تحديث Plus");
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail));
    }
  };

  if (!user) return null;

  const profileView = { ...user, ...(draft || {}) };
  const isPlus = !!user.is_personal_plus;
  const canActivateTrialPlus = user.is_plus || clanMembersCount >= 6;
  const accent = (isPlus && profileView.accent_color) || "#FFCC00";
  const bannerStyle = isPlus && profileView.banner
    ? { backgroundImage: `url(${profileView.banner})`, backgroundSize: "cover", backgroundPosition: "center" }
    : { backgroundColor: accent };
  const hasDraftChanges = isProfileDraftDirty(user, draft);

  return (
    <div className="space-y-8">
      <PremiumProfileHeader
        user={profileView}
        rawUser={user}
        draft={draft}
        accent={accent}
        isPlus={isPlus}
        bannerStyle={bannerStyle}
        onFieldChange={onFieldChange}
      />

      {user.clan_id && (
        <Link to={`/clans/${user.clan_id}`} data-testid="profile-clan-link" className="block bg-surface border b-soft rounded-xl p-5 hover:border-gold-500/30">
          <div className="flex items-center gap-3">
            <Shield className="text-gold-500" />
            <div className="flex-1">
              <div className="text-xs uppercase tracking-widest text-white/40">كلانك</div>
              <div className="font-display font-black text-lg">اذهب إلى صفحة الكلان</div>
            </div>
          </div>
        </Link>
      )}

      <section className="bg-surface border b-soft rounded-xl p-6" data-testid="referrals-rewards-card">
        <div className="flex items-center gap-2 mb-3">
          <Sparkles className="text-emerald-400" size={18} />
          <h2 className="font-display font-black text-xl">الإحالات والمكافآت</h2>
        </div>

        <div className="grid md:grid-cols-3 gap-3 mb-4">
          <div className="rounded-lg border b-soft bg-background/40 p-3">
            <div className="text-[10px] uppercase tracking-widest text-white/40">الرصيد الحالي</div>
            <div className="font-display font-black text-2xl text-emerald-300">🪙 {Number(referralStats?.riv_points ?? user?.riv_points ?? 0)} RIV</div>
          </div>
          <div className="rounded-lg border b-soft bg-background/40 p-3">
            <div className="text-[10px] uppercase tracking-widest text-white/40">عدد المدعوين</div>
            <div className="font-display font-black text-2xl text-gold-500">{Number(referralStats?.invited_count || 0)}</div>
          </div>
          <div className="rounded-lg border b-soft bg-background/40 p-3">
            <div className="text-[10px] uppercase tracking-widest text-white/40">مكافأة كل دعوة</div>
            <div className="font-display font-black text-2xl text-emerald-300">+{Number(referralStats?.reward_per_invite || 1)} RIV</div>
          </div>
        </div>

        <div className="text-xs text-white/50 mb-2">رابط الإحالة الخاص بك</div>
        <div className="flex items-center gap-2 flex-wrap">
          <input
            readOnly
            value={referralStats?.referral_link || ""}
            className="flex-1 min-w-[220px] bg-background border b-soft rounded-md px-3 py-2 text-sm text-white/80"
          />
          <button
            type="button"
            onClick={copyReferralLink}
            className={`px-3 py-2 rounded-md font-bold inline-flex items-center gap-1.5 transition-all duration-300 ${copiedReferral ? "bg-emerald-400 text-black shadow-[0_0_22px_rgba(16,185,129,0.8)] ring-1 ring-emerald-300" : "bg-emerald-500 text-black hover:bg-emerald-400"}`}
          >
            <Copy size={14} /> {copiedReferral ? "Copied! ✓" : "Copy Link"}
          </button>
        </div>

        <div className="mt-4 rounded-lg border border-emerald-500/20 bg-emerald-500/5 p-4">
          <div className="font-bold text-emerald-300 mb-2">❓ ما هي نقاط RIV وكيف تستفيد منها؟</div>
          <p className="text-sm text-white/75 leading-7">
            نقاط RIV هي العملة الخاصة بـ RIVALS (كل نقطة تساوي 1 ريال)! يمكنك جمع النقاط بسهولة عن طريق مشاركة رابط الإحالة الخاص بك مع أصدقائك؛ حيث ستحصل على نقطة واحدة (1 RIV) فور تسجيل وتأكيد حساب كل شخص يدخل عن طريقك. يمكنك لاحقاً استخدام هذه النقاط لشراء أو تجديد اشتراكك مجاناً بالكامل دون الحاجة للدفع بالفيزا! (اشتراك Personal Plus بـ 11 نقطة فقط، واشتراك Clan Plus بـ 27 نقطة فقط).
          </p>
        </div>
      </section>
      <div className={`rounded-xl p-6 border ${user.is_plus ? "border-gold-500/40 bg-gold-500/5" : "border-white/5 bg-surface"}`}>
        <div className="flex items-center gap-3 mb-3">
          <Sparkles className="text-gold-500" />
          <h2 className="font-display font-black text-xl">RIVALS Plus (الكلان)</h2>
          {user.is_plus && <span className="text-[10px] uppercase tracking-widest bg-gold-500 text-black px-2 py-0.5 rounded">مفعل</span>}
        </div>
        {user.plus_expires_at && (
          <div className="text-xs text-gold-500 mb-3" data-testid="plus-expiry">
            ينتهي خلال: {Math.max(0, Math.ceil((new Date(user.plus_expires_at) - new Date()) / 86400000))} يوم
          </div>
        )}
        {billingStatus && (
          <div className="text-xs text-white/60 mb-3" data-testid="billing-source">
            مصدر الاشتراك: {billingStatus.sources?.includes("manual") ? "يدوي" : "—"}
            {billingStatus.sources?.includes("manual") && billingStatus.sources?.includes("billing") ? " + " : ""}
            {billingStatus.sources?.includes("billing") ? "دفع" : ""}
          </div>
        )}
        <ul className="text-sm text-white/70 space-y-1 mb-4 list-disc pr-5">
          <li>زيادة سعة الكلان من 7 إلى 12 لاعب</li>
          <li>تعيين نائبَين للقائد بدل نائب واحد</li>
          <li>دعم أولوية في النزاعات</li>
          <li className="text-gold-500">🎁 املأ كلانك حتى يصل لـ 6 لاعبين تحصل على Plus مجاناً لمدة 7 أيام</li>
        </ul>
        <button
          data-testid="toggle-plus-btn"
          onClick={togglePlus}
          disabled={!canActivateTrialPlus}
          title={!canActivateTrialPlus ? "يتطلب 6 لاعبين على الأقل في الكلان" : ""}
          className={`px-4 py-2 rounded-md font-bold ${
            user.is_plus ? "bg-white/5 hover:bg-white/10" : "bg-gold-500 text-black hover:bg-gold-400"
          } disabled:opacity-50 disabled:cursor-not-allowed`}
        >
          {user.is_plus ? "إلغاء Plus" : "تفعيل Plus (مجاناً للتجربة)"}
        </button>
        {!canActivateTrialPlus && (
          <div className="text-xs text-destructive mt-2">
            يجب أن يحتوي الكلان على 6 لاعبين على الأقل لتفعيل التجربة المجانية
          </div>
        )}
      </div>

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

      <ProfileDraftActionBar
        visible={hasDraftChanges}
        saving={savingDraft}
        onSave={saveDraft}
        onDiscard={discardDraft}
      />
    </div>
  );
}

// --------------- Premium profile header ----------------
function PremiumProfileHeader({ user, rawUser, draft, accent, isPlus, bannerStyle, onFieldChange }) {
  const role = user.role === "owner" ? "مالك" : user.role === "admin" ? "منظم" : "لاعب";
  const roleBadgeClass = user.role === "owner"
    ? "text-royalGold-300 border-royalGold-400/40 bg-royalGold-500/10"
    : user.role === "admin"
      ? "text-gray-200 border-gray-300/30 bg-gray-300/10"
      : "text-white/80 border-white/20 bg-black/25";
  const initial = (user.username?.[0] || "?").toUpperCase();
  const avatarInputRef = useRef(null);
  const bannerInputRef = useRef(null);
  const [editingAct, setEditingAct] = useState(false);

  const pickVisual = (kind) => {
    if (!isPlus) {
      toast.error("التخصيص البصري متاح لمشتركي Personal Plus فقط");
      return;
    }
    if (kind === "avatar") avatarInputRef.current?.click();
    else bannerInputRef.current?.click();
  };

  const onPickImage = async (file, type) => {
    if (!file) return;
    const max = type === "avatar" ? 2_000_000 : 3_000_000;
    if (file.size > max) {
      toast.error(type === "avatar" ? "الأفاتار كبير (الحد 2MB)" : "البانر كبير (الحد 3MB)");
      return;
    }
    const dataUrl = await fileToDataUrl(file);
    onFieldChange(type, dataUrl);
  };

  return (
    <div data-testid="premium-profile" className="rounded-2xl overflow-hidden border b-soft bg-surface">
      <div data-testid="profile-banner" className="h-48 md:h-56 w-full relative group/banner cursor-pointer" style={bannerStyle} onClick={() => pickVisual("banner")}>
        <div className="absolute inset-0 bg-gradient-to-t from-background via-background/40 to-transparent" />
        <MediaEditOverlay label="تعديل البنر" />
        <input
          ref={bannerInputRef}
          type="file"
          accept="image/*"
          className="hidden"
          onChange={(e) => onPickImage(e.target.files?.[0], "banner")}
        />
        <div className="absolute bottom-3 left-3 flex items-center gap-2 flex-wrap">
          <span className={`inline-flex items-center gap-1 text-[10px] uppercase tracking-widest backdrop-blur px-2.5 py-1 rounded-full border ${roleBadgeClass}`}>
            <Shield size={10} /> {role}
          </span>
          {isPlus && (
            <span className="inline-flex items-center gap-1 text-[10px] uppercase tracking-widest px-2.5 py-1 rounded-full border border-royalGold-400/40 bg-gradient-to-l from-royalGold-700/70 to-royalGold-500/70 text-white shadow-[0_0_12px_rgba(203,213,225,0.22)]">
              <Sparkles size={10} className="text-[#d4af37] drop-shadow-[0_0_8px_rgba(212,175,55,0.55)]" /> Personal Plus
            </span>
          )}
        </div>
      </div>

      <div className="px-6 md:px-8 pb-6 -mt-12 relative space-y-5">
        <div className="grid lg:grid-cols-[1fr_auto] gap-4 items-end">
          <div className="flex items-end gap-4 min-w-0">
            <div
              data-testid="profile-avatar"
              onClick={() => pickVisual("avatar")}
              className="h-24 w-24 md:h-28 md:w-28 rounded-full border-4 border-background grid place-items-center overflow-hidden text-3xl font-display font-black relative group/avatar cursor-pointer"
              style={{
                backgroundColor: isPlus && user.avatar ? "transparent" : `${accent}22`,
                color: accent,
                boxShadow: `0 0 0 2px ${accent}55`,
              }}
            >
              {isPlus && user.avatar ? (
                <img src={user.avatar} alt={user.username} className="h-full w-full object-cover" />
              ) : initial}
              <MediaEditOverlay avatar />
              <input
                ref={avatarInputRef}
                type="file"
                accept="image/*"
                className="hidden"
                onChange={(e) => onPickImage(e.target.files?.[0], "avatar")}
              />
            </div>
            <div className="flex-1 min-w-0">
              {!editingAct ? (
                <div className="flex items-center gap-2">
                  {user.act ? (
                    <h1 data-testid="profile-act-display" className="font-display font-black text-2xl sm:text-3xl md:text-4xl leading-tight break-all whitespace-normal" style={{ color: accent }}>
                      {user.act}
                    </h1>
                  ) : (
                    <h1 className="font-display font-black text-2xl sm:text-3xl md:text-4xl leading-tight break-all whitespace-normal text-white/70">{user.username}</h1>
                  )}
                  <button
                    type="button"
                    disabled={!!formatActCooldown(rawUser?.act_changed_at)}
                    onClick={() => setEditingAct(true)}
                    className="p-1.5 rounded-md border border-white/20 text-white/75 hover:bg-white/10 disabled:opacity-45"
                  >
                    <Pencil size={13} />
                  </button>
                </div>
              ) : (
                <div className="flex items-center gap-2 max-w-md">
                  <input
                    data-testid="profile-act-input"
                    value={draft?.act || ""}
                    onChange={(e) => onFieldChange("act", e.target.value)}
                    minLength={2}
                    maxLength={40}
                    placeholder="YourName#1234"
                    className="flex-1 bg-background border b-soft rounded-md px-3 py-2 outline-none focus:border-gold-500/40 text-sm"
                  />
                  <button type="button" onClick={() => setEditingAct(false)} className="px-2.5 py-2 rounded-md border border-white/20 text-white/80 hover:bg-white/10 text-xs">
                    تم
                  </button>
                </div>
              )}
              <div className="text-white/50 text-sm mt-1 truncate">@{user.username} • {user.email}</div>
              {formatActCooldown(rawUser?.act_changed_at) ? (
                <div data-testid="act-cooldown-msg" className="text-[11px] text-destructive mt-1 inline-flex items-center gap-1">
                  <Lock size={12} /> لا يمكنك تعديل حساب اللعب الآن. المتبقي: {formatActCooldown(rawUser?.act_changed_at)}
                </div>
              ) : null}
            </div>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-2 lg:w-[440px]" data-testid="profile-main-stats">
            <Stat label="نقاط" value={user.points || 0} accent={accent} testid="stat-points" />
            <Stat label="فوز" value={user.wins || 0} accent={accent} testid="stat-wins" />
            <Stat label="خسارة" value={user.losses || 0} accent={accent} testid="stat-losses" />
            <Stat label="W/L" value={user.kd ?? 0} accent={accent} testid="stat-kd" />
          </div>
        </div>

        <div className="grid lg:grid-cols-[1.2fr_1fr] gap-4">
          <div>
            <div className="text-[10px] uppercase tracking-widest text-white/40 mb-2">الإنجازات</div>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-2" data-testid="profile-achievements">
              <AchievementBadge icon={<Check size={14} />} label="عدد مرات التحضير" value={user.attendances || 0} accent={accent} tone="silver" />
              <AchievementBadge icon={<Trophy size={14} />} label="نجم المباراة" value={user.mvp_count || 0} accent={accent} tone="gold" />
              <AchievementBadge icon={<Swords size={14} />} label="Wins" value={user.wins || 0} accent={accent} tone="bronze" />
              <AchievementBadge icon={<Flame size={14} />} label="Losses" value={user.losses || 0} accent={accent} tone="danger" />
            </div>
          </div>

          <div>
            <SingleColorPicker value={draft?.accent_color || "#FFCC00"} onChange={(v) => onFieldChange("accent_color", v)} disabled={!isPlus} />
            <div className="text-[10px] uppercase tracking-widest text-white/40 mb-2 mt-3">القنوات والحسابات</div>
            <SocialChannelsCard user={user} onFieldChange={onFieldChange} testidPrefix="social" />
          </div>
        </div>
      </div>
    </div>
  );
}

const SOCIAL_PLATFORMS = [
  { key: "discord_username", label: "Discord", testid: "social-discord", Icon: FaDiscord, color: "#5865F2", kind: "text", placeholder: "your_username" },
  { key: "twitch_url", label: "Twitch", testid: "social-twitch", Icon: FaTwitch, color: "#a970ff" },
  { key: "kick_url", label: "Kick", testid: "social-kick", Icon: SiKick, color: "#53fc18" },
  { key: "youtube_url", label: "YouTube", testid: "social-youtube", Icon: FaYoutube, color: "#ff0000" },
  { key: "tiktok_url", label: "TikTok", testid: "social-tiktok", Icon: FaTiktok, color: "#ffffff" },
  { key: "instagram_link", label: "Instagram", testid: "social-instagram", Icon: FaInstagram, color: "#e1306c" },
  { key: "x_link", label: "X", testid: "social-x", Icon: FaXTwitter, color: "#ffffff" },
];

function SocialChannelsCard({ user, onFieldChange, testidPrefix = "social" }) {
  const [editingKey, setEditingKey] = useState("");

  const startEdit = (key, initialValue) => {
    setEditingKey(key);
  };

  const cancelEdit = () => {
    setEditingKey("");
  };

  return (
    <div className="grid gap-2">
      {SOCIAL_PLATFORMS.map((p) => {
        const url = user?.[p.key] || "";
        return (
          <SocialRow
            key={p.key}
            platform={{ ...p, testid: `${testidPrefix}-${p.label.toLowerCase()}` }}
            url={url}
            isEditing={editingKey === p.key}
            onDraftChange={(v) => onFieldChange?.(p.key, v)}
            onEdit={() => startEdit(p.key, url)}
            onCancel={cancelEdit}
            onSave={() => setEditingKey("")}
          />
        );
      })}
    </div>
  );
}

function AchievementBadge({ icon, label, value, accent, tone = "gold" }) {
  const toneClass = tone === "gold"
    ? "border-royalGold-500/30 bg-royalGold-500/8"
    : tone === "silver"
      ? "border-gray-300/30 bg-gray-300/10"
      : tone === "bronze"
        ? "border-slate-500/40 bg-slate-500/10"
        : "border-destructive/35 bg-destructive/10";
  const iconClass = tone === "gold"
    ? "text-royalGold-400"
    : tone === "silver"
      ? "text-gray-300"
      : tone === "bronze"
        ? "text-slate-400"
        : "text-destructive";
  return (
    <div className={`rounded-xl border px-3 py-2 text-center ${toneClass}`}>
      <div className="mb-1 inline-flex items-center justify-center h-6 w-6 rounded-full bg-black/20">
        <span className={iconClass}>{icon}</span>
      </div>
      <div className="text-lg font-display font-black" style={{ color: accent }}>{value}</div>
      <div className="text-[10px] text-white/60">{label}</div>
    </div>
  );
}

function Stat({ label, value, accent, testid }) {
  return (
    <div className="text-center rounded-xl border border-royalGold-500/20 bg-royalGold-500/5 px-3 py-2" data-testid={testid}>
      <div className="font-display font-black text-xl md:text-2xl" style={{ color: accent }}>{value}</div>
      <div className="text-[10px] uppercase tracking-widest text-white/40">{label}</div>
    </div>
  );
}

function SocialRow({ platform, url, isEditing = false, onDraftChange, onEdit, onCancel, onSave }) {
  const { Icon, label, color, testid, kind = "url", placeholder = "" } = platform;
  const iconNode = <Icon size={16} color={color} />;
  const normalizedValue = kind === "text" ? String(url || "").replace(/^@+/, "") : url;

  if (isEditing) {
    return (
      <div className="w-full flex items-center gap-3 bg-[#111113] border border-gray-800 rounded-lg px-3 py-2.5 text-sm" data-testid={`${testid}-edit`}>
        <span>{iconNode}</span>
        <span className="font-bold w-16 shrink-0">{label}</span>
        <input
          value={normalizedValue}
          onChange={(e) => onDraftChange?.(e.target.value)}
          placeholder={kind === "text" ? placeholder : `https://${label.toLowerCase()}.com/username`}
          className="flex-1 bg-black/35 border border-gray-700 rounded-md px-2.5 py-1.5 outline-none focus:border-royalGold-400 text-white/85"
        />
        <button
          type="button"
          onClick={onSave}
          className="px-2.5 py-1.5 rounded-md bg-emerald-500 text-black font-bold hover:bg-emerald-400 disabled:opacity-50"
        >
          تم
        </button>
        <button
          type="button"
          onClick={onCancel}
          className="px-2.5 py-1.5 rounded-md border border-gray-700 text-white/75 hover:bg-white/5 disabled:opacity-50"
        >
          إلغاء
        </button>
      </div>
    );
  }

  if (!url) {
    return (
      <div className="w-full flex items-center gap-3 bg-[#111113] border border-gray-900 rounded-lg px-3 py-3 text-sm text-white/40" data-testid={testid}>
        <span>{iconNode}</span>
        <span className="font-bold w-16 shrink-0">{label}</span>
        <span className="text-xs flex-1">{kind === "text" ? "— غير محدد —" : "— لا يوجد رابط —"}</span>
        <button type="button" onClick={onEdit} className="p-1.5 rounded-md border border-gray-800 text-white/65 hover:bg-white/5 hover:text-white">
          <Pencil size={13} />
        </button>
      </div>
    );
  }

  if (kind === "text") {
    return (
      <div data-testid={testid} className="w-full flex items-center gap-3 bg-[#111113] border border-gray-900 rounded-lg px-3 py-3 text-sm hover:border-gray-700 hover:bg-[#18181b] transition">
        <span>{iconNode}</span>
        <span className="font-bold w-16 shrink-0">{label}</span>
        <span className="text-white/80 truncate flex-1" dir="ltr">@{normalizedValue}</span>
        <button type="button" onClick={onEdit} className="p-1.5 rounded-md border border-gray-800 text-white/65 hover:bg-white/5 hover:text-white">
          <Pencil size={13} />
        </button>
      </div>
    );
  }

  return (
    <div data-testid={testid} className="w-full flex items-center gap-3 bg-[#111113] border border-gray-900 rounded-lg px-3 py-3 text-sm hover:border-gray-700 hover:bg-[#18181b] transition">
      <span>{iconNode}</span>
      <span className="font-bold w-16 shrink-0">{label}</span>
      {url ? (
        <a href={url} target="_blank" rel="noreferrer" className="text-white/70 truncate flex-1 hover:text-white">{url}</a>
      ) : (
        <span className="text-white/70 truncate flex-1">— لا يوجد رابط —</span>
      )}
      <button type="button" onClick={onEdit} className="p-1.5 rounded-md border border-gray-800 text-white/65 hover:bg-white/5 hover:text-white">
        <Pencil size={13} />
      </button>
    </div>
  );
}

async function fileToDataUrl(file) {
  return new Promise((res, rej) => {
    const fr = new FileReader();
    fr.onload = () => res(fr.result);
    fr.onerror = rej;
    fr.readAsDataURL(file);
  });
}

function MediaEditOverlay({ label = "تعديل", avatar = false }) {
  return (
    <div className="absolute inset-0 grid place-items-center bg-black/40 backdrop-blur-[2px] opacity-100 md:opacity-0 md:group-hover/banner:opacity-100 md:group-hover/avatar:opacity-100 transition-opacity duration-200">
      <span className={`inline-flex items-center gap-1.5 text-white ${avatar ? "text-sm" : "text-xs"} px-3 py-1.5 rounded-full border border-white/20 bg-black/35`}>
        <FaPenToSquare size={14} /> {label}
      </span>
    </div>
  );
}

function SingleColorPicker({ value, onChange, disabled = false }) {
  return (
    <div className="rounded-xl border border-white/10 bg-black/25 p-3" data-testid="single-color-editor">
      <div className="text-[10px] uppercase tracking-widest text-white/45 mb-2">لون الملف</div>
      <div className="flex items-center gap-3">
        <div className="h-12 w-12 rounded-lg border border-white/20" style={{ background: value }} />
        <input
          data-testid="profile-color-input"
          type="color"
          value={value}
          disabled={disabled}
          onChange={(e) => onChange?.(e.target.value)}
          className="h-12 w-20 cursor-pointer bg-transparent border-0 disabled:opacity-45"
        />
        <div className="text-xs text-white/75 font-mono">{value}</div>
      </div>
      {!disabled ? null : <div className="text-[10px] text-white/45 mt-2">تغيير اللون متاح لمشتركي Personal Plus فقط.</div>}
    </div>
  );
}

function ProfileDraftActionBar({ visible, saving, onSave, onDiscard }) {
  return (
    <div className={`fixed bottom-4 left-1/2 -translate-x-1/2 z-[999] transition-all duration-200 ${visible ? "opacity-100 translate-y-0" : "opacity-0 translate-y-8 pointer-events-none"}`}>
      <div className="rounded-2xl border border-white/15 bg-[#111113]/95 backdrop-blur-md px-4 py-3 shadow-[0_14px_35px_rgba(0,0,0,0.45)] flex items-center gap-2.5">
        <button
          type="button"
          disabled={saving}
          onClick={onSave}
          className="px-4 py-2 rounded-lg bg-emerald-500 text-black font-black hover:bg-emerald-400 shadow-[0_0_20px_rgba(16,185,129,0.45)] disabled:opacity-50"
        >
          {saving ? "..." : "حفظ التغييرات"}
        </button>
        <button
          type="button"
          disabled={saving}
          onClick={onDiscard}
          className="px-4 py-2 rounded-lg bg-gray-700 text-white font-semibold hover:bg-gray-600 disabled:opacity-50"
        >
          تجاهل
        </button>
      </div>
    </div>
  );
}
