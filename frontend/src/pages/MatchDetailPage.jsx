import { useEffect, useRef, useState, useCallback, useMemo } from "react";
import { useParams, Link } from "react-router-dom";
import api, { formatApiErrorDetail } from "../api";
import { useAuth } from "../AuthContext";
import { Send, Image as ImageIcon, Video, Shield, Flag, Lock, LogOut } from "lucide-react";
import { toast } from "sonner";
import MapsBoard from "../components/match/MapsBoard";
import ChatMessage from "../components/match/ChatMessage";

const IMG_MAX = 3_000_000;
const VID_MAX = 10_000_000;
const POLL_MS = 4000;

function readAsDataURL(file) {
  return new Promise((resolve, reject) => {
    const r = new FileReader();
    r.onload = () => resolve(r.result);
    r.onerror = reject;
    r.readAsDataURL(file);
  });
}

function MatchHeader({ match, wonA, wonB, isLeaderA, isLeaderB, onDispute, onWithdraw }) {
  return (
    <div className="bg-surface border b-soft rounded-xl p-6 md:p-8">
      <div className="flex items-center justify-between mb-6 flex-wrap gap-3">
        <div className="flex items-center gap-3">
          {match.status === "live" ? (
            <>
              <span className="live-dot" />
              <span className="text-xs uppercase tracking-widest text-destructive font-bold">مباشر</span>
            </>
          ) : (
            <span className="text-xs uppercase tracking-widest text-white/40">
              {match.withdrawn_clan_id ? "انسحاب" : "منتهية"}
            </span>
          )}
          <span className="text-xs text-white/40 mr-3">| {match.game} • BO3</span>
        </div>
        {match.status === "live" && (isLeaderA || isLeaderB) && (
          <div className="flex gap-2 flex-wrap">
            <button data-testid="withdraw-btn" onClick={onWithdraw} className="px-3 py-1.5 rounded-md border border-destructive/40 text-destructive text-sm hover:bg-destructive/10 flex items-center gap-1">
              <LogOut size={14} /> انسحاب (-3 نقاط)
            </button>
            <button data-testid="dispute-btn" onClick={onDispute} className="px-3 py-1.5 rounded-md border border-destructive/40 text-destructive text-sm hover:bg-destructive/10 flex items-center gap-1">
              <Flag size={14} /> نزاع
            </button>
          </div>
        )}
      </div>

      <div className="grid grid-cols-[1fr_auto_1fr] items-center gap-4 md:gap-8">
        <Link to={`/clans/${match.clan_a?.id}`} className="text-right group">
          <div className="text-xs text-gold-500 uppercase tracking-widest">[{match.clan_a?.tag}]</div>
          <div className="font-display font-black text-2xl md:text-4xl group-hover:text-gold-500 transition">{match.clan_a?.name}</div>
          {match.withdrawn_clan_id === match.clan_a?.id && (
            <div className="text-[10px] uppercase tracking-widest text-destructive mt-1">منسحب</div>
          )}
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
          {match.withdrawn_clan_id === match.clan_b?.id && (
            <div className="text-[10px] uppercase tracking-widest text-destructive mt-1">منسحب</div>
          )}
        </Link>
      </div>
    </div>
  );
}

