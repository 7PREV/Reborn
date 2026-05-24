import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import api from "../api";
import { Shield, Trophy, Tv, Twitch, Sparkles, ArrowRight } from "lucide-react";

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

  const isPlus = !!u.is_personal_plus;
  const accent = (isPlus && u.accent_color) || "#FFCC00";
  const bannerStyle = isPlus && u.banner
    ? { backgroundImage: `url(${u.banner})`, backgroundSize: "cover", backgroundPosition: "center" }
    : { background: `linear-gradient(135deg, ${accent}22, transparent 80%)` };
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
              <Sparkles size={10} className="text-gold-500" />
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
                <h1 data-testid="player-act" className="font-display font-black text-3xl md:text-4xl truncate" style={{ color: accent }}>{u.act}</h1>
              ) : (
                <h1 className="font-display font-black text-3xl md:text-4xl truncate text-white/70">{u.username}</h1>
              )}
              <div className="text-white/50 text-sm mt-1">@{u.username}</div>
            </div>
            <div className="flex items-center gap-4">
              <Stat label="نقاط" value={u.points || 0} accent={accent} testid="player-points" />
              <Stat label="فوز/خسارة" value={`${wins} / ${losses}`} accent={accent} testid="player-wl" />
              <Stat label="W/L" value={Number(kd).toFixed(2)} accent={accent} testid="player-kd" />
            </div>
          </div>

          <div className="mt-6">
            <div className="text-[10px] uppercase tracking-widest text-white/40 mb-2">القنوات والحسابات</div>
            <div className="space-y-2">
              <SocialRow icon={<Twitch size={16} />} label="Twitch" url={u.twitch_url} accent={accent} testid="ply-social-twitch" />
              <SocialRow icon={<Tv size={16} />} label="Kick" url={u.kick_url} accent={accent} testid="ply-social-kick" />
              <SocialRow icon={<Tv size={16} />} label="TikTok" url={u.tiktok_url} accent={accent} testid="ply-social-tiktok" />
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

function SocialRow({ icon, label, url, accent, testid }) {
  if (!url) {
    return (
      <div className="flex items-center gap-3 bg-background/40 border b-soft rounded-md px-3 py-2 text-sm text-white/40" data-testid={testid}>
        <span style={{ color: accent }}>{icon}</span>
        <span className="font-bold w-16">{label}</span>
        <span className="text-xs">— لا يوجد رابط —</span>
      </div>
    );
  }
  return (
    <a href={url} target="_blank" rel="noreferrer" data-testid={testid} className="flex items-center gap-3 bg-background/40 border b-soft rounded-md px-3 py-2 text-sm hover:border-gold-500/40 transition">
      <span style={{ color: accent }}>{icon}</span>
      <span className="font-bold w-16">{label}</span>
      <span className="text-white/70 truncate flex-1">{url}</span>
    </a>
  );
}
