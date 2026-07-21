import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import api from "../api";
import { Shield, Trophy, Sparkles, ArrowRight, Check, Flame, Swords } from "lucide-react";
import { FaTwitch, FaYoutube, FaTiktok, FaInstagram, FaXTwitter, FaDiscord } from "react-icons/fa6";
import { SiKick } from "react-icons/si";

const SOCIAL_PLATFORMS = [
  { key: "twitch_url", label: "Twitch", testid: "ply-social-twitch", Icon: FaTwitch, color: "#a970ff" },
  { key: "kick_url", label: "Kick", testid: "ply-social-kick", Icon: SiKick, color: "#53fc18" },
  { key: "youtube_url", label: "YouTube", testid: "ply-social-youtube", Icon: FaYoutube, color: "#ff0000" },
  { key: "tiktok_url", label: "TikTok", testid: "ply-social-tiktok", Icon: FaTiktok, color: "#ffffff" },
  { key: "instagram_link", label: "Instagram", testid: "ply-social-instagram", Icon: FaInstagram, color: "#e1306c" },
  { key: "x_link", label: "X", testid: "ply-social-x", Icon: FaXTwitter, color: "#ffffff" },
];

export default function PlayerProfilePage() {
  const { id } = useParams();
  const [u, setU] = useState(null);
  const [notFound, setNotFound] = useState(false);

  useEffect(() => {
    api.get(`/users/${id}`).then((r) => setU(r.data)).catch(() => setNotFound(true));
  }, [id]);

  if (notFound) {
    return <div data-testid="player-not-found" className="bg-surface border b-soft rounded-xl p-12 text-center text-white/40">اللاعب غير موجود</div>;
  }
  if (!u) return null;

  const isPlus = !!(u.is_personal_plus || u.is_plus || u.plan === "plus");
  const accent = (isPlus && u.accent_color) || "#FFCC00";
  const bannerStyle = isPlus && u.banner
    ? { backgroundImage: `url(${u.banner})`, backgroundSize: "cover", backgroundPosition: "center" }
    : { backgroundColor: accent };
  const initial = (u.username?.[0] || "?").toUpperCase();
  const wins = u.wins || 0;
  const losses = u.losses || 0;
  const kd = u.kd != null ? u.kd : (losses === 0 ? wins.toFixed(2) : (wins / losses).toFixed(2));

  return (
    <div className="space-y-6">
      <div data-testid="player-profile" className="rounded-2xl overflow-hidden border b-soft bg-surface">
        <div className="h-44 md:h-52 w-full relative" style={bannerStyle}>
          <div className="absolute inset-0 bg-gradient-to-t from-background via-background/40 to-transparent" />
          {isPlus && (
            <div className="absolute top-3 left-3 inline-flex items-center gap-1 text-[10px] uppercase tracking-widest bg-black/40 backdrop-blur px-2 py-1 rounded">
              <Sparkles size={10} className="text-[#d4af37] drop-shadow-[0_0_8px_rgba(212,175,55,0.55)]" />
              <span className="text-gold-500">Personal Plus</span>
            </div>
          )}
        </div>
        <div className="px-6 md:px-8 pb-6 -mt-12 relative">
          <div className="flex items-end gap-4 flex-wrap">
            <div
              data-testid="player-avatar"
              className="h-24 w-24 md:h-28 md:w-28 rounded-full border-4 border-background grid place-items-center overflow-hidden text-3xl font-display font-black"
              style={{
                backgroundColor: isPlus && u.avatar ? "transparent" : `${accent}22`,
                color: accent,
                boxShadow: `0 0 0 2px ${accent}55`,
              }}
            >
              {isPlus && u.avatar ? <img src={u.avatar} alt={u.username} className="h-full w-full object-cover" /> : initial}
            </div>
            <div className="flex-1 min-w-0">
              {u.act ? (
                <h1 data-testid="player-act" className="font-display font-black text-2xl sm:text-3xl md:text-4xl leading-tight break-all whitespace-normal" style={{ color: accent }}>{u.act}</h1>
              ) : (
                <h1 className="font-display font-black text-2xl sm:text-3xl md:text-4xl leading-tight break-all whitespace-normal text-white/70">{u.username}</h1>
              )}
              <div className="text-white/50 text-sm mt-1">@{u.username}</div>
              {!!u.discord_username && (
                <div className="text-white/65 text-xs mt-1 inline-flex items-center gap-1.5" dir="ltr" data-testid="player-discord-username">
                  <FaDiscord size={13} color="#5865F2" /> @{String(u.discord_username).replace(/^@+/, "")}
                </div>
              )}
            </div>
            <div className="flex items-center gap-4">
              <Stat label="نقاط" value={u.points || 0} accent={accent} testid="player-points" />
              <Stat label="فوز/خسارة" value={`${wins} / ${losses}`} accent={accent} testid="player-wl" />
              <Stat label="W/L" value={Number(kd).toFixed(2)} accent={accent} testid="player-kd" />
            </div>
          </div>

          <div className="mt-6 grid lg:grid-cols-[1.2fr_1fr] gap-4">
            <div>
              <div className="text-[10px] uppercase tracking-widest text-white/40 mb-2">الإنجازات</div>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-2" data-testid="player-achievements">
                <AchievementBadge icon={<Check size={14} />} label="عدد مرات التحضير" value={u.attendances || 0} accent={accent} tone="silver" />
                <AchievementBadge icon={<Trophy size={14} />} label="نجم المباراة" value={u.mvp_count || 0} accent={accent} tone="gold" />
                <AchievementBadge icon={<Swords size={14} />} label="Wins" value={wins} accent={accent} tone="bronze" />
                <AchievementBadge icon={<Flame size={14} />} label="Losses" value={losses} accent={accent} tone="danger" />
              </div>
            </div>
            <div>
              <div className="text-[10px] uppercase tracking-widest text-white/40 mb-2">القنوات والحسابات</div>
              <div className="space-y-2">
                {SOCIAL_PLATFORMS.map((p) => (
                  <SocialRow key={p.key} platform={p} url={u?.[p.key] || ""} />
                ))}
              </div>
            </div>
          </div>

          {u.clan_id && (
            <Link to={`/clans/${u.clan_id}`} className="inline-flex items-center gap-2 mt-6 text-sm text-gold-500 hover:text-gold-400">
              <Shield size={16} /> اذهب إلى صفحة الكلان <ArrowRight size={14} />
            </Link>
          )}
        </div>
      </div>
      {u.role !== "player" && (
        <div className="bg-surface border b-soft rounded-lg p-3 flex items-center gap-2 text-sm">
          <Trophy size={14} className="text-gold-500" />
          <span className="text-white/60">الدور:</span>
          <span className="font-bold text-gold-500">{u.role === "owner" ? "المالك" : "منظم"}</span>
        </div>
      )}
    </div>
  );
}

