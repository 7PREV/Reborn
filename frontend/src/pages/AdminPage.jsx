import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import api from "../api";
import { useAuth } from "../AuthContext";
import { AlertCircle, ScrollText, Swords, Shield, Sparkles, Settings } from "lucide-react";
import { toast } from "sonner";

export default function AdminPage() {
  const { user } = useAuth();
  const [live, setLive] = useState([]);
  const [history, setHistory] = useState([]);
  const [clans, setClans] = useState([]);
  const [disputes, setDisputes] = useState([]);

  useEffect(() => {
    if (user?.role !== "admin") return;
    api.get("/matches/live").then((r) => {
      setLive(r.data);
      const disp = r.data.filter((m) => (m.maps || []).some((mp) => mp.disputed));
      setDisputes(disp);
    });
    api.get("/matches/history").then((r) => setHistory(r.data));
    api.get("/clans").then((r) => setClans(r.data));
  }, [user]);

  if (user?.role !== "admin") {
    return (
      <div className="bg-surface border b-soft rounded-xl p-12 text-center">
        <AlertCircle size={32} className="mx-auto mb-3 text-destructive" />
        غير مصرح — هذه الصفحة للمنظمين فقط
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <div>
        <div className="text-xs uppercase tracking-widest text-gold-500 mb-2">لوحة الإدارة</div>
        <h1 className="font-display font-black text-3xl md:text-4xl">مرحباً يا منظم</h1>
        <p className="text-white/50 mt-1">إشراف كامل على المباريات والكلانات والقوانين</p>
      </div>

      <div className="grid sm:grid-cols-4 gap-4">
        <div className="bg-surface border b-soft rounded-lg p-5">
          <div className="text-xs uppercase tracking-widest text-white/40">مباشر</div>
          <div className="text-3xl font-display font-black text-gold-500">{live.length}</div>
        </div>
        <div className="bg-surface border b-soft rounded-lg p-5">
          <div className="text-xs uppercase tracking-widest text-destructive">نزاعات</div>
          <div className="text-3xl font-display font-black text-destructive">{disputes.length}</div>
        </div>
        <div className="bg-surface border b-soft rounded-lg p-5">
          <div className="text-xs uppercase tracking-widest text-white/40">٢٤ ساعة</div>
          <div className="text-3xl font-display font-black">{history.length}</div>
        </div>
        <div className="bg-surface border b-soft rounded-lg p-5">
          <div className="text-xs uppercase tracking-widest text-white/40">كلانات</div>
          <div className="text-3xl font-display font-black">{clans.length}</div>
        </div>
      </div>

      <div className="grid lg:grid-cols-3 gap-4">
        <Link to="/rules" className="bg-surface border b-soft rounded-lg p-5 hover:border-gold-500/30 transition flex items-center gap-3">
          <ScrollText className="text-gold-500" />
          <div>
            <div className="font-display font-bold">إدارة القوانين</div>
            <div className="text-xs text-white/50">إضافة، تعديل وحذف القوانين</div>
          </div>
        </Link>
        <div className="bg-surface border b-soft rounded-lg p-5 flex items-center gap-3">
          <Shield className="text-gold-500" />
          <div>
            <div className="font-display font-bold">{clans.length} كلان</div>
            <div className="text-xs text-white/50">إجمالي الكلانات النشطة</div>
          </div>
        </div>
        <div className="bg-surface border b-soft rounded-lg p-5 flex items-center gap-3">
          <Sparkles className="text-gold-500" />
          <div>
            <div className="font-display font-bold">Plus</div>
            <div className="text-xs text-white/50">7 → 12 لاعب • نائب → نائبَين</div>
          </div>
        </div>
      </div>

      {disputes.length > 0 && (
        <section>
          <h2 className="font-display font-black text-2xl mb-4 text-destructive flex items-center gap-2">
            <AlertCircle /> نزاعات تنتظر قرارك ({disputes.length})
          </h2>
          <div className="bg-surface border border-destructive/30 rounded-lg divide-y divide-white/5">
            {disputes.map((m) => (
              <Link key={m.id} to={`/matches/${m.id}`} className="p-4 flex items-center gap-4 hover:bg-destructive/5">
                <span className="live-dot" />
                <div className="flex-1 flex items-center gap-3">
                  <span className="font-bold">{m.clan_a?.tag}</span>
                  <span className="text-white/40">vs</span>
                  <span className="font-bold">{m.clan_b?.tag}</span>
                </div>
                <span className="text-xs text-destructive">حلّ النزاع ←</span>
              </Link>
            ))}
          </div>
        </section>
      )}

      <section>
        <h2 className="font-display font-black text-2xl mb-4">المباريات المباشرة</h2>
        <div className="bg-surface border b-soft rounded-lg divide-y divide-white/5">
          {live.length === 0 && <div className="p-6 text-center text-white/40 text-sm">لا توجد</div>}
          {live.map((m) => (
            <Link key={m.id} to={`/matches/${m.id}`} className="p-4 flex items-center gap-4 hover:bg-white/[0.03]">
              <span className="live-dot" />
              <div className="flex-1 flex items-center gap-3">
                <span className="font-bold">{m.clan_a?.tag}</span>
                <span className="text-white/40">vs</span>
                <span className="font-bold">{m.clan_b?.tag}</span>
              </div>
              <span className="text-xs text-white/40">{m.game}</span>
              <span className="text-xs text-gold-500">دخول ←</span>
            </Link>
          ))}
        </div>
      </section>
    </div>
  );
}
