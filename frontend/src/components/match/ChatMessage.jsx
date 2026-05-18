import { Crown, Star, Shield, CheckCircle, XCircle, Edit3 } from "lucide-react";

const ROLE_META = {
  admin:  { Icon: Shield, color: "text-gold-500",  label: "منظم" },
  leader: { Icon: Crown,  color: "text-gold-400",  label: "قائد" },
  vice:   { Icon: Star,   color: "text-white/70",  label: "نائب" },
};

function ImageMediaBlock({ m, showOpponentButtons, onOpponentDecide }) {
  return (
    <div>
      <img src={m.image} alt="screenshot" className="rounded-md mb-2 max-w-full max-h-72 object-contain" />
      {m.opponent_decision && (
        <div className={`text-xs mb-2 inline-flex items-center gap-1 px-2 py-1 rounded ${
          m.opponent_decision === "accept" ? "bg-emerald-500/10 text-emerald-400" : "bg-destructive/10 text-destructive"
        }`}>
          {m.opponent_decision === "accept" ? <CheckCircle size={12} /> : <XCircle size={12} />}
          <span>{m.opponent_decision === "accept" ? "تأكيد الخصم" : "رفض الخصم — يتدخل المنظم"}</span>
        </div>
      )}
      {showOpponentButtons && (
        <div className="flex gap-1 mt-1" data-testid={`img-buttons-${m.id}`}>
          <button data-testid={`img-accept-${m.id}`} onClick={() => onOpponentDecide(m.id, "accept")} className="px-2 py-1 rounded bg-emerald-500/10 text-emerald-400 hover:bg-emerald-500/20 flex items-center gap-1 text-xs">
            <CheckCircle size={12} /> اقبل
          </button>
          <button data-testid={`img-reject-${m.id}`} onClick={() => onOpponentDecide(m.id, "reject")} className="px-2 py-1 rounded bg-destructive/10 text-destructive hover:bg-destructive/20 flex items-center gap-1 text-xs">
            <XCircle size={12} /> ارفض
          </button>
        </div>
      )}
    </div>
  );
}

function VideoMediaBlock({ m, isAdmin, onAdminDecide }) {
  return (
    <div>
      <video src={m.video} controls className="rounded-md mb-2 max-w-full max-h-72" />
      {m.admin_decision && (
        <div className={`text-xs mb-2 inline-flex items-center gap-1 px-2 py-1 rounded ${
          m.admin_decision === "approve" ? "bg-emerald-500/10 text-emerald-400" : "bg-destructive/10 text-destructive"
        }`}>
          {m.admin_decision === "approve" ? <CheckCircle size={12} /> : <XCircle size={12} />}
          <span>قرار المنظم: {m.admin_decision === "approve" ? "موافقة" : "رفض"}</span>
        </div>
      )}
      {m.admin_note && (
        <div className="text-xs text-white/60 bg-white/5 rounded p-2 mb-2 flex items-start gap-1">
          <Edit3 size={12} className="mt-0.5 text-gold-500" />
          <span>{m.admin_note}</span>
        </div>
      )}
      {isAdmin && (
        <div className="flex gap-1 mt-1" data-testid={`video-buttons-${m.id}`}>
          <button data-testid={`vid-approve-${m.id}`} onClick={() => onAdminDecide(m.id, "approve")} className="px-2 py-1 rounded bg-emerald-500/10 text-emerald-400 hover:bg-emerald-500/20 flex items-center gap-1 text-xs"><CheckCircle size={12} /></button>
          <button data-testid={`vid-reject-${m.id}`} onClick={() => onAdminDecide(m.id, "reject")} className="px-2 py-1 rounded bg-destructive/10 text-destructive hover:bg-destructive/20 flex items-center gap-1 text-xs"><XCircle size={12} /></button>
          <button data-testid={`vid-note-${m.id}`} onClick={() => onAdminDecide(m.id, "note")} className="px-2 py-1 rounded bg-white/5 hover:bg-white/10 flex items-center gap-1 text-xs"><Edit3 size={12} /></button>
        </div>
      )}
    </div>
  );
}

export default function ChatMessage({ m, user, isAdmin, userClanId, onOpponentDecide, onAdminDecide, matchClans }) {
  const isMine = m.user_id === user?.id;
  const meta = ROLE_META[m.user_role] || ROLE_META.vice;

  const showOpponentButtons =
    m.type === "image" && !m.opponent_decision &&
    userClanId && m.user_clan_id && userClanId !== m.user_clan_id &&
    [matchClans.a, matchClans.b].includes(userClanId);

  return (
    <div className={`flex ${isMine ? "justify-start" : "justify-end"}`}>
      <div className={`max-w-[75%] rounded-lg p-3 border ${isMine ? "bg-gold-500/10 border-gold-500/30" : "bg-background border-white/5"}`}>
        <div className={`flex items-center gap-1 text-xs mb-1 ${meta.color}`}>
          <meta.Icon size={12} />
          <span className="font-bold">{m.username}</span>
          <span className="text-white/30">• {meta.label}</span>
        </div>
        {m.image && (
          <ImageMediaBlock m={m} showOpponentButtons={showOpponentButtons} onOpponentDecide={onOpponentDecide} />
        )}
        {m.video && (
          <VideoMediaBlock m={m} isAdmin={isAdmin} onAdminDecide={onAdminDecide} />
        )}
        {m.text && <div className="text-sm whitespace-pre-wrap break-words">{m.text}</div>}
        <div className="text-[10px] text-white/30 mt-1">{new Date(m.created_at).toLocaleTimeString("ar")}</div>
      </div>
    </div>
  );
}
