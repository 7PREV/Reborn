import { AlertTriangle, Hourglass, Pause, Trophy } from "lucide-react";
import { useEffect, useState } from "react";

const formatRemaining = (ms) => {
  if (ms <= 0) return "00:00";
  const total = Math.floor(ms / 1000);
  const m = String(Math.floor(total / 60)).padStart(2, "0");
  const s = String(total % 60).padStart(2, "0");
  return `${m}:${s}`;
};

function TimerBar({ mp, userSide, onGrace, onPrayer, onClaim }) {
  const state = mp.grace_state || {};
  const [, force] = useState(0);
  useEffect(() => {
    if (!state.active) return;
    const t = setInterval(() => force((n) => n + 1), 1000);
    return () => clearInterval(t);
  }, [state.active]);

  const endsAt = state.ends_at ? new Date(state.ends_at) : null;
  const remaining = endsAt ? endsAt - new Date() : 0;
  const expired = state.active && !state.paused && remaining <= 0;
  const isClaimer = userSide && state.started_by === userSide;
  const isOpponent = userSide && state.started_by && state.started_by !== userSide;
  const opponentAlreadyPrayed =
    isOpponent && (mp.prayer_used_by_clan || []).includes(userSide);

  return (
    <div className="mt-2 pt-2 border-t b-soft space-y-2" data-testid={`timer-${mp.index}`}>
      {!state.active && userSide && (
        <button
          data-testid={`grace-start-${mp.index}`}
          onClick={() => onGrace(mp.index)}
          className="w-full py-1.5 rounded text-xs bg-destructive/10 text-destructive hover:bg-destructive/20 flex items-center justify-center gap-1"
        >
          <Hourglass size={12} /> بدء مهلة الانتظار (10 دقائق)
        </button>
      )}
      {state.active && (
        <div className="bg-background border b-soft rounded-md p-2 space-y-1">
          <div className="flex items-center justify-between text-[10px] uppercase tracking-widest text-white/40">
            <span className="flex items-center gap-1 text-destructive">
              <Hourglass size={10} /> مهلة الانتظار
            </span>
            <span className="text-gold-500 font-bold text-xs" data-testid={`timer-remaining-${mp.index}`}>
              {state.paused ? "موقوف" : formatRemaining(remaining)}
            </span>
          </div>
          <div className="text-[10px] text-white/50">
            بدأها كلان {state.started_by} • {state.paused ? "هناك استراحة صلاة" : `تنتهي ${endsAt?.toLocaleTimeString("ar")}`}
          </div>
          {isOpponent && !state.paused && !opponentAlreadyPrayed && (
            <button
              data-testid={`prayer-start-${mp.index}`}
              onClick={() => onPrayer(mp.index)}
              className="w-full py-1 rounded text-xs bg-white/5 hover:bg-white/10 flex items-center justify-center gap-1"
            >
              <Pause size={11} /> استراحة صلاة (10 دقائق)
            </button>
          )}
          {expired && isClaimer && (
            <button
              data-testid={`claim-win-${mp.index}`}
              onClick={() => onClaim(mp.index)}
              className="w-full py-1.5 rounded text-xs bg-gold-500 text-black font-bold hover:bg-gold-400 flex items-center justify-center gap-1"
            >
              <Trophy size={12} /> طالب بالفوز التلقائي
            </button>
          )}
        </div>
      )}
    </div>
  );
}

export default function MapsBoard({ match, isLeaderA, isLeaderB, isAdmin, userSide, onVote, onResolve, onGrace, onPrayer, onClaim }) {
  return (
    <div className="grid sm:grid-cols-3 gap-3 mt-6">
      {match.maps.map((mp) => (
        <MapCard
          key={mp.index}
          mp={mp}
          match={match}
          isLeaderA={isLeaderA}
          isLeaderB={isLeaderB}
          isAdmin={isAdmin}
          userSide={userSide}
          onVote={onVote}
          onResolve={onResolve}
          onGrace={onGrace}
          onPrayer={onPrayer}
          onClaim={onClaim}
        />
      ))}
    </div>
  );
}

