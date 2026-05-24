import { useEffect, useState } from "react";
import api, { formatApiErrorDetail } from "../api";
import { useAuth } from "../AuthContext";
import { ScrollText, Plus, Edit, Trash2, Save, X } from "lucide-react";
import { toast } from "sonner";

export default function RulesPage() {
  const { user } = useAuth();
  const [rules, setRules] = useState([]);
  const [editing, setEditing] = useState(null);
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState({ title: "", body: "", order: 0, image: "" });

  const isAdmin = user?.role === "admin" || user?.role === "owner";

  const load = async () => {
    const { data } = await api.get("/rules");
    setRules(data);
  };

  useEffect(() => { load(); }, []);

  const startCreate = () => {
    setCreating(true);
    setForm({ title: "", body: "", order: rules.length + 1, image: "" });
  };

  const save = async (e) => {
    e.preventDefault();
    try {
      if (editing) {
        await api.put(`/rules/${editing}`, form);
        toast.success("تم الحفظ");
      } else {
        await api.post("/rules", form);
        toast.success("تمت الإضافة");
      }
      setEditing(null);
      setCreating(false);
      load();
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail));
    }
  };

  const startEdit = (r) => {
    setEditing(r.id);
    setForm({ title: r.title, body: r.body, order: r.order, image: r.image || "" });
    setCreating(false);
  };

  const onImage = async (e) => {
    const f = e.target.files?.[0];
    if (!f) return;
    if (f.size > 2_000_000) return toast.error("الصورة كبيرة (الحد 2MB)");
    const fr = new FileReader();
    fr.onload = () => setForm((p) => ({ ...p, image: fr.result }));
    fr.readAsDataURL(f);
  };

  const remove = async (id) => {
    if (!confirm("حذف القاعدة؟")) return;
    await api.delete(`/rules/${id}`);
    load();
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <div>
          <h1 className="font-display font-black text-3xl md:text-4xl flex items-center gap-3">
            <ScrollText className="text-gold-500" /> قوانين الدوري
          </h1>
          <p className="text-white/50 mt-1">القواعد التي تحكم كل المباريات والكلانات</p>
        </div>
        {isAdmin && (
          <button data-testid="add-rule-btn" onClick={startCreate} className="px-4 py-2 rounded-md bg-gold-500 text-black font-bold hover:bg-gold-400 flex items-center gap-2">
            <Plus size={16} /> قاعدة جديدة
          </button>
        )}
      </div>

      {(creating || editing) && isAdmin && (
        <form onSubmit={save} className="bg-surface border b-soft rounded-lg p-5 space-y-3" data-testid="rule-form">
          <input
            data-testid="rule-title-input"
            required
            value={form.title}
            onChange={(e) => setForm({ ...form, title: e.target.value })}
            placeholder="عنوان القاعدة"
            className="w-full bg-background border b-soft rounded-md px-4 py-3 outline-none focus:border-gold-500/40"
          />
          <textarea
            data-testid="rule-body-input"
            required
            value={form.body}
            onChange={(e) => setForm({ ...form, body: e.target.value })}
            placeholder="تفاصيل القاعدة..."
            rows={4}
            className="w-full bg-background border b-soft rounded-md px-4 py-3 outline-none focus:border-gold-500/40 resize-none"
          />
          <input
            type="number"
            value={form.order}
            onChange={(e) => setForm({ ...form, order: Number(e.target.value) })}
            placeholder="ترتيب"
            className="w-32 bg-background border b-soft rounded-md px-4 py-2 outline-none focus:border-gold-500/40"
          />
          <div>
            <label className="text-xs uppercase tracking-widest text-white/50 mb-1 block">صورة مرفقة (اختياري — ≤2MB)</label>
            <label className="inline-flex items-center gap-2 px-3 py-2 rounded-md bg-background border b-soft hover:border-gold-500/40 text-sm cursor-pointer">
              <Plus size={14} />
              <span>{form.image ? "تم اختيار صورة" : "اختر صورة"}</span>
              <input data-testid="rule-image-input" type="file" accept="image/*" onChange={onImage} className="hidden" />
            </label>
            {form.image && (
              <div className="mt-2 flex items-center gap-2">
                <img src={form.image} alt="rule" className="max-h-32 rounded border b-soft" />
                <button type="button" onClick={() => setForm({ ...form, image: "" })} className="px-2 py-1 text-xs text-destructive hover:bg-destructive/10 rounded">حذف الصورة</button>
              </div>
            )}
          </div>
          <div className="flex gap-2">
            <button data-testid="save-rule" type="submit" className="px-5 py-2 rounded-md bg-gold-500 text-black font-bold hover:bg-gold-400 flex items-center gap-1">
              <Save size={14} /> حفظ
            </button>
            <button type="button" onClick={() => { setEditing(null); setCreating(false); }} className="px-5 py-2 rounded-md hover:bg-white/5 flex items-center gap-1">
              <X size={14} /> إلغاء
            </button>
          </div>
        </form>
      )}

      <div className="space-y-3">
        {rules.map((r, idx) => (
          <div key={r.id} data-testid={`rule-${r.id}`} className="bg-surface border b-soft rounded-lg p-5 fade-in">
            <div className="flex items-start gap-3">
              <div className="h-9 w-9 rounded bg-gold-500/10 text-gold-500 grid place-items-center font-display font-black shrink-0">
                {idx + 1}
              </div>
              <div className="flex-1 min-w-0">
                <h3 className="font-display font-bold text-lg">{r.title}</h3>
                <p className="text-white/70 mt-1 whitespace-pre-wrap leading-relaxed">{r.body}</p>
                {r.image && (
                  <img src={r.image} alt={r.title} className="mt-3 rounded-md max-h-72 border b-soft" data-testid={`rule-image-${r.id}`} />
                )}
              </div>
              {isAdmin && (
                <div className="flex gap-1">
                  <button onClick={() => startEdit(r)} className="p-2 rounded hover:bg-white/5 text-white/60"><Edit size={16} /></button>
                  <button onClick={() => remove(r.id)} className="p-2 rounded hover:bg-destructive/10 text-destructive"><Trash2 size={16} /></button>
                </div>
              )}
            </div>
          </div>
        ))}
        {rules.length === 0 && (
          <div className="text-center text-white/40 py-12">لا توجد قوانين بعد</div>
        )}
      </div>
    </div>
  );
}
