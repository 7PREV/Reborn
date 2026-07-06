import { Crown, Star, UserMinus } from "lucide-react";

function MemberRow({ m, isClanLeader, isVice, canManage, onPromote, onKick }) {
  let label = "لاعب";
  if (isClanLeader) label = "القائد";
  else if (isVice) label = "نائب القائد";

  return (
    <div data-testid={`member-${m.id}`} className="bg-surface border b-soft rounded-lg p-4 flex items-center gap-3">
      <div className="h-10 w-10 rounded-md bg-white/5 grid place-items-center font-display text-gold-500">
        {m.username[0].toUpperCase()}
      </div>
      <div className="flex-1 min-w-0">
        <div className="font-bold truncate flex items-center gap-1">
          {m.username}
          {isClanLeader && <Crown size={14} className="text-gold-500" />}
          {isVice && <Star size={14} className="text-gold-500/70" />}
        </div>
        <div className="text-[10px] uppercase tracking-widest text-white/40">{label}</div>
      </div>
      {canManage && !isClanLeader && (
        <div className="flex gap-1">
          <button onClick={() => onPromote(m.id)} title={isVice ? "إزالة نائب" : "ترقية نائب"} className="p-1.5 rounded hover:bg-white/5 text-gold-500">
            <Star size={14} />
          </button>
          <button onClick={() => onKick(m.id)} title="طرد" className="p-1.5 rounded hover:bg-destructive/10 text-destructive">
            <UserMinus size={14} />
          </button>
        </div>
      )}
    </div>
  );
}

export default function MembersList({ members, leaderId, viceLeaderIds, canManage, onPromote, onKick }) {
  return (
    <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
      {members.map((m) => (
        <MemberRow
          key={m.id}
          m={m}
          isClanLeader={m.id === leaderId}
          isVice={viceLeaderIds.includes(m.id)}
          canManage={canManage}
          onPromote={onPromote}
          onKick={onKick}
        />
      ))}
    </div>
  );
}