function MapCard({ mp, match, isLeaderA, isLeaderB, isAdmin, userSide, onVote, onResolve, onGrace, onPrayer, onClaim }) {
  const idx = mp.index;
  const myVote = isLeaderA ? mp.vote_a : isLeaderB ? mp.vote_b : null;
  const canVote = isLeaderA || isLeaderB;
  const showDisputeNote = mp.vote_a && mp.vote_b && mp.vote_a !== mp.vote_b && !mp.admin_resolved;

  let containerStyle = "border-white/5 bg-surface";
  if (mp.disputed) containerStyle = "border-destructive/50 bg-destructive/5";
  else if (mp.winner) containerStyle = "border-gold-500/30 bg-gold-500/5";

  return (
    <div data-testid={`map-${idx}`} className={`rounded-lg border p-4 ${containerStyle}`}>
      <MapHeader mp={mp} idx={idx} />
      {mp.winner ? (
        <MapWinner mp={mp} match={match} />
      ) : (
        <>
          <MapVoting
            mp={mp} idx={idx} match={match}
            canVote={canVote} isAdmin={isAdmin} myVote={myVote}
            onVote={onVote} onResolve={onResolve}
            showDisputeNote={showDisputeNote}
          />
          {match.status === "live" && (canVote || isAdmin) && (
            <TimerBar mp={mp} userSide={userSide} onGrace={onGrace} onPrayer={onPrayer} onClaim={onClaim} />
          )}
        </>
      )}
    </div>
  );
}

function MapHeader({ mp, idx }) {
  return (
    <div className="flex items-center justify-between mb-3">
      <div className="text-xs uppercase tracking-widest text-white/40">ماب {idx + 1}</div>
      {mp.disputed && (
        <span className="text-[10px] uppercase text-destructive font-bold flex items-center gap-1">
          <AlertTriangle size={10} /> نزاع
        </span>
      )}
      {mp.admin_resolved && (
        <span className="text-[10px] uppercase text-gold-500 font-bold">قرار المنظم</span>
      )}
    </div>
  );
}

function MapWinner({ mp, match }) {
  return (
    <div className="text-center py-3">
      <div className="text-[10px] uppercase tracking-widest text-white/40">الفائز</div>
      <div className="font-display font-black text-xl text-gold-500 mt-1">
        {mp.winner === "A" ? match.clan_a?.tag : match.clan_b?.tag}
      </div>
    </div>
  );
}

function MapVoting({ mp, idx, match, canVote, isAdmin, myVote, onVote, onResolve, showDisputeNote }) {
  if (!canVote && !isAdmin) {
    return <div className="text-center text-xs text-white/40 py-3">للمشاهدة فقط</div>;
  }
  return (
    <div className="space-y-2">
      <div className="text-xs text-white/50 text-center mb-2">من فاز بهذا الماب؟</div>
      {canVote && (
        <>
          <button
            data-testid={`vote-a-${idx}`}
            onClick={() => onVote(idx, match.clan_a_id)}
            className={`w-full py-2 rounded text-sm transition ${
              myVote === "A" ? "bg-gold-500 text-black font-bold" : "bg-white/5 hover:bg-white/10"
            }`}
          >
            {match.clan_a?.tag}
          </button>
          <button
            data-testid={`vote-b-${idx}`}
            onClick={() => onVote(idx, match.clan_b_id)}
            className={`w-full py-2 rounded text-sm transition ${
              myVote === "B" ? "bg-gold-500 text-black font-bold" : "bg-white/5 hover:bg-white/10"
            }`}
          >
            {match.clan_b?.tag}
          </button>
        </>
      )}
      {isAdmin && (
        <div className="mt-2 pt-2 border-t b-soft">
          <div className="text-[10px] uppercase tracking-widest text-gold-500 mb-1">قرار المنظم</div>
          <div className="grid grid-cols-2 gap-1">
            <button data-testid={`admin-resolve-a-${idx}`} onClick={() => onResolve(idx, match.clan_a_id)} className="py-1.5 rounded text-xs bg-gold-500/10 text-gold-500 hover:bg-gold-500/20">{match.clan_a?.tag}</button>
            <button data-testid={`admin-resolve-b-${idx}`} onClick={() => onResolve(idx, match.clan_b_id)} className="py-1.5 rounded text-xs bg-gold-500/10 text-gold-500 hover:bg-gold-500/20">{match.clan_b?.tag}</button>
          </div>
        </div>
      )}
      {showDisputeNote && (
        <div className="text-[10px] text-destructive text-center pt-1">اختلاف في التصويت</div>
      )}
    </div>
  );
}
