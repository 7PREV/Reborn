import { useEffect, useRef, useState } from "react";
import { useParams, Link } from "react-router-dom";
import api, { formatApiErrorDetail } from "../api";
import { useAuth } from "../AuthContext";
import {
  Send, Image as ImageIcon, Video, Crown, Star, Shield, CheckCircle, XCircle,
  Edit3, Flag, AlertTriangle, Lock,
} from "lucide-react";
import { toast } from "sonner";

function MapsBoard({ match, isLeaderA, isLeaderB, isAdmin, onVote, onResolve }) {
  return (
    <div className="grid sm:grid-cols-3 gap-3 mt-6">
      {match.maps.map((mp, idx) => {
        const winnerSide = mp.winner;
        const aWin = winnerSide === "A";
        const bWin = winnerSide === "B";
        const myVote = isLeaderA ? mp.vote_a : isLeaderB ? mp.vote_b : null;
        return (
          <div key={idx} data-testid={`map-${idx}`} className={`rounded-lg border p-4 ${
            mp.disputed ? "border-destructive/50 bg-destructive/5"
            : mp.winner ? "border-gold-500/30 bg-gold-500/5"
            : "border-white/5 bg-surface"
          }`}>
            <div className="flex items-center justify-between mb-3">
              <div className="text-xs uppercase tracking-widest text-white/40">ماب {idx + 1}</div>
              {mp.disputed && <span className="text-[10px] uppercase text-destructive font-bold flex items-center gap-1"><AlertTriangle size={10} /> نزاع</span>}
              {mp.admin_resolved && <span className="text-[10px] uppercase text-gold-500 font-bold">قرار المنظم</span>}
            </div>
            {mp.winner ? (
              <div className="text-center py-3">
                <div className="text-[10px] uppercase tracking-widest text-white/40">الفائز</div>
                <div className="font-display font-black text-xl text-gold-500 mt-1">
                  {aWin ? match.clan_a?.tag : match.clan_b?.tag}
                </div>
              </div>
            ) : (
              <div className="space-y-2">
                <div className="text-xs text-white/50 text-center mb-2">من فاز بهذا الماب؟</div>
                {(isLeaderA || isLeaderB || isAdmin) ? (
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
                    {isAdmin && (
                      <div className="mt-2 pt-2 border-t b-soft">
                        <div className="text-[10px] uppercase tracking-widest text-gold-500 mb-1">قرار المنظم</div>
                        <div className="grid grid-cols-2 gap-1">
                          <button data-testid={`admin-resolve-a-${idx}`} onClick={() => onResolve(idx, match.clan_a_id)} className="py-1.5 rounded text-xs bg-gold-500/10 text-gold-500 hover:bg-gold-500/20">{match.clan_a?.tag}</button>
                          <button data-testid={`admin-resolve-b-${idx}`} onClick={() => onResolve(idx, match.clan_b_id)} className="py-1.5 rounded text-xs bg-gold-500/10 text-gold-500 hover:bg-gold-500/20">{match.clan_b?.tag}</button>
                        </div>
                      </div>
                    )}
                  </>
                ) : (
                  <div className="text-center text-xs text-white/40 py-3">للمشاهدة فقط</div>
                )}
                {mp.vote_a && mp.vote_b && mp.vote_a !== mp.vote_b && !mp.admin_resolved && (
                  <div className="text-[10px] text-destructive text-center pt-1">اختلاف في التصويت</div>
                )}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

function ChatMessage({ m, user, isAdmin, userClanId, onOpponentDecide, onAdminDecide, matchClans }) {
  const isMine = m.user_id === user?.id;
  const tagColor = m.user_role === "admin" ? "text-gold-500" : m.user_role === "leader" ? "text-gold-400" : "text-white/70";
  const roleLabel = m.user_role === "admin" ? "منظم" : m.user_role === "leader" ? "قائد" : "نائب";
  const RoleIcon = m.user_role === "admin" ? Shield : m.user_role === "leader" ? Crown : Star;

  // Determine if current user should see opponent buttons on this image
  const showOpponentButtons = m.type === "image" && !m.opponent_decision &&
    userClanId && m.user_clan_id && userClanId !== m.user_clan_id &&
    [matchClans.a, matchClans.b].includes(userClanId);

  return (
    <div className={`flex ${isMine ? "justify-start" : "justify-end"}`}>
      <div className={`max-w-[75%] rounded-lg p-3 border ${isMine ? "bg-gold-500/10 border-gold-500/30" : "bg-background border-white/5"}`}>
        <div className={`flex items-center gap-1 text-xs mb-1 ${tagColor}`}>
          <RoleIcon size={12} />
          <span className="font-bold">{m.username}</span>
          <span className="text-white/30">• {roleLabel}</span>
        </div>

        {m.image && (
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
        )}

        {m.video && (
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
                <button data-testid={`vid-approve-${m.id}`} onClick={() => onAdminDecide(m.id, "approve")} className="px-2 py-1 rounded bg-emerald-500/10 text-emerald-400 hover:bg-emerald-500/20 flex items-center gap-1 text-xs">
                  <CheckCircle size={12} />
                </button>
                <button data-testid={`vid-reject-${m.id}`} onClick={() => onAdminDecide(m.id, "reject")} className="px-2 py-1 rounded bg-destructive/10 text-destructive hover:bg-destructive/20 flex items-center gap-1 text-xs">
                  <XCircle size={12} />
                </button>
                <button data-testid={`vid-note-${m.id}`} onClick={() => onAdminDecide(m.id, "note")} className="px-2 py-1 rounded bg-white/5 hover:bg-white/10 flex items-center gap-1 text-xs">
                  <Edit3 size={12} />
                </button>
              </div>
            )}
          </div>
        )}

        {m.text && <div className="text-sm whitespace-pre-wrap break-words">{m.text}</div>}
        <div className="text-[10px] text-white/30 mt-1">{new Date(m.created_at).toLocaleTimeString("ar")}</div>
      </div>
    </div>
  );
}

export default function MatchDetailPage() {
  const { id } = useParams();
  const { user } = useAuth();
  const [match, setMatch] = useState(null);
  const [messages, setMessages] = useState([]);
  const [canWrite, setCanWrite] = useState(false);
  const [isAdminFlag, setIsAdminFlag] = useState(false);
  const [userClanInChat, setUserClanInChat] = useState(null);
  const [text, setText] = useState("");
  const [image, setImage] = useState(null);
  const [video, setVideo] = useState(null);
  const scrollRef = useRef(null);

  const loadMatch = async () => {
    const { data } = await api.get(`/matches/${id}`);
    setMatch(data);
  };
  const loadChat = async () => {
    try {
      const { data } = await api.get(`/matches/${id}/chat`);
      setMessages(data.messages);
      setCanWrite(data.can_write);
      setIsAdminFlag(data.is_admin);
      setUserClanInChat(data.user_clan_id);
    } catch (err) {
      // silent
    }
  };

  useEffect(() => {
    loadMatch();
    loadChat();
    const t = setInterval(() => { loadChat(); loadMatch(); }, 4000);
    return () => clearInterval(t);
  }, [id]);

  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [messages.length]);

  if (!match) return <div className="text-white/40">جارٍ التحميل...</div>;

  const isLeaderA = user && match.clan_a && (user.clan_id === match.clan_a.id);
  const isLeaderB = user && match.clan_b && (user.clan_id === match.clan_b.id);
  const wonA = match.maps.filter((m) => m.winner === "A").length;
  const wonB = match.maps.filter((m) => m.winner === "B").length;

  const onImage = (e) => {
    const f = e.target.files?.[0];
    if (!f) return;
    if (f.size > 3_000_000) return toast.error("الصورة كبيرة (الحد 3MB)");
    const reader = new FileReader();
    reader.onload = () => setImage(reader.result);
    reader.readAsDataURL(f);
  };

  const onVideo = (e) => {
    const f = e.target.files?.[0];
    if (!f) return;
    if (f.size > 10_000_000) return toast.error("الفيديو كبير (الحد 10MB)");
    const reader = new FileReader();
    reader.onload = () => setVideo(reader.result);
    reader.readAsDataURL(f);
  };

  const send = async (e) => {
    e.preventDefault();
    if (!text.trim() && !image && !video) return;
    try {
      await api.post(`/matches/${id}/chat`, { text: text.trim(), image, video });
      setText(""); setImage(null); setVideo(null);
      loadChat();
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail));
    }
  };

  const vote = async (idx, winnerClanId) => {
    try {
      await api.post(`/matches/${id}/vote-map`, { map_index: idx, winner_clan_id: winnerClanId });
      loadMatch();
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail));
    }
  };

  const resolve = async (idx, winnerClanId) => {
    try {
      await api.post(`/matches/${id}/admin-resolve-map`, { map_index: idx, winner_clan_id: winnerClanId });
      toast.success("تم تحديد الفائز");
      loadMatch();
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail));
    }
  };

  const dispute = async () => {
    try {
      await api.post(`/matches/${id}/dispute`);
      toast.success("تم استدعاء المنظم");
      loadMatch();
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail));
    }
  };

  const opponentDecide = async (msgId, decision) => {
    try {
      await api.post(`/chat/${msgId}/opponent-decision`, { decision });
      toast.success(decision === "accept" ? "تم التأكيد" : "تم الرفض، سيتدخل المنظم");
      loadChat();
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail));
    }
  };

  const adminDecide = async (msgId, decision) => {
    let note = "";
    if (decision === "note") {
      note = prompt("اكتب ملاحظتك:") || "";
      if (!note) return;
      decision = "approve";  // note is a soft action
    }
    try {
      await api.post(`/chat/${msgId}/admin-decision`, { decision, note });
      loadChat();
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail));
    }
  };

  const isStaffOfMatch = isAdminFlag || isLeaderA || isLeaderB;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-surface border b-soft rounded-xl p-6 md:p-8">
        <div className="flex items-center justify-between mb-6 flex-wrap gap-3">
          <div className="flex items-center gap-3">
            {match.status === "live" ? (
              <>
                <span className="live-dot" />
                <span className="text-xs uppercase tracking-widest text-destructive font-bold">مباشر</span>
              </>
            ) : (
              <span className="text-xs uppercase tracking-widest text-white/40">منتهية</span>
            )}
            <span className="text-xs text-white/40 mr-3">| {match.game} • BO3</span>
          </div>
          {match.status === "live" && (isLeaderA || isLeaderB) && (
            <button data-testid="dispute-btn" onClick={dispute} className="px-3 py-1.5 rounded-md border border-destructive/40 text-destructive text-sm hover:bg-destructive/10 flex items-center gap-1">
              <Flag size={14} /> نزاع — استدعاء المنظم
            </button>
          )}
        </div>

        <div className="grid grid-cols-[1fr_auto_1fr] items-center gap-4 md:gap-8">
          <Link to={`/clans/${match.clan_a?.id}`} className="text-right group">
            <div className="text-xs text-gold-500 uppercase tracking-widest">[{match.clan_a?.tag}]</div>
            <div className="font-display font-black text-2xl md:text-4xl group-hover:text-gold-500 transition">{match.clan_a?.name}</div>
          </Link>
          <div className="text-center">
            <div className="font-display font-black text-4xl md:text-6xl">
              <span className={match.winner_clan_id === match.clan_a_id ? "text-gold-500" : ""}>{wonA}</span>
              <span className="text-white/30 mx-3">-</span>
              <span className={match.winner_clan_id === match.clan_b_id ? "text-gold-500" : ""}>{wonB}</span>
            </div>
            <div className="text-[10px] uppercase tracking-widest text-white/40 mt-1">أفضل من 3</div>
          </div>
          <Link to={`/clans/${match.clan_b?.id}`} className="text-left group">
            <div className="text-xs text-gold-500 uppercase tracking-widest">[{match.clan_b?.tag}]</div>
            <div className="font-display font-black text-2xl md:text-4xl group-hover:text-gold-500 transition">{match.clan_b?.name}</div>
          </Link>
        </div>

        <MapsBoard
          match={match}
          isLeaderA={isLeaderA}
          isLeaderB={isLeaderB}
          isAdmin={isAdminFlag}
          onVote={vote}
          onResolve={resolve}
        />

        {match.status === "finished" && match.winner_clan_id && (
          <div className="mt-6 text-center py-3 bg-gold-500/10 border border-gold-500/30 rounded-lg">
            <div className="text-[10px] uppercase tracking-widest text-gold-500">الفائز</div>
            <div className="font-display font-black text-2xl text-gold-500">
              {match.winner_clan_id === match.clan_a?.id ? match.clan_a?.name : match.clan_b?.name}
            </div>
          </div>
        )}
      </div>

      {/* Chat */}
      <div className="bg-surface border b-soft rounded-xl overflow-hidden">
        <div className="p-4 border-b b-soft flex items-center gap-2">
          <Shield size={18} className="text-gold-500" />
          <h2 className="font-display font-black text-lg">شات المباراة</h2>
          <span className="text-xs text-white/40 mr-auto">
            {isStaffOfMatch ? "نص + وسائط" : "وسائط فقط (للزوار)"}
          </span>
        </div>

        <div ref={scrollRef} className="h-[500px] overflow-y-auto p-4 space-y-3" data-testid="chat-messages">
          {messages.length === 0 && (
            <div className="text-center text-white/40 py-12">لا توجد رسائل بعد</div>
          )}
          {messages.map((m) => (
            <ChatMessage
              key={m.id}
              m={m}
              user={user}
              isAdmin={isAdminFlag}
              userClanId={userClanInChat}
              onOpponentDecide={opponentDecide}
              onAdminDecide={adminDecide}
              matchClans={{ a: match.clan_a?.id, b: match.clan_b?.id }}
            />
          ))}
        </div>

        {canWrite ? (
          <form onSubmit={send} className="border-t b-soft p-3 space-y-2" data-testid="chat-form">
            {(image || video) && (
              <div className="flex gap-2">
                {image && (
                  <div className="relative">
                    <img src={image} alt="" className="h-16 w-16 rounded object-cover border b-soft" />
                    <button type="button" onClick={() => setImage(null)} className="absolute -top-1 -right-1 bg-destructive rounded-full text-white text-xs w-4 h-4 grid place-items-center">×</button>
                  </div>
                )}
                {video && (
                  <div className="relative">
                    <video src={video} className="h-16 w-16 rounded object-cover border b-soft" />
                    <button type="button" onClick={() => setVideo(null)} className="absolute -top-1 -right-1 bg-destructive rounded-full text-white text-xs w-4 h-4 grid place-items-center">×</button>
                  </div>
                )}
              </div>
            )}
            <div className="flex gap-2 items-end">
              <label className="cursor-pointer p-2 rounded-md hover:bg-white/5 text-white/60" title="صورة">
                <ImageIcon size={20} />
                <input data-testid="chat-image-input" type="file" accept="image/*" onChange={onImage} className="hidden" />
              </label>
              <label className="cursor-pointer p-2 rounded-md hover:bg-white/5 text-white/60" title="فيديو">
                <Video size={20} />
                <input data-testid="chat-video-input" type="file" accept="video/*" onChange={onVideo} className="hidden" />
              </label>
              <input
                data-testid="chat-input"
                value={text}
                onChange={(e) => setText(e.target.value)}
                placeholder="اكتب رسالة..."
                className="flex-1 bg-background border b-soft rounded-md px-4 py-2 outline-none focus:border-gold-500/40"
              />
              <button data-testid="send-chat" type="submit" className="px-4 py-2 rounded-md bg-gold-500 text-black hover:bg-gold-400 transition">
                <Send size={16} />
              </button>
            </div>
          </form>
        ) : (
          <div className="border-t b-soft p-4 text-center text-white/40 text-sm flex items-center justify-center gap-2" data-testid="chat-readonly">
            <Lock size={14} /> الكتابة للقادة، النواب والمنظمين فقط
          </div>
        )}
      </div>
    </div>
  );
}