function Stat({ label, value, accent, testid }) {
  return (
    <div className="text-center" data-testid={testid}>
      <div className="font-display font-black text-2xl" style={{ color: accent }}>{value}</div>
      <div className="text-[10px] uppercase tracking-widest text-white/40">{label}</div>
    </div>
  );
}

function SocialRow({ platform, url }) {
  const { Icon, label, color, testid } = platform;
  const iconNode = <Icon size={16} color={color} />;
  if (!url) {
    return (
      <div className="w-full flex items-center gap-3 bg-[#111113] border border-gray-900 rounded-lg px-3 py-3 text-sm text-white/40" data-testid={testid}>
        <span>{iconNode}</span>
        <span className="font-bold w-16 shrink-0">{label}</span>
        <span className="text-xs">— لا يوجد رابط —</span>
      </div>
    );
  }
  return (
    <a href={url} target="_blank" rel="noreferrer" data-testid={testid} className="w-full flex items-center gap-3 bg-[#111113] border border-gray-900 rounded-lg px-3 py-3 text-sm hover:border-gray-700 hover:bg-[#18181b] transition">
      <span>{iconNode}</span>
      <span className="font-bold w-16 shrink-0">{label}</span>
      <span className="text-white/70 truncate flex-1">{url}</span>
      <span className="text-royalGold-400 text-xs">فتح</span>
    </a>
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
