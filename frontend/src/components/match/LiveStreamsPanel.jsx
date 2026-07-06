import { useEffect, useState } from "react";
import api from "../../api";
import { Tv } from "lucide-react";

export default function LiveStreamsPanel({ matchId }) {
  const [streams, setStreams] = useState([]);

  useEffect(() => {
    let alive = true;
    const load = async () => {
      try {
        const { data } = await api.get(`/matches/${matchId}/live-streams`);
        if (alive) setStreams(data || []);
      } catch {
        // benign
      }
    };
    load();
    const t = setInterval(load, 60000); // re-check every 60s
    return () => { alive = false; clearInterval(t); };
  }, [matchId]);

  if (!streams || streams.length === 0) {
    return (
      <div data-testid="live-streams-empty" className="bg-surface border b-soft rounded-xl p-4 text-xs text-white/40">
        <div className="flex items-center gap-2 mb-2">
          <Tv size={14} className="text-white/40" />
          <span className="font-display font-bold text-sm">البث المباشر</span>
        </div>
        لا يوجد بث مباشر حاليًا للاعبين.
      </div>
    );
  }

  return (
    <div data-testid="live-streams-panel" className="bg-surface border b-soft rounded-xl p-4 space-y-3">
      <div className="flex items-center gap-2">
        <Tv size={14} className="text-destructive" />
        <span className="font-display font-bold text-sm">على الهواء الآن ({streams.length})</span>
      </div>
      {streams.map((s) => (
        <a
          key={`${s.user_id}-${s.platform}`}
          href={s.url}
          target="_blank"
          rel="noreferrer"
          data-testid={`live-stream-${s.user_id}-${s.platform}`}
          className="block bg-background border b-soft rounded-md overflow-hidden hover:border-destructive/40 transition"
        >
          <div className="relative">
            {s.thumbnail ? (
              <img src={s.thumbnail} alt={s.title || s.username} className="w-full aspect-video object-cover" />
            ) : (
              <div className="w-full aspect-video bg-black/40 grid place-items-center text-white/30 text-xs">{s.platform}</div>
            )}
            <span className="absolute top-2 right-2 text-[10px] uppercase tracking-widest bg-destructive text-white px-1.5 py-0.5 rounded flex items-center gap-1">
              <span className="inline-block w-1.5 h-1.5 rounded-full bg-white animate-pulse" /> Live
            </span>
            <span className="absolute top-2 left-2 text-[10px] uppercase tracking-widest bg-black/60 text-white px-1.5 py-0.5 rounded">
              {s.platform}
            </span>
          </div>
          <div className="p-2">
            <div className="text-xs font-bold truncate">{s.username}</div>
            {s.title && <div className="text-[10px] text-white/50 truncate">{s.title}</div>}
            {typeof s.viewer_count === "number" && (
              <div className="text-[10px] text-white/40 mt-0.5">{s.viewer_count} مشاهد</div>
            )}
          </div>
        </a>
      ))}
    </div>
  );
}
