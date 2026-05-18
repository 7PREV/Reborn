import { AlertTriangle } from "lucide-react";

export default function MapsBoard({ match, isLeaderA, isLeaderB, isAdmin, onVote, onResolve }) {
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
          onVote={onVote}
          onResolve={onResolve}
        />
      ))}
    </div>
  );
}

function MapCard({ mp, match, isLeaderA, isLeaderB, isAdmin, onVote, onResolve }) {
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
        <MapVoting
          mp={mp} idx={idx} match={match}
          canVote={canVote} isAdmin={isAdmin} myVote={myVote}
          onVote={onVote} onResolve={onResolve}
          showDisputeNote={showDisputeNote}
        />
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
