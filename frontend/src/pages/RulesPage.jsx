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
  const [form, setForm] = useState({ title: "", body: "", order: 0, image: "", images: [] });

  const isAdmin = user?.role === "admin" || user?.role === "owner";

  const load = async () => {
    const { data } = await api.get("/rules");
    setRules(data);
  };

  useEffect(() => { load(); }, []);

  const startCreate = () => {
    setCreating(true);
    setForm({ title: "", body: "", order: rules.length + 1, image: "", images: [] });
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
    const images = Array.isArray(r.images) && r.images.length ? r.images : (r.image ? [r.image] : []);
    setEditing(r.id);
    setForm({ title: r.title, body: r.body, order: r.order, image: images[0] || "", images });
    setCreating(false);
  };

  const readAsDataUrl = (file) => new Promise((resolve, reject) => {
    const fr = new FileReader();
    fr.onload = () => resolve(fr.result);
    fr.onerror = reject;
    fr.readAsDataURL(file);
  });

  const onImages = async (e) => {
    const files = Array.from(e.target.files || []);
    if (!files.length) return;

    const added = [];
    for (const f of files) {
      if (!f.type.startsWith("image/")) {
        toast.error(`الملف ${f.name} ليس صورة`);
        continue;
      }
      if (f.size > 2_000_000) {
        toast.error(`الصورة ${f.name} كبيرة (الحد 2MB)`);
        continue;
      }
      try {
        // eslint-disable-next-line no-await-in-loop
        const data = await readAsDataUrl(f);
        if (typeof data === "string") added.push(data);
      } catch {
        toast.error(`فشل قراءة الصورة ${f.name}`);
      }
    }

    if (added.length) {
      setForm((p) => {
        const merged = [...(p.images || []), ...added];
        return { ...p, images: merged, image: merged[0] || "" };
      });
    }
    e.target.value = "";
  };

  const removeImageAt = (idx) => {
    setForm((p) => {
      const next = (p.images || []).filter((_, i) => i !== idx);
      return { ...p, images: next, image: next[0] || "" };
    });
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
            <ScrollText className="text-gold-500" /> القوانين العامة
          </h1>
          <p className="text-white/50 mt-1">القواعد العامة التي تحكم المنصة والسلوك العام</p>
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
            <label className="text-xs uppercase tracking-widest text-white/50 mb-1 block">صور مرفقة (اختياري — كل صورة ≤2MB)</label>
            <label className="inline-flex items-center gap-2 px-3 py-2 rounded-md bg-background border b-soft hover:border-gold-500/40 text-sm cursor-pointer">
              <Plus size={14} />
              <span>{form.images?.length ? `تم اختيار ${form.images.length} صورة` : "اختر صور"}</span>
              <input data-testid="rule-image-input" type="file" accept="image/*" multiple onChange={onImages} className="hidden" />
            </label>
            {!!form.images?.length && (
              <div className="mt-2 grid grid-cols-2 md:grid-cols-3 gap-2">
                {form.images.map((img, idx) => (
                  <div key={`${img.slice(0, 24)}-${idx}`} className="relative">
                    <img src={img} alt={`rule-${idx}`} className="h-24 w-full object-cover rounded border b-soft" />
                    <button type="button" onClick={() => removeImageAt(idx)} className="absolute top-1 left-1 px-2 py-0.5 text-[10px] text-destructive bg-black/70 hover:bg-destructive/20 rounded">حذف</button>
                  </div>
                ))}
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
                {(() => {
                  const imgs = Array.isArray(r.images) && r.images.length ? r.images : (r.image ? [r.image] : []);
                  if (!imgs.length) return null;
                  return (
                    <div className="mt-3 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
                      {imgs.map((img, imageIdx) => (
                        <img
                          key={`${r.id}-${imageIdx}`}
                          src={img}
                          alt={`${r.title}-${imageIdx + 1}`}
                          className="rounded-md max-h-72 w-full object-cover border b-soft"
                          data-testid={`rule-image-${r.id}-${imageIdx}`}
                        />
                      ))}
                    </div>
                  );
                })()}
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
