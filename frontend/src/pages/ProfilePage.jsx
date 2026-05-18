import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import api, { formatApiErrorDetail } from "../api";
import { useAuth } from "../AuthContext";
import { Shield, Trophy, Mail, Check, X, Sparkles } from "lucide-react";
import { toast } from "sonner";

export default function ProfilePage() {
  const { user, refresh } = useAuth();
  const [invites, setInvites] = useState([]);

  const load = async () => {
    const { data } = await api.get("/me/invites");
    setInvites(data);
  };
  useEffect(() => { load(); }, []);

  const respond = async (inv, action) => {
    try {
      const { data } = await api.post(`/invites/${inv.id}`, { action });
      if (data?.reward_granted) {
        toast.success("🎁 امتلأ كلانك! حصلت على Plus 7 أيام!", { duration: 6000 });
      } else {
        toast.success(action === "accept" ? "انضممت للكلان" : "رفضت الدعوة");
      }
      await refresh();
      load();
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail));
    }
  };

  const togglePlus = async () => {
    try {
      await api.post("/me/plus");
      await refresh();
      toast.success("تم تحديث Plus");
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail));
    }
  };

  if (!user) return null;

  return (
    <div className="space-y-8">
      <div className="bg-surface border b-soft rounded-xl p-6 md:p-8 flex items-center gap-5 flex-wrap">
        <div className="h-20 w-20 rounded-lg bg-gold-500/10 text-gold-500 grid place-items-center font-display font-black text-3xl">
          {user.username[0].toUpperCase()}
        </div>
        <div className="flex-1 min-w-0">
          <div className="text-xs uppercase tracking-widest text-gold-500 flex items-center gap-2">
            {user.role === "admin" ? "منظم" : user.is_plus ? "Plus" : "لاعب"}
            {user.is_plus && <Sparkles size={12} />}
          </div>
          <h1 className="font-display font-black text-3xl">{user.username}</h1>
          <div className="text-white/50 text-sm">{user.email}</div>
        </div>
        <div className="text-center">
          <div className="text-3xl font-display font-black text-gold-500 flex items-center gap-1">
            <Trophy size={20} /> {user.points}
          </div>
          <div className="text-[10px] uppercase tracking-widest text-white/40">النقاط</div>
        </div>
      </div>

      <div className={`rounded-xl p-6 border ${user.is_plus ? "border-gold-500/40 bg-gold-500/5" : "border-white/5 bg-surface"}`}>
        <div className="flex items-center gap-3 mb-3">
          <Sparkles className="text-gold-500" />
          <h2 className="font-display font-black text-xl">RIVALS Plus</h2>
          {user.is_plus && <span className="text-[10px] uppercase tracking-widest bg-gold-500 text-black px-2 py-0.5 rounded">مفعل</span>}
        </div>
        {user.plus_expires_at && (
          <div className="text-xs text-gold-500 mb-3" data-testid="plus-expiry">
            ينتهي خلال: {Math.max(0, Math.ceil((new Date(user.plus_expires_at) - new Date()) / 86400000))} يوم
          </div>
        )}
        <ul className="text-sm text-white/70 space-y-1 mb-4 list-disc pr-5">
          <li>زيادة سعة الكلان من 7 إلى 12 لاعب</li>
          <li>تعيين نائبَين للقائد بدل نائب واحد</li>
          <li>دعم أولوية في النزاعات</li>
          <li className="text-gold-500">🎁 املأ كلانك بـ 6 لاعبين تحصل على Plus مجاناً لمدة 7 أيام</li>
        </ul>
        <button data-testid="toggle-plus-btn" onClick={togglePlus} className={`px-4 py-2 rounded-md font-bold ${
          user.is_plus ? "bg-white/5 hover:bg-white/10" : "bg-gold-500 text-black hover:bg-gold-400"
        }`}>
          {user.is_plus ? "إلغاء Plus" : "تفعيل Plus (مجاناً للتجربة)"}
        </button>
      </div>

      {user.clan_id && (
        <div className="bg-surface border b-soft rounded-xl p-5 flex items-center gap-3">
          <Shield className="text-gold-500" />
          <span>أنت عضو في كلان</span>
          <Link to={`/clans/${user.clan_id}`} className="mr-auto px-3 py-1.5 rounded bg-gold-500 text-black text-sm font-bold hover:bg-gold-400">
            عرض الكلان
          </Link>
        </div>
      )}

      <section>
        <h2 className="font-display font-black text-2xl mb-4 flex items-center gap-2">
          <Mail size={20} className="text-gold-500" /> دعوات الانضمام
        </h2>
        {invites.length === 0 ? (
          <div className="bg-surface border b-soft rounded-lg p-8 text-center text-white/40">لا توجد دعوات</div>
        ) : (
          <div className="space-y-2">
            {invites.map((inv) => (
              <div key={inv.id} className="bg-surface border b-soft rounded-lg p-4 flex items-center gap-3" data-testid={`invite-${inv.id}`}>
                <Shield className="text-gold-500" />
                <div className="flex-1">
                  <div className="font-bold">{inv.clan_name}</div>
                  <div className="text-xs text-white/40">[{inv.clan_tag}]</div>
                </div>
                <button data-testid={`invite-accept-${inv.id}`} onClick={() => respond(inv, "accept")} className="p-2 rounded bg-gold-500 text-black hover:bg-gold-400"><Check size={16} /></button>
                <button onClick={() => respond(inv, "reject")} className="p-2 rounded border b-soft hover:bg-destructive/10 text-destructive"><X size={16} /></button>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