function ChatComposer({ text, image, video, onText, onImage, onVideo, onClearImage, onClearVideo, onSubmit }) {
  return (
    <form onSubmit={onSubmit} className="border-t b-soft p-3 space-y-2" data-testid="chat-form">
      {(image || video) && (
        <div className="flex gap-2">
          {image && (
            <div className="relative">
              <img src={image} alt="" className="h-16 w-16 rounded object-cover border b-soft" />
              <button type="button" onClick={onClearImage} className="absolute -top-1 -right-1 bg-destructive rounded-full text-white text-xs w-4 h-4 grid place-items-center">×</button>
            </div>
          )}
          {video && (
            <div className="relative">
              <video src={video} className="h-16 w-16 rounded object-cover border b-soft" />
              <button type="button" onClick={onClearVideo} className="absolute -top-1 -right-1 bg-destructive rounded-full text-white text-xs w-4 h-4 grid place-items-center">×</button>
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
          onChange={(e) => onText(e.target.value)}
          placeholder="اكتب رسالة..."
          className="flex-1 bg-background border b-soft rounded-md px-4 py-2 outline-none focus:border-gold-500/40"
        />
        <button data-testid="send-chat" type="submit" className="px-4 py-2 rounded-md bg-gold-500 text-black hover:bg-gold-400 transition">
          <Send size={16} />
        </button>
      </div>
    </form>
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

  const loadMatch = useCallback(async () => {
    try {
      const { data } = await api.get(`/matches/${id}`);
      setMatch(data);
    } catch {
      // polling will retry
    }
  }, [id]);

  const loadChat = useCallback(async () => {
    try {
      const { data } = await api.get(`/matches/${id}/chat`);
      setMessages(data.messages);
      setCanWrite(data.can_write);
      setIsAdminFlag(data.is_admin);
      setUserClanInChat(data.user_clan_id);
    } catch {
      // 401/403 expected for guests / outsiders; polling retries
    }
  }, [id]);

  useEffect(() => {
    loadMatch();
    loadChat();
    const t = setInterval(() => { loadChat(); loadMatch(); }, POLL_MS);
    return () => clearInterval(t);
  }, [loadMatch, loadChat]);

  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [messages.length]);

  const matchClans = useMemo(
    () => ({ a: match?.clan_a?.id, b: match?.clan_b?.id }),
    [match?.clan_a?.id, match?.clan_b?.id]
  );

  const wonA = useMemo(
    () => (match?.maps?.filter((m) => m.winner === "A").length ?? 0),
    [match?.maps]
  );
  const wonB = useMemo(
    () => (match?.maps?.filter((m) => m.winner === "B").length ?? 0),
    [match?.maps]
  );

  if (!match) return <div className="text-white/40">جارٍ التحميل...</div>;

  const isLeaderA = !!(user && match.clan_a && user.clan_id === match.clan_a.id);
  const isLeaderB = !!(user && match.clan_b && user.clan_id === match.clan_b.id);

  const onImage = async (e) => {
    const f = e.target.files?.[0];
    if (!f) return;
    if (f.size > IMG_MAX) return toast.error("الصورة كبيرة (الحد 3MB)");
    setImage(await readAsDataURL(f));
  };
  const onVideo = async (e) => {
    const f = e.target.files?.[0];
    if (!f) return;
    if (f.size > VID_MAX) return toast.error("الفيديو كبير (الحد 10MB)");
    setVideo(await readAsDataURL(f));
  };

  const handleErr = (err) => toast.error(formatApiErrorDetail(err.response?.data?.detail));

  const send = async (e) => {
    e.preventDefault();
    if (!text.trim() && !image && !video) return;
    try {
      await api.post(`/matches/${id}/chat`, { text: text.trim(), image, video });
      setText(""); setImage(null); setVideo(null);
      loadChat();
    } catch (err) { handleErr(err); }
  };

  const vote = async (idx, winnerClanId) => {
    try {
      await api.post(`/matches/${id}/vote-map`, { map_index: idx, winner_clan_id: winnerClanId });
      loadMatch();
    } catch (err) { handleErr(err); }
  };

  const resolve = async (idx, winnerClanId) => {
    try {
      await api.post(`/matches/${id}/admin-resolve-map`, { map_index: idx, winner_clan_id: winnerClanId });
      toast.success("تم تحديد الفائز");
      loadMatch();
    } catch (err) { handleErr(err); }
  };

  const dispute = async () => {
    try {
      await api.post(`/matches/${id}/dispute`);
      toast.success("تم استدعاء المنظم");
      loadMatch();
    } catch (err) { handleErr(err); }
  };

  const withdraw = async () => {
    // eslint-disable-next-line no-alert
    if (!confirm("هل أنت متأكد؟ سيتم خصم 3 نقاط من كلانك وفوز الخصم.")) return;
    try {
      await api.post(`/matches/${id}/withdraw`);
      toast.success("تم الانسحاب من المباراة");
      loadMatch();
      loadChat();
    } catch (err) { handleErr(err); }
  };

  const opponentDecide = async (msgId, decision) => {
    try {
      await api.post(`/chat/${msgId}/opponent-decision`, { decision });
      toast.success(decision === "accept" ? "تم التأكيد" : "تم الرفض، سيتدخل المنظم");
      loadChat();
    } catch (err) { handleErr(err); }
  };

  const adminDecide = async (msgId, decision) => {
    let note = "";
    let finalDecision = decision;
    if (decision === "note") {
      // eslint-disable-next-line no-alert
      note = prompt("اكتب ملاحظتك:") || "";
      if (!note) return;
      finalDecision = "approve";
    }
    try {
      await api.post(`/chat/${msgId}/admin-decision`, { decision: finalDecision, note });
      loadChat();
    } catch (err) { handleErr(err); }
  };

  const isStaffOfMatch = isAdminFlag || isLeaderA || isLeaderB;

  return (
    <div className="space-y-6">
      <MatchHeader
        match={match} wonA={wonA} wonB={wonB}
        isLeaderA={isLeaderA} isLeaderB={isLeaderB}
        onDispute={dispute} onWithdraw={withdraw}
      />
      <div className="bg-surface border b-soft rounded-xl p-6 md:p-8 -mt-6">
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
              matchClans={matchClans}
            />
          ))}
        </div>

        {canWrite ? (
          <ChatComposer
            text={text} image={image} video={video}
            onText={setText} onImage={onImage} onVideo={onVideo}
            onClearImage={() => setImage(null)}
            onClearVideo={() => setVideo(null)}
            onSubmit={send}
          />
        ) : (
          <div className="border-t b-soft p-4 text-center text-white/40 text-sm flex items-center justify-center gap-2" data-testid="chat-readonly">
            <Lock size={14} /> الكتابة للقادة، النواب والمنظمين فقط
          </div>
        )}
      </div>
    </div>
  );
}
