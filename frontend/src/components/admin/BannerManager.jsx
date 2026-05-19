import { useEffect, useState, useCallback } from "react";
import api, { formatApiErrorDetail } from "../../api";
import { Image as ImageIcon, Plus, Trash2, Edit, ExternalLink, Save, X } from "lucide-react";
import { toast } from "sonner";

const EMPTY = { title: "", subtitle: "", image: "", link: "", active: true, order: 0 };

export default function BannerManager() {
  const [banners, setBanners] = useState([]);
  const [editing, setEditing] = useState(null);  // banner id or "new"
  const [form, setForm] = useState(EMPTY);

  const load = useCallback(async () => {
    const { data } = await api.get("/admin/banners");
    setBanners(data);
  }, []);

  useEffect(() => { load(); }, [load]);

  const onImage = (e) => {
    const f = e.target.files?.[0];
    if (!f) return;
    if (f.size > 2_000_000) return toast.error("الصورة كبيرة (الحد 2MB)");
    const r = new FileReader();
    r.onload = () => setForm((s) => ({ ...s, image: r.result }));
    r.readAsDataURL(f);
  };

  const startNew = () => { setEditing("new"); setForm({ ...EMPTY, order: banners.length + 1 }); };
  const startEdit = (b) => { setEditing(b.id); setForm({ ...EMPTY, ...b }); };
  const cancel = () => { setEditing(null); setForm(EMPTY); };

  const save = async (e) => {
    e.preventDefault();
    if (!form.image) return toast.error("اختر صورة للإعلان");
    try {
      if (editing === "new") {
        await api.post("/banners", form);
        toast.success("تم إضافة الإعلان");
      } else {
        await api.put(`/banners/${editing}`, form);
        toast.success("تم الحفظ");
      }
      cancel();
      load();
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail));
    }
  };

  const remove = async (id) => {
    // eslint-disable-next-line no-alert
    if (!confirm("حذف الإعلان؟")) return;
    await api.delete(`/banners/${id}`);
    load();
  };

  return (
    <section>
      <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
        <h2 className="font-display font-black text-2xl flex items-center gap-2">
          <ImageIcon className="text-gold-500" /> إعلانات الواجهة
        </h2>
        {!editing && (
          <button data-testid="add-banner-btn" onClick={startNew} className="px-4 py-2 rounded-md bg-gold-500 text-black font-bold hover:bg-gold-400 flex items-center gap-2">
            <Plus size={16} /> إعلان جديد
          </button>
        )}
      </div>

      {editing && (
        <form onSubmit={save} className="bg-surface border b-soft rounded-lg p-5 space-y-3 mb-4" data-testid="banner-form">
          <input
            data-testid="banner-title-input"
            required minLength={2} maxLength={80}
            value={form.title}
            onChange={(e) => setForm({ ...form, title: e.target.value })}
            placeholder="عنوان الإعلان"
            className="w-full bg-background border b-soft rounded-md px-4 py-3 outline-none focus:border-gold-500/40"
          />
          <input
            value={form.subtitle}
            onChange={(e) => setForm({ ...form, subtitle: e.target.value })}
            placeholder="نص فرعي (اختياري)"
            className="w-full bg-background border b-soft rounded-md px-4 py-3 outline-none focus:border-gold-500/40"
          />
          <input
            value={form.link || ""}
            onChange={(e) => setForm({ ...form, link: e.target.value })}
            placeholder="رابط الإعلان (مثلاً https://...) — اتركه فارغاً للبطل الافتراضي"
            className="w-full bg-background border b-soft rounded-md px-4 py-3 outline-none focus:border-gold-500/40"
          />
          <div>
            <label className="text-xs uppercase tracking-widest text-white/50 mb-2 block">الصورة</label>
            {form.image ? (
              <div className="relative">
                <img src={form.image} alt="" className="w-full max-h-48 object-cover rounded border b-soft" />
                <button type="button" onClick={() => setForm({ ...form, image: "" })} className="absolute top-2 left-2 bg-destructive rounded-full text-white w-6 h-6 grid place-items-center">×</button>
              </div>
            ) : (
              <label className="cursor-pointer block bg-background border b-soft border-dashed rounded-md p-6 text-center text-white/50 hover:border-gold-500/40">
                <ImageIcon size={24} className="mx-auto mb-2" />
                اضغط لاختيار صورة (حد أقصى 2MB)
                <input data-testid="banner-image-input" type="file" accept="image/*" onChange={onImage} className="hidden" />
              </label>
            )}
            <input
              value={form.image && !form.image.startsWith("data:") ? form.image : ""}
              onChange={(e) => setForm({ ...form, image: e.target.value })}
              placeholder="أو الصق رابط صورة URL"
              className="w-full mt-2 bg-background border b-soft rounded-md px-4 py-2 outline-none text-sm"
            />
          </div>
          <div className="flex items-center gap-3">
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={form.active}
                onChange={(e) => setForm({ ...form, active: e.target.checked })}
                className="accent-gold-500 w-4 h-4"
              />
              <span className="text-sm">نشط</span>
            </label>
            <div className="flex items-center gap-2">
              <span className="text-xs text-white/50">ترتيب</span>
              <input
                type="number"
                value={form.order}
                onChange={(e) => setForm({ ...form, order: Number(e.target.value) })}
                className="w-20 bg-background border b-soft rounded-md px-3 py-1 outline-none text-sm"
              />
            </div>
          </div>
          <div className="flex gap-2 justify-end">
            <button type="button" onClick={cancel} className="px-4 py-2 rounded-md hover:bg-white/5 flex items-center gap-1">
              <X size={14} /> إلغاء
            </button>
            <button data-testid="save-banner" type="submit" className="px-5 py-2 rounded-md bg-gold-500 text-black font-bold hover:bg-gold-400 flex items-center gap-1">
              <Save size={14} /> حفظ
            </button>
          </div>
        </form>
      )}

      <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {banners.map((b) => (
          <div key={b.id} data-testid={`banner-${b.id}`} className={`bg-surface border rounded-lg overflow-hidden ${b.active ? "b-soft" : "border-white/3 opacity-60"}`}>
            <div className="aspect-video bg-background relative">
              {b.image && <img src={b.image} alt={b.title} className="w-full h-full object-cover" />}
              {!b.active && (
                <div className="absolute top-2 right-2 text-[10px] uppercase tracking-widest bg-destructive/20 text-destructive px-2 py-0.5 rounded">معطل</div>
              )}
            </div>
            <div className="p-3">
              <div className="font-bold text-sm truncate">{b.title}</div>
              {b.subtitle && <div className="text-xs text-white/50 truncate">{b.subtitle}</div>}
              {b.link && (
                <a href={b.link} target="_blank" rel="noopener noreferrer" className="text-[10px] text-gold-500 truncate flex items-center gap-1 hover:underline">
                  <ExternalLink size={10} /> {b.link.slice(0, 30)}...
                </a>
              )}
              <div className="flex gap-1 mt-2">
                <button onClick={() => startEdit(b)} className="p-1.5 rounded hover:bg-white/5 text-white/60"><Edit size={14} /></button>
                <button onClick={() => remove(b.id)} className="p-1.5 rounded hover:bg-destructive/10 text-destructive"><Trash2 size={14} /></button>
              </div>
            </div>
          </div>
        ))}
        {banners.length === 0 && !editing && (
          <div className="col-span-full text-center text-white/40 py-6 text-sm">لا توجد إعلانات — أضف أول واحد!</div>
        )}
      </div>
    </section>
  );
}
