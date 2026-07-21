import { useMemo, useState } from "react";
import { Bot, Send, X } from "lucide-react";
import api, { formatApiErrorDetail } from "../../api";
import { useAuth } from "../../AuthContext";

function nowLabel() {
  const d = new Date();
  return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}

export default function SanadChatWidget({ matchId, disabled, onSynced }) {
  const { user } = useAuth();
  const [open, setOpen] = useState(false);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [messages, setMessages] = useState([
    {
      id: "welcome",
      from: "bot",
      text: "أنا سند 🤖. اكتب سؤالك عن القوانين، النقاط، الشات، أو الصلاة.",
      at: nowLabel(),
    },
  ]);

  const canAsk = useMemo(() => !!matchId && !disabled, [matchId, disabled]);

  const send = async (e) => {
    e.preventDefault();
    const raw = (input || "").trim();
    if (!raw || sending || !canAsk) return;

    const question = raw.includes("سند") || raw.toLowerCase().includes("sanad") ? raw : `سند ${raw}`;
    const mine = {
      id: `u-${Date.now()}`,
      from: "user",
      text: question,
      at: nowLabel(),
    };
    setMessages((prev) => [...prev, mine]);
    setInput("");
    setSending(true);

    try {
      const { data } = await api.post(`/matches/${matchId}/sanad/ask`, { question });
      const answer = data?.answer || "تم استلام سؤالك.";
      setMessages((prev) => [
        ...prev,
        {
          id: `b-${Date.now()}`,
          from: "bot",
          text: answer,
          at: nowLabel(),
        },
      ]);
      if (onSynced) onSynced();
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        {
          id: `e-${Date.now()}`,
          from: "bot",
          text: formatApiErrorDetail(err.response?.data?.detail) || "تعذر الرد حالياً.",
          at: nowLabel(),
        },
      ]);
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="fixed bottom-5 left-5 z-[100]" dir="rtl" data-testid="sanad-widget-root">
      {open && (
        <div className="mb-3 w-[min(92vw,360px)] rounded-2xl border border-emerald-500/25 bg-[#0f1116]/95 shadow-[0_18px_60px_rgba(0,0,0,0.45)] overflow-hidden">
          <div className="flex items-center justify-between px-3 py-2 border-b border-white/10 bg-emerald-500/10">
            <div className="flex items-center gap-2 text-emerald-300">
              <Bot size={16} />
              <span className="text-sm font-bold">سند الذكي</span>
            </div>
            <button onClick={() => setOpen(false)} className="text-white/60 hover:text-white" data-testid="sanad-widget-close">
              <X size={16} />
            </button>
          </div>

          <div className="h-72 overflow-y-auto p-3 space-y-2">
            {messages.map((m) => (
              <div key={m.id} className={`max-w-[88%] rounded-xl px-3 py-2 text-sm ${m.from === "user" ? "mr-auto bg-gold-500/20 border border-gold-500/30" : "ml-auto bg-white/5 border border-white/10"}`}>
                <div className="leading-6 text-white/90">{m.text}</div>
                <div className="text-[10px] text-white/40 mt-1">{m.from === "user" ? user?.username || "أنت" : "سند"} • {m.at}</div>
              </div>
            ))}
          </div>

          <form onSubmit={send} className="border-t border-white/10 p-2 flex items-center gap-2">
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder={canAsk ? "اسأل سند..." : "سند متاح فقط لأطراف المباراة"}
              disabled={!canAsk || sending}
              data-testid="sanad-widget-input"
              className="flex-1 rounded-md border border-white/15 bg-black/20 px-3 py-2 text-sm outline-none focus:border-emerald-400/60 disabled:opacity-60"
            />
            <button
              type="submit"
              disabled={!canAsk || sending || !input.trim()}
              data-testid="sanad-widget-send"
              className="px-3 py-2 rounded-md bg-emerald-500 text-black hover:bg-emerald-400 disabled:opacity-50"
            >
              <Send size={15} />
            </button>
          </form>
        </div>
      )}

      <button
        onClick={() => setOpen((v) => !v)}
        data-testid="sanad-widget-toggle"
        className="h-12 px-4 rounded-full bg-emerald-500 text-black font-bold shadow-[0_0_25px_rgba(16,185,129,0.5)] hover:bg-emerald-400 inline-flex items-center gap-2"
      >
        <Bot size={17} /> سند
      </button>
    </div>
  );
}
