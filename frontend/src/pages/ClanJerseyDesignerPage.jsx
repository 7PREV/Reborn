import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { CheckCircle2, Image as ImageIcon, Shield, Sparkles } from "lucide-react";
import { toast } from "sonner";
import api, { formatApiErrorDetail } from "../api";
import { useAuth } from "../AuthContext";

const TEXTURES = ["carbon", "classic", "matte", "mesh", "diamond"];
const FRAMES = ["athletic", "lean", "stocky", "slim", "curvy"];

async function fileToDataUrl(file) {
  return await new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result || ""));
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}

export default function ClanJerseyDesignerPage() {
  const { id } = useParams();
  const { user, refresh } = useAuth();
  const [clan, setClan] = useState(null);
  const [isPlusClan, setIsPlusClan] = useState(false);
  const [rivalsBadge, setRivalsBadge] = useState("");
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(true);
  const [previewGender, setPreviewGender] = useState("male");
  const [form, setForm] = useState({
    base_texture: "classic",
    primary_color: "#1f2937",
    secondary_color: "#111827",
    accent_color: "#f59e0b",
    logo: "",
    male_frame: "athletic",
    female_frame: "athletic",
  });

  const canEdit = useMemo(() => {
    if (!user || !clan) return false;
    if (user.role === "admin" || user.role === "owner") return true;
    if (user.id === clan.leader_id) return true;
    return (clan.vice_leader_ids || []).includes(user.id);
  }, [user, clan]);

  const activeFrame = previewGender === "male" ? form.male_frame : form.female_frame;

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [clanRes, jerseyRes] = await Promise.all([
        api.get(`/clans/${id}`),
        api.get(`/clans/${id}/jersey`),
      ]);
      setClan(clanRes.data);
      setIsPlusClan(!!jerseyRes.data?.isPlusClan);
      setRivalsBadge(jerseyRes.data?.rivals_badge || "");
      if (jerseyRes.data?.jersey) {
        const j = jerseyRes.data.jersey;
        setForm({
          base_texture: j.base_texture || "classic",
          primary_color: j.primary_color || "#1f2937",
          secondary_color: j.secondary_color || "#111827",
          accent_color: j.accent_color || "#f59e0b",
          logo: j.logo || "",
          male_frame: j.male_frame || "athletic",
          female_frame: j.female_frame || "athletic",
        });
      }
      const defaultGender = user?.avatar_render?.gender || "male";
      setPreviewGender(defaultGender === "female" ? "female" : "male");
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail));
    } finally {
      setLoading(false);
    }
  }, [id, user]);

  useEffect(() => {
    load();
  }, [load]);

  const save = async () => {
    setSaving(true);
    try {
      await api.put(`/clans/${id}/jersey`, form);
      await refresh();
      toast.success("تم حفظ تصميم الزي الرسمي");
      load();
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail));
    } finally {
      setSaving(false);
    }
  };

  const onUploadLogo = async (file) => {
    if (!file) return;
    const dataUrl = await fileToDataUrl(file);
    setForm((prev) => ({ ...prev, logo: dataUrl }));
  };

  if (loading) {
    return <div className="h-56 rounded-xl border b-soft bg-surface animate-pulse" />;
  }

  if (!clan) {
    return <div className="rounded-xl border b-soft bg-surface p-8 text-center text-white/50">تعذر تحميل بيانات الكلان.</div>;
  }

  return (
    <div className="space-y-6">
      <section className="rounded-2xl border b-soft bg-surface p-6 md:p-8">
        <div className="flex items-center justify-between gap-3 flex-wrap">
          <div>
            <h1 className="font-display font-black text-3xl md:text-4xl flex items-center gap-2">
              <Shield className="text-gold-500" /> مصمم زي الكلان
            </h1>
            <p className="mt-2 text-white/60 text-sm">
              {clan.name} [{clan.tag}] • متاح للكلانات Plus
            </p>
          </div>
          <Link to={`/clans/${id}`} className="text-sm text-gold-500 hover:text-gold-400">العودة لصفحة الكلان</Link>
        </div>
      </section>

      {!isPlusClan ? (
        <section className="rounded-xl border border-gold-500/30 bg-gold-500/5 p-6 text-center">
          <Sparkles className="mx-auto text-gold-500" />
          <h2 className="font-display font-black text-xl mt-3">ميزة Plus فقط</h2>
          <p className="text-white/60 text-sm mt-2">هذا الكلان لا يملك اشتراك Plus لتفعيل مصمم الزي الرسمي.</p>
        </section>
      ) : (
        <div className="grid lg:grid-cols-3 gap-4">
          <div className="lg:col-span-2 space-y-4">
            <section className="rounded-xl border b-soft bg-surface p-4 grid sm:grid-cols-2 gap-3">
              <label className="text-xs text-white/50 space-y-1.5">
                Texture
                <select
                  value={form.base_texture}
                  onChange={(e) => setForm((prev) => ({ ...prev, base_texture: e.target.value }))}
                  className="w-full rounded-lg bg-background border b-soft px-3 py-2 text-sm outline-none focus:border-gold-500/35"
                >
                  {TEXTURES.map((t) => <option key={t} value={t}>{t}</option>)}
                </select>
              </label>

              <label className="text-xs text-white/50 space-y-1.5">
                Male Frame
                <select
                  value={form.male_frame}
                  onChange={(e) => setForm((prev) => ({ ...prev, male_frame: e.target.value }))}
                  className="w-full rounded-lg bg-background border b-soft px-3 py-2 text-sm outline-none focus:border-gold-500/35"
                >
                  {FRAMES.map((f) => <option key={f} value={f}>{f}</option>)}
                </select>
              </label>

              <label className="text-xs text-white/50 space-y-1.5">
                Primary Color
                <input
                  type="color"
                  value={form.primary_color}
                  onChange={(e) => setForm((prev) => ({ ...prev, primary_color: e.target.value }))}
                  className="h-10 w-full rounded-lg bg-background border b-soft"
                />
              </label>

              <label className="text-xs text-white/50 space-y-1.5">
                Secondary Color
                <input
                  type="color"
                  value={form.secondary_color}
                  onChange={(e) => setForm((prev) => ({ ...prev, secondary_color: e.target.value }))}
                  className="h-10 w-full rounded-lg bg-background border b-soft"
                />
              </label>

              <label className="text-xs text-white/50 space-y-1.5">
                Accent Color
                <input
                  type="color"
                  value={form.accent_color}
                  onChange={(e) => setForm((prev) => ({ ...prev, accent_color: e.target.value }))}
                  className="h-10 w-full rounded-lg bg-background border b-soft"
                />
              </label>

              <label className="text-xs text-white/50 space-y-1.5">
                Female Frame
                <select
                  value={form.female_frame}
                  onChange={(e) => setForm((prev) => ({ ...prev, female_frame: e.target.value }))}
                  className="w-full rounded-lg bg-background border b-soft px-3 py-2 text-sm outline-none focus:border-gold-500/35"
                >
                  {FRAMES.map((f) => <option key={f} value={f}>{f}</option>)}
                </select>
              </label>
            </section>

            <section className="rounded-xl border b-soft bg-surface p-4 space-y-3">
              <div className="text-sm font-bold">Logo Upload</div>
              <label className="inline-flex items-center gap-2 px-3 py-2 rounded-lg border b-soft hover:bg-white/5 cursor-pointer text-sm">
                <ImageIcon size={15} /> رفع شعار
                <input type="file" accept="image/*" className="hidden" onChange={(e) => onUploadLogo(e.target.files?.[0])} />
              </label>
              <input
                value={form.logo}
                onChange={(e) => setForm((prev) => ({ ...prev, logo: e.target.value }))}
                placeholder="رابط الشعار أو Base64"
                className="w-full rounded-lg bg-background border b-soft px-3 py-2 text-sm outline-none focus:border-gold-500/35"
              />
              {form.logo ? (
                <div className="h-24 w-24 rounded-xl border border-white/10 bg-background/70 overflow-hidden">
                  <img src={form.logo} alt="Logo" className="h-full w-full object-cover" />
                </div>
              ) : null}
            </section>

            <button
              onClick={save}
              disabled={!canEdit || saving}
              className="px-5 py-2.5 rounded-lg bg-gold-500 text-black font-bold hover:bg-gold-400 disabled:opacity-50 disabled:cursor-not-allowed inline-flex items-center gap-2"
            >
              <CheckCircle2 size={16} /> {saving ? "جارٍ الحفظ..." : "حفظ تصميم الزي"}
            </button>
            {!canEdit && (
              <div className="text-xs text-amber-300/80">يستطيع القائد/النواب أو الإدارة فقط تعديل تصميم الزي.</div>
            )}
          </div>

          <aside className="rounded-2xl border b-soft bg-surface p-4">
            <div className="text-xs text-white/45">معاينة الدمج التلقائي على الآفاتار</div>
            <div className="mt-3 inline-flex rounded-md border border-white/10 overflow-hidden">
              <button
                onClick={() => setPreviewGender("male")}
                className={`px-3 py-1.5 text-xs ${previewGender === "male" ? "bg-gold-500 text-black font-bold" : "bg-background text-white/70"}`}
              >
                Male
              </button>
              <button
                onClick={() => setPreviewGender("female")}
                className={`px-3 py-1.5 text-xs ${previewGender === "female" ? "bg-gold-500 text-black font-bold" : "bg-background text-white/70"}`}
              >
                Female
              </button>
            </div>

            <div className="mt-4 rounded-xl border border-white/10 bg-background p-4 min-h-[280px] flex flex-col items-center justify-center">
              <div
                className="h-44 w-36 rounded-2xl border border-white/15 relative overflow-hidden"
                style={{
                  background: `linear-gradient(160deg, ${form.primary_color} 0%, ${form.secondary_color} 65%, ${form.accent_color || form.primary_color} 100%)`,
                }}
              >
                <div className="absolute top-3 left-3 text-[10px] px-1.5 py-0.5 rounded bg-black/35 border border-white/20">{form.base_texture}</div>
                <div className="absolute bottom-2 inset-x-2 text-[10px] text-center text-white/90 bg-black/30 rounded px-1 py-1">
                  frame: {activeFrame}
                </div>
                {form.logo && <img src={form.logo} alt="clan logo" className="absolute top-10 right-4 h-8 w-8 rounded-full border border-white/30 object-cover" />}
                {rivalsBadge && <img src={rivalsBadge} alt="rivals badge" className="absolute top-10 left-4 h-8 w-8 rounded-full border border-white/30 object-cover" />}
              </div>

              <p className="mt-4 text-xs text-white/55 text-center leading-5">
                يتم اختيار إطار الزي تلقائياً حسب جنس الآفاتار النشط ({previewGender}) ثم تطبيق الألوان/الشعار عليه.
              </p>
            </div>
          </aside>
        </div>
      )}
    </div>
  );
}
