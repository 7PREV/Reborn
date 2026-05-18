import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import api from "../api";
import { useAuth } from "../AuthContext";
import { Search, Plus, Shield } from "lucide-react";
import { toast } from "sonner";
import { formatApiErrorDetail } from "../api";

export default function ClansPage() {
  const { user } = useAuth();
  const [clans, setClans] = useState([]);
  const [q, setQ] = useState("");
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({ name: "", tag: "", description: "" });

  const load = async () => {
    const { data } = await api.get("/clans", { params: { q } });
    setClans(data);
  };

  useEffect(() => {
    load();
  }, [q]);

  const create = async (e) => {
    e.preventDefault();
    try {
      const { data } = await api.post("/clans", form);
      toast.success("تم إنشاء الكلان");
      setShowCreate(false);
      setForm({ name: "", tag: "", description: "" });
      load();
      window.location.href = `/clans/${data.id}`;
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail));
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <div>
          <h1 className="font-display font-black text-3xl md:text-4xl">الكلانات</h1>
          <p className="text-white/50 mt-1">اكتشف، انضم أو أنشئ كلانك</p>
        </div>
        {user && !user.clan_id && (
          <button
            data-testid="create-clan-btn"
            onClick={() => setShowCreate(true)}
            className="px-5 py-3 rounded-md bg-gold-500 text-black font-bold hover:bg-gold-400 transition flex items-center gap-2"
          >
            <Plus size={18} /> إنشاء كلان
          </button>
        )}
      </div>

      <div className="relative max-w-xl">
        <Search size={18} className="absolute right-3 top-1/2 -translate-y-1/2 text-white/30" />
        <input
          data-testid="search-clans"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="ابحث باسم الكلان أو التاج..."
          className="w-full bg-surface border b-soft rounded-md pr-10 pl-4 py-3 outline-none focus:border-gold-500/40"
        />
      </div>

      <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {clans.map((c) => (
          <Link
            key={c.id}
            to={`/clans/${c.id}`}
            data-testid={`clan-card-${c.id}`}
            className="bg-surface border b-soft rounded-lg p-5 hover:border-gold-500/30 transition fade-in"
          >
            <div className="flex items-center gap-3">
              <div className="h-12 w-12 rounded-md bg-gold-500/10 grid place-items-center text-gold-500">
                <Shield size={22} />
              </div>
              <div className="min-w-0">
                <div className="font-display font-black text-lg truncate">{c.name}</div>
                <div className="text-xs text-white/40">[{c.tag}]</div>
              </div>
            </div>
            {c.description && (
              <p className="text-sm text-white/50 mt-3 line-clamp-2">{c.description}</p>
            )}
            <div className="mt-4 flex justify-between text-xs text-white/40 uppercase tracking-widest">
              <span>{c.member_ids?.length || 0} أعضاء</span>
              <span className="text-gold-500">{c.points} نقطة</span>
            </div>
          </Link>
        ))}
        {clans.length === 0 && (
          <div className="col-span-full text-center text-white/40 py-12">لا توجد كلانات</div>
        )}
      </div>

      {showCreate && (
        <div className="fixed inset-0 z-50 grid place-items-center bg-black/70 backdrop-blur-xl p-4">
          <form
            onSubmit={create}
            data-testid="create-clan-form"
            className="bg-surface border b-soft rounded-xl p-6 w-full max-w-md space-y-4"
          >
            <h2 className="font-display font-black text-2xl">كلان جديد</h2>
            <input
              data-testid="clan-name-input"
              required
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              placeholder="اسم الكلان"
              className="w-full bg-background border b-soft rounded-md px-4 py-3 outline-none focus:border-gold-500/40"
            />
            <input
              data-testid="clan-tag-input"
              required
              minLength={2}
              maxLength={8}
              value={form.tag}
              onChange={(e) => setForm({ ...form, tag: e.target.value.toUpperCase() })}
              placeholder="التاج (مثال: ARN)"
              className="w-full bg-background border b-soft rounded-md px-4 py-3 outline-none focus:border-gold-500/40"
            />
            <textarea
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
              placeholder="وصف مختصر"
              rows={3}
              className="w-full bg-background border b-soft rounded-md px-4 py-3 outline-none focus:border-gold-500/40 resize-none"
            />
            <div className="flex gap-2 justify-end">
              <button type="button" onClick={() => setShowCreate(false)} className="px-4 py-2 rounded-md hover:bg-white/5">
                إلغاء
              </button>
              <button data-testid="submit-create-clan" type="submit" className="px-5 py-2 rounded-md bg-gold-500 text-black font-bold hover:bg-gold-400">
                إنشاء
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}
