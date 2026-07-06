import { useEffect, useState, useCallback } from "react";
import { Link } from "react-router-dom";
import api, { formatApiErrorDetail } from "../api";
import { useAuth } from "../AuthContext";
import { Trophy, Plus, Crown, Sparkles } from "lucide-react";
import { toast } from "sonner";

function StatusBadge({ status }) {
  const map = {
    registration: { label: "تسجيل مفتوح", cls: "bg-emerald-500/10 text-emerald-400" },
    live: { label: "جارية", cls: "bg-destructive/10 text-destructive animate-pulse-glow border border-royalGold-500/30 shadow-[0_0_10px_rgba(203,213,225,0.2)]" },
    finished: { label: "منتهية", cls: "bg-white/5 text-white/60" },
  };
  const m = map[status] || map.finished;
  return <span className={`text-[10px] uppercase tracking-widest px-2 py-1 rounded ${m.cls}`}>{m.label}</span>;
}

function CreateTournamentModal({ onClose, onCreated }) {
  const [form, setForm] = useState({ name: "", description: "", rules: "", max_participants: 8, losers_bracket: false });
  const submit = async (e) => {
    e.preventDefault();
    try {
      const { data } = await api.post("/tournaments", form);
      toast.success("تم إنشاء البطولة");
      onCreated(data);
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail));
    }
  };
  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-black/70 backdrop-blur-xl p-4">
      <form onSubmit={submit} className="bg-surface border b-soft rounded-xl p-6 w-full max-w-lg space-y-4" data-testid="create-tournament-form">
        <h2 className="font-display font-black text-2xl">بطولة خروج المغلوب</h2>
        <input
          data-testid="t-name-input"
          required minLength={2} maxLength={80}
          value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })}
          placeholder="اسم البطولة"
          className="w-full bg-background border b-soft rounded-md px-4 py-3 outline-none focus:border-gold-500/40"
        />
        <textarea
          value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })}
          placeholder="وصف البطولة"
          rows={2}
          className="w-full bg-background border b-soft rounded-md px-4 py-3 outline-none focus:border-gold-500/40 resize-none"
        />
        <textarea
          data-testid="t-rules-input"
          value={form.rules} onChange={(e) => setForm({ ...form, rules: e.target.value })}
          placeholder="قوانين البطولة"
          rows={3}
          className="w-full bg-background border b-soft rounded-md px-4 py-3 outline-none focus:border-gold-500/40 resize-none"
        />
        <div>
          <label className="text-xs uppercase tracking-widest text-white/50 mb-2 block">عدد الكلانات</label>
          <select
            data-testid="t-size-select"
            value={form.max_participants}
            onChange={(e) => setForm({ ...form, max_participants: Number(e.target.value) })}
            className="w-full bg-background border b-soft rounded-md px-4 py-3 outline-none"
          >
            {[2, 4, 8, 12, 16].map((n) => <option key={n} value={n}>{n} كلان</option>)}
          </select>
        </div>
        <label className="flex items-center gap-2 cursor-pointer text-sm">
          <input
            data-testid="t-losers-bracket"
            type="checkbox"
            checked={form.losers_bracket}
            onChange={(e) => setForm({ ...form, losers_bracket: e.target.checked })}
            className="accent-gold-500 h-4 w-4"
          />
          <span>تفعيل نظام الفرصة الثانية (Losers Bracket)</span>
        </label>
        <p className="text-xs text-white/50">أول 24 ساعة: تسجيل الكلانات Plus فقط، ثم يفتح للجميع.</p>
        <div className="flex gap-2 justify-end">
          <button type="button" onClick={onClose} className="px-4 py-2 rounded-md hover:bg-white/5">إلغاء</button>
          <button data-testid="submit-tournament" type="submit" className="px-5 py-2 rounded-md bg-gold-500 text-black font-bold hover:bg-gold-400">إطلاق</button>
        </div>
      </form>
    </div>
  );
}

export default function TournamentsPage() {
  const { user } = useAuth();
  const [list, setList] = useState([]);
  const [showCreate, setShowCreate] = useState(false);

  const load = useCallback(async () => {
    const { data } = await api.get("/tournaments");
    setList(data);
  }, []);

  useEffect(() => { load(); }, [load]);

  const isStaff = user && (user.role === "admin" || user.role === "owner");

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <div>
          <h1 className="font-display font-black text-3xl md:text-4xl flex items-center gap-3">
            <Trophy className="text-gold-500" /> البطولات
          </h1>
          <p className="text-white/50 mt-1">خروج المغلوب • Call of Duty</p>
        </div>
        {isStaff && (
          <button data-testid="create-tournament-btn" onClick={() => setShowCreate(true)} className="px-5 py-3 rounded-md bg-gold-500 text-black font-bold hover:bg-gold-400 flex items-center gap-2">
            <Plus size={18} /> بطولة جديدة
          </button>
        )}
      </div>

      <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {list.map((t) => {
          const now = new Date();
          const plusUntil = new Date(t.plus_window_until);
          const plusOnly = t.status === "registration" && now < plusUntil;
          return (
            <Link key={t.id} to={`/tournaments/${t.id}`} data-testid={`tournament-${t.id}`} className="bg-surface border b-soft rounded-lg p-5 hover:border-gold-500/30 transition fade-in animate-float-up">
              <div className="flex items-center justify-between mb-3">
                <StatusBadge status={t.status} />
                <div className="text-xs text-white/40">{t.participants?.length || 0}/{t.max_participants}</div>
              </div>
              <h3 className="font-display font-black text-xl">{t.name}</h3>
              {t.description && <p className="text-sm text-white/50 mt-1 line-clamp-2">{t.description}</p>}
              {plusOnly && (
                <div className="mt-3 inline-flex items-center gap-1 text-[10px] uppercase tracking-widest text-gold-500">
                  <Sparkles size={10} /> Plus فقط حالياً
                </div>
              )}
              {t.status === "finished" && t.champion_clan_id && (
                <div className="mt-3 inline-flex items-center gap-1 text-[11px] text-gold-500">
                  <Crown size={12} /> البطل: {t.clans?.[t.champion_clan_id]?.name || "—"}
                </div>
              )}
            </Link>
          );
        })}
        {list.length === 0 && (
          <div className="col-span-full text-center text-white/40 py-12">لا توجد بطولات بعد</div>
        )}
      </div>

      {showCreate && (
        <CreateTournamentModal
          onClose={() => setShowCreate(false)}
          onCreated={(t) => { setShowCreate(false); window.location.href = `/tournaments/${t.id}`; }}
        />
      )}
    </div>
  );
}
