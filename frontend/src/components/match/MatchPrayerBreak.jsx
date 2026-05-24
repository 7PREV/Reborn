import { useEffect, useState } from "react";
import api, { formatApiErrorDetail } from "../../api";
import { Pause, Play, Lock } from "lucide-react";
import { toast } from "sonner";
import { useAuth } from "../../AuthContext";

const formatMs = (ms) => {
  if (ms <= 0) return "00:00";
  const total = Math.floor(ms / 1000);
  const m = String(Math.floor(total / 60)).padStart(2, "0");
  const s = String(total % 60).padStart(2, "0");
  return `${m}:${s}`;
};

export default function MatchPrayerBreak({ match, userSide, isStaff, onUpdate }) {
  const { user } = useAuth();
  const pb = match.match_prayer_break;
  const isActive = pb && !pb.resumed && pb.ends_at && new Date(pb.ends_at) > new Date();
  const userCdUntil = user?.prayer_break_cooldown_until ? new Date(user.prayer_break_cooldown_until) : null;
  const userInCooldown = userCdUntil && userCdUntil > new Date() && !isStaff;
  const [, force] = useState(0);
  useEffect(() => {
    if (!isActive && !userInCooldown) return;
    const t = setInterval(() => force((n) => n + 1), 1000);
    return () => clearInterval(t);
  }, [isActive, userInCooldown]);

  const start = async () => {
    try {
      await api.post(`/matches/${match.id}/match-prayer-break`);
      toast.success("بدأ بريك الصلاة 15 دقيقة");
      onUpdate();
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail));
    }
  };

  const resume = async () => {
    try {
      await api.post(`/matches/${match.id}/match-prayer-resume`);
      toast.success("تم استئناف المباراة");
      onUpdate();
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail));
    }
  };

  const canStart = !!userSide || isStaff;
  const canResume = isStaff || (pb && pb.started_by_clan === userSide);

  if (!isActive) {
    if (!canStart) return null;
    if (userInCooldown) {
      const mins = Math.ceil((userCdUntil - new Date()) / 60000);
      return (
        <button
          data-testid="match-prayer-locked"
          disabled
          className="px-3 py-1.5 rounded-md border border-white/10 text-white/40 text-sm flex items-center gap-1 cursor-not-allowed"
        >
          <Lock size={14} /> بريك صلاة (متاح بعد {mins}د)
        </button>
      );
    }
    return (
      <button
        data-testid="match-prayer-start"
        onClick={start}
        className="px-3 py-1.5 rounded-md border border-emerald-500/40 text-emerald-400 text-sm hover:bg-emerald-500/10 flex items-center gap-1"
      >
        <Pause size={14} /> بريك صلاة (15د)
      </button>
    );
  }

  const endsAt = new Date(pb.ends_at);
  const remaining = endsAt - new Date();

  return (
    <div data-testid="match-prayer-active" className="bg-emerald-500/5 border border-emerald-500/30 rounded-md px-3 py-1.5 flex items-center gap-2 text-sm">
      <span className="inline-block w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
      <span className="text-emerald-400 font-bold">بريك صلاة</span>
      <span className="font-mono text-gold-500" data-testid="match-prayer-remaining">{formatMs(remaining)}</span>
      {pb.started_by_username && (
        <span className="text-xs text-white/50">• بدأها {pb.started_by_username}</span>
      )}
      {canResume && (
        <button
          data-testid="match-prayer-resume"
          onClick={resume}
          className="ml-2 px-2 py-1 rounded bg-emerald-500 text-black text-xs font-bold hover:bg-emerald-400 flex items-center gap-1"
        >
          <Play size={12} /> العودة من البريك
        </button>
      )}
    </div>
  );
}
