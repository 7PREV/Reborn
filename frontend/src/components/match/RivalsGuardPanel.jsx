import { useCallback, useEffect, useMemo, useState } from "react";
import api, { formatApiErrorDetail } from "../../api";
import { Shield, ShieldAlert, Monitor, Gamepad2, Link2 } from "lucide-react";
import { toast } from "sonner";

function buildGuardWsUrl(matchId) {
  const backend = process.env.REACT_APP_BACKEND_URL || "http://localhost:8000";
  const wsBase = backend.startsWith("https://")
    ? backend.replace("https://", "wss://")
    : backend.replace("http://", "ws://");
  return `${wsBase}/api/ws/matches/${matchId}/guard`;
}

function statusChip(player) {
  if (player.status === "guard_active") {
    return <span className="text-[10px] px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">🟢 Rivals Guard Active</span>;
  }
  if (player.status === "console_validated") {
    return <span className="text-[10px] px-2 py-0.5 rounded bg-sky-500/20 text-sky-300 border border-sky-500/30">🎮 Console Validated</span>;
  }
  return <span className="text-[10px] px-2 py-0.5 rounded bg-destructive/15 text-destructive border border-destructive/40">🔴 Rivals Guard Inactive</span>;
}

export default function RivalsGuardPanel({ matchId, user, isStaff, onStatusChange }) {
  const [status, setStatus] = useState({ players: [], all_pc_ready: true, pc_required_count: 0, pc_ready_count: 0 });
  const [connecting, setConnecting] = useState(false);

  const load = useCallback(async () => {
    try {
      const { data } = await api.get(`/matches/${matchId}/guard/status`);
      setStatus(data || { players: [], all_pc_ready: true, pc_required_count: 0, pc_ready_count: 0 });
      onStatusChange?.(data || null);
    } catch {
      // silent polling fallback
    }
  }, [matchId, onStatusChange]);

  useEffect(() => {
    load();
    const t = setInterval(load, 4000);
    return () => clearInterval(t);
  }, [load]);

  useEffect(() => {
    const wsUrl = buildGuardWsUrl(matchId);
    let ws;
    try {
      ws = new WebSocket(wsUrl);
    } catch {
      return undefined;
    }

    ws.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data || "{}");
        if (payload.event === "guard_status") {
          setStatus({
            players: payload.players || [],
            all_pc_ready: !!payload.all_pc_ready,
            pc_required_count: Number(payload.pc_required_count || 0),
            pc_ready_count: Number(payload.pc_ready_count || 0),
          });
          onStatusChange?.(payload);
        }
        if (payload.event === "guard_red_alert") {
          toast.error(`🚨 Red Alert: ${payload.title || "Guard Alert"}`);
        }
      } catch {
        // ignore malformed packet
      }
    };

    const heartbeat = setInterval(() => {
      if (ws && ws.readyState === WebSocket.OPEN) ws.send("ping");
    }, 12000);

    return () => {
      clearInterval(heartbeat);
      if (ws && ws.readyState <= 1) ws.close();
    };
  }, [matchId, onStatusChange]);

  const myPlatform = useMemo(() => {
    const p = (user?.gaming_platform || "pc").toLowerCase();
    if (["ps5", "xbox", "console"].includes(p)) return p;
    return "pc";
  }, [user?.gaming_platform]);

  const launchGuard = async () => {
    setConnecting(true);
    try {
      const { data } = await api.get(`/guard/launcher-link/${matchId}`);
      if (data?.uri) {
        window.location.href = data.uri;
      }
      await api.post("/guard/session/connect", {
        match_id: matchId,
        platform: myPlatform,
        session_token: data?.session_token || "",
        app_version: "web-bridge-1.0",
      });
      toast.success("تم ربط Rivals Guard");
      load();
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail));
    } finally {
      setConnecting(false);
    }
  };

  const myNeedsGuard = myPlatform === "pc";
  const guardReadyText = `${status.pc_ready_count}/${status.pc_required_count}`;

  return (
    <div className="bg-surface border b-soft rounded-xl p-4 space-y-3" data-testid="rivals-guard-panel">
      <div className="flex items-center gap-2">
        {status.all_pc_ready ? <Shield className="text-emerald-400" size={18} /> : <ShieldAlert className="text-destructive" size={18} />}
        <h3 className="font-display font-black text-base">Rivals Guard Lobby</h3>
        <span className={`text-xs px-2 py-0.5 rounded border ${status.all_pc_ready ? "text-emerald-300 border-emerald-500/30 bg-emerald-500/10" : "text-destructive border-destructive/40 bg-destructive/10"}`}>
          PC Ready: {guardReadyText}
        </span>
      </div>

      {!status.all_pc_ready && (
        <div className="text-xs rounded-md border border-destructive/35 bg-destructive/10 text-destructive px-3 py-2">
          لا يمكن بدء/متابعة الجولة حتى تصبح حماية كل لاعبي PC فعّالة.
        </div>
      )}

      {myNeedsGuard && (
        <button
          onClick={launchGuard}
          disabled={connecting}
          className="px-3 py-1.5 rounded-md bg-emerald-500 text-black text-sm font-bold hover:bg-emerald-400 flex items-center gap-1 disabled:opacity-60"
          data-testid="guard-launch-btn"
        >
          <Link2 size={14} /> {connecting ? "جاري الربط..." : "تشغيل Rivals Guard"}
        </button>
      )}

      <div className="space-y-2 max-h-56 overflow-y-auto">
        {(status.players || []).map((p) => (
          <div key={p.user_id} className="flex items-center gap-2 rounded-md border b-soft bg-background px-3 py-2 text-sm">
            <div className="flex-1 min-w-0">
              <div className="font-bold truncate">{p.username}</div>
              <div className="text-[10px] text-white/45">{p.side ? `Team ${p.side}` : "Lobby"}</div>
            </div>
            <div className="text-white/60">
              {p.platform === "pc" ? <Monitor size={14} /> : <Gamepad2 size={14} />}
            </div>
            {statusChip(p)}
          </div>
        ))}
        {(status.players || []).length === 0 && (
          <div className="text-xs text-white/45">لا توجد بيانات حماية حالياً.</div>
        )}
      </div>

      {isStaff && (
        <div className="text-[10px] text-white/45">تنبيه: عند اكتشاف تهديد، سيرسل النظام Red Alert فقط بدون حظر تلقائي.</div>
      )}
    </div>
  );
}
