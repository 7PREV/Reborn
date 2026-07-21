import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import api from "../api";
import { Search, Sparkles } from "lucide-react";
import { useAuth } from "../AuthContext";
import { toast } from "sonner";
import { formatApiErrorDetail } from "../api";

export default function PlayersPage() {
  const { user } = useAuth();
  const [users, setUsers] = useState([]);
  const [q, setQ] = useState("");
  const [tab, setTab] = useState("all");
  const [myClan, setMyClan] = useState(null);
  const [offerModalOpen, setOfferModalOpen] = useState(false);
  const [selectedFreeAgent, setSelectedFreeAgent] = useState(null);
  const [offerTerms, setOfferTerms] = useState("");
  const [sendingOffer, setSendingOffer] = useState(false);

  useEffect(() => {
    api.get("/users/search", { params: { q } }).then((r) => setUsers(r.data));
  }, [q]);

  useEffect(() => {
    if (!user?.clan_id) {
      setMyClan(null);
      return;
    }
    api.get(`/clans/${user.clan_id}`).then((r) => setMyClan(r.data)).catch(() => setMyClan(null));
  }, [user?.clan_id]);

  const isClanLeader = !!(user?.clan_id && myClan?.leader_id === user?.id);

  const filteredUsers = useMemo(() => {
    if (tab === "in-clan") return users.filter((u) => !!u.clan_id);
    if (tab === "free") return users.filter((u) => !u.clan_id);
    return users;
  }, [users, tab]);

  const openOfferModal = (freeAgent) => {
    setSelectedFreeAgent(freeAgent);
    setOfferTerms("");
    setOfferModalOpen(true);
  };

  const sendContractOffer = async () => {
    if (!isClanLeader || !selectedFreeAgent?.id || !user?.clan_id) return;
    setSendingOffer(true);
    try {
      await api.post(`/clans/${user.clan_id}/contract-offer`, {
        user_id: selectedFreeAgent.id,
        terms: offerTerms,
      });
      toast.success("تم إرسال عرض التعاقد بنجاح");
      setOfferModalOpen(false);
      setSelectedFreeAgent(null);
      setOfferTerms("");
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail));
    } finally {
      setSendingOffer(false);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-display font-black text-3xl md:text-4xl">اللاعبون</h1>
        <p className="text-white/50 mt-1">ابحث عن لاعب بالاسم أو البريد</p>
      </div>

      <div className="relative max-w-xl">
        <Search size={18} className="absolute right-3 top-1/2 -translate-y-1/2 text-white/30" />
        <input
          data-testid="search-players"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="اسم اللاعب..."
          className="w-full bg-surface border b-soft rounded-md pr-10 pl-4 py-3 outline-none focus:border-gold-500/40"
        />
      </div>

      <div className="flex items-center gap-2 flex-wrap">
        <button
          type="button"
          onClick={() => setTab("all")}
          className={`px-3 py-1.5 rounded-md text-sm border ${tab === "all" ? "bg-gold-500 text-black border-gold-500" : "b-soft text-white/70 hover:bg-white/5"}`}
        >
          All
        </button>
        <button
          type="button"
          onClick={() => setTab("in-clan")}
          className={`px-3 py-1.5 rounded-md text-sm border ${tab === "in-clan" ? "bg-gold-500 text-black border-gold-500" : "b-soft text-white/70 hover:bg-white/5"}`}
        >
          In-Clan
        </button>
        <button
          type="button"
          onClick={() => setTab("free")}
          className={`px-3 py-1.5 rounded-md text-sm border ${tab === "free" ? "bg-emerald-500 text-black border-emerald-500" : "b-soft text-white/70 hover:bg-white/5"}`}
        >
          Free Agents 🟢
        </button>
      </div>

      <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {filteredUsers.map((u) => {
          const isPlusMember = !!(u.is_plus || u.is_personal_plus || u.plan === "plus");
          const isFreeAgent = !u.clan_id;
          return (
            <div
              key={u.id}
              data-testid={`player-${u.id}`}
              className={`bg-surface border b-soft rounded-lg p-4 flex items-center gap-3 fade-in hover:border-gold-500/40 transition ${isPlusMember ? "plus-glow" : ""}`}
            >
              <Link to={`/players/${u.id}`} className="h-12 w-12 rounded-md bg-gold-500/10 text-gold-500 grid place-items-center font-display font-black text-lg overflow-hidden flex-shrink-0">
                {u.is_personal_plus && u.avatar ? (
                  <img src={u.avatar} alt={u.username} className="h-full w-full object-cover" />
                ) : (u.username[0] || "?").toUpperCase()}
              </Link>
              <div className="flex-1 min-w-0">
                <div className="font-bold truncate flex items-center gap-1.5">
                  <Link to={`/players/${u.id}`} className="truncate hover:text-gold-500">{u.username}</Link>
                  {isPlusMember && <Sparkles size={11} className="text-[#d4af37] drop-shadow-[0_0_8px_rgba(212,175,55,0.55)]" />}
                  {isFreeAgent && (
                    <span className="inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-bold bg-emerald-500/15 text-emerald-400 border border-emerald-500/40 shadow-[0_0_14px_rgba(16,185,129,0.45)]">
                      لاعب حر / Free Agent
                    </span>
                  )}
                </div>
                <div className="text-xs text-white/40 truncate">
                  {u.role === "owner" ? "مالك" : u.role === "admin" ? "منظم" : u.clan_id ? "في كلان" : "حر"}
                </div>
              </div>
              <div className="flex flex-col items-end gap-2">
                <div className="text-gold-500 font-display font-black">{u.points}</div>
                {isClanLeader && isFreeAgent && (
                  <button
                    type="button"
                    onClick={() => openOfferModal(u)}
                    className="px-2.5 py-1.5 rounded text-xs font-bold bg-emerald-500 text-black hover:bg-emerald-400"
                  >
                    ارسال دعوة 📝
                  </button>
                )}
              </div>
            </div>
          );
        })}
        {filteredUsers.length === 0 && <div className="col-span-full text-center text-white/40 py-12">لا توجد نتائج</div>}
      </div>

      {offerModalOpen && selectedFreeAgent && (
        <div className="fixed inset-0 z-50 grid place-items-center bg-black/70 backdrop-blur-xl p-4">
          <div className="bg-surface border b-soft rounded-xl p-6 w-full max-w-lg space-y-4">
            <h2 className="font-display font-black text-2xl"> 'ارسال دعوة' 📝</h2>
            <div className="text-sm text-white/70">
              إرسال دعوة إلى <span className="text-gold-500 font-bold">{selectedFreeAgent.username}</span>
            </div>
            <textarea
              value={offerTerms}
              onChange={(e) => setOfferTerms(e.target.value)}
              rows={4}
              placeholder="اكتب شروط العقد (اختياري)..."
              className="w-full bg-background border b-soft rounded-md px-4 py-3 outline-none focus:border-gold-500/40 resize-none"
            />
            <div className="flex items-center justify-end gap-2">
              <button
                type="button"
                onClick={() => setOfferModalOpen(false)}
                className="px-4 py-2 rounded-md hover:bg-white/5"
                disabled={sendingOffer}
              >
                إلغاء
              </button>
              <button
                type="button"
                onClick={sendContractOffer}
                disabled={sendingOffer}
                className="px-5 py-2 rounded-md bg-emerald-500 text-black font-bold hover:bg-emerald-400 disabled:opacity-60"
              >
                {sendingOffer ? "جاري الإرسال..." : "إرسال العرض"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
