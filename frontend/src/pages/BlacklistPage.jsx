import { useEffect, useState, useCallback } from "react";
import api, { formatApiErrorDetail } from "../api";
import { useAuth } from "../AuthContext";
import { AlertOctagon, Plus, Trash2, ShieldOff, Image as ImageIcon } from "lucide-react";
import { toast } from "sonner";

const PROOF_MAX = 3_000_000;

function readAsDataURL(file) {
  return new Promise((resolve, reject) => {
    const r = new FileReader();
    r.onload = () => resolve(r.result);
    r.onerror = reject;
    r.readAsDataURL(file);
  });
}

function AddForm({ onCreated }) {
  const [form, setForm] = useState({
    player_name: "",
    player_user_id: "",
    player_email: "",
    cheat_tool: "",
    details: "",
    proof_image: "",
  });
  const [searchResults, setSearchResults] = useState([]);
  const [busy, setBusy] = useState(false);

  const searchUser = async (q) => {
    setForm({ ...form, player_name: q });
    if (!q || q.length < 2) return setSearchResults([]);
    try {
      const { data } = await api.get("/users/search", { params: { q } });
      setSearchResults(data.slice(0, 5));
    } catch {
      setSearchResults([]);
    }
  };

  const pickUser = (u) => {
    setForm({ ...form, player_name: u.username, player_user_id: u.id, player_email: u.email });
    setSearchResults([]);
  };

  const onProof = async (e) => {
    const f = e.target.files?.[0];
    if (!f) return;
    if (f.size > PROOF_MAX) return toast.error("الصورة كبيرة (الحد 3MB)");
    setForm({ ...form, proof_image: await readAsDataURL(f) });
  };

  const submit = async (e) => {
    e.preventDefault();
    if (!form.player_name || !form.cheat_tool) return toast.error("الاسم وأداة الغش إلزاميان");
    setBusy(true);
    try {
      await api.post("/blacklist", form);
      toast.success("تم إضافة اللاعب للقائمة السوداء");
      setForm({ player_name: "", player_user_id: "", player_email: "", cheat_tool: "", details: "", proof_image: "" });
      onCreated();
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail));
    } finally {
      setBusy(false);
    }
  };

  return (
    <form onSubmit={submit} className="bg-surface border b-soft rounded-xl p-5 space-y-3" data-testid="blacklist-form">
      <h2 className="font-display font-black text-xl flex items-center gap-2">
        <Plus className="text-destructive" /> إضافة لاعب غشاش
      </h2>
      <div className="relative">
        <label className="text-xs uppercase tracking-widest text-white/50 mb-1 block">اسم اللاعب</label>
        <input
          data-testid="bl-player-name"
          required
          value={form.player_name}
          onChange={(e) => searchUser(e.target.value)}
          placeholder="ابحث باسم المستخدم أو اكتب يدوياً"
          className="w-full bg-background border b-soft rounded-md px-3 py-2 outline-none focus:border-destructive/50 text-sm"
        />
        {searchResults.length > 0 && (
          <div className="absolute z-10 top-full mt-1 right-0 left-0 bg-background border b-soft rounded-md shadow-lg overflow-hidden">
            {searchResults.map((u) => (
              <button type="button" key={u.id} onClick={() => pickUser(u)} className="w-full text-right p-2 hover:bg-white/5 flex items-center gap-2 text-sm">
                <span className="font-bold">{u.username}</span>
                <span className="text-xs text-white/40">{u.email}</span>
              </button>
            ))}
          </div>
        )}
      </div>
      <div>
        <label className="text-xs uppercase tracking-widest text-white/50 mb-1 block">أداة الغش</label>
        <input
          data-testid="bl-cheat-tool"
          required
          value={form.cheat_tool}
          onChange={(e) => setForm({ ...form, cheat_tool: e.target.value })}
          placeholder="Aimbot, Wallhack, ..."
          className="w-full bg-background border b-soft rounded-md px-3 py-2 outline-none focus:border-destructive/50 text-sm"
        />
      </div>
      <div>
        <label className="text-xs uppercase tracking-widest text-white/50 mb-1 block">التفاصيل</label>
        <textarea
          data-testid="bl-details"
          value={form.details}
          onChange={(e) => setForm({ ...form, details: e.target.value })}
          rows={3}
          placeholder="تفاصيل الواقعة، الوقت، المباراة..."
          className="w-full bg-background border b-soft rounded-md px-3 py-2 outline-none focus:border-destructive/50 text-sm resize-none"
        />
      </div>
      <div>
        <label className="text-xs uppercase tracking-widest text-white/50 mb-1 block">إثبات الغش (صورة)</label>
        <label className="cursor-pointer inline-flex items-center gap-2 px-3 py-2 rounded-md bg-background border b-soft hover:border-destructive/40 text-sm">
          <ImageIcon size={14} />
          <span>{form.proof_image ? "تم اختيار صورة" : "اختر صورة"}</span>
          <input data-testid="bl-proof-input" type="file" accept="image/*" onChange={onProof} className="hidden" />
        </label>
        {form.proof_image && (
          <img src={form.proof_image} alt="proof" className="mt-2 max-h-40 rounded border b-soft" />
        )}
      </div>
      <button
        data-testid="bl-submit"
        disabled={busy}
        type="submit"
        className="px-4 py-2 rounded-md bg-destructive text-white font-bold hover:bg-destructive/90 disabled:opacity-50"
      >
        {busy ? "..." : "إضافة للقائمة"}
      </button>
    </form>
  );
}

export default function BlacklistPage() {
  const { user } = useAuth();
  const [items, setItems] = useState([]);

  const load = useCallback(async () => {
    try {
      const { data } = await api.get("/blacklist");
      setItems(data);
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail));
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const remove = async (id) => {
    // eslint-disable-next-line no-alert
    if (!confirm("حذف هذا السجل من القائمة السوداء؟")) return;
    try {
      await api.delete(`/blacklist/${id}`);
      toast.success("تم الحذف");
      load();
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail));
    }
  };

  if (!user || (user.role !== "admin" && user.role !== "owner")) {
    return (
      <div className="bg-surface border b-soft rounded-xl p-12 text-center" data-testid="blacklist-denied">
        <AlertOctagon size={32} className="mx-auto mb-3 text-destructive" />
        صفحة القائمة السوداء للمنظمين والمالك فقط
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-display font-black text-3xl md:text-4xl flex items-center gap-3">
          <ShieldOff className="text-destructive" /> القائمة السوداء
        </h1>
        <p className="text-white/50 mt-1">سجل اللاعبين الغشاشين مع إثباتات. تظهر هذه الصفحة فقط للمنظمين والمالك.</p>
      </div>

      <div className="grid lg:grid-cols-2 gap-6">
        <AddForm onCreated={load} />

        <section>
          <h2 className="font-display font-black text-xl mb-3">السجلات ({items.length})</h2>
          <div className="space-y-3 max-h-[700px] overflow-y-auto pl-1">
            {items.length === 0 && (
              <div className="bg-surface border b-soft rounded-lg p-8 text-center text-white/40 text-sm">
                لا توجد سجلات بعد
              </div>
            )}
            {items.map((b) => (
              <article
                key={b.id}
                data-testid={`blacklist-item-${b.id}`}
                className="bg-surface border border-destructive/20 rounded-lg p-4 space-y-2"
              >
                <div className="flex items-start justify-between gap-2 flex-wrap">
                  <div>
                    <div className="text-xs uppercase tracking-widest text-destructive">غشاش</div>
                    <div className="font-display font-black text-lg">{b.player_name}</div>
                    {b.player_account?.email && (
                      <div className="text-xs text-white/50">{b.player_account.email}</div>
                    )}
                  </div>
                  <button
                    data-testid={`bl-delete-${b.id}`}
                    onClick={() => remove(b.id)}
                    className="p-2 rounded text-destructive hover:bg-destructive/10"
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
                <div className="text-sm">
                  <span className="text-white/40">أداة الغش: </span>
                  <span className="font-bold text-destructive">{b.cheat_tool}</span>
                </div>
                {b.player_account && (
                  <div className="text-xs text-white/60 bg-background border b-soft rounded p-2">
                    <div><span className="text-white/40">المعرف: </span>{b.player_account.id}</div>
                    {b.player_account.act && <div><span className="text-white/40">Activision: </span>{b.player_account.act}</div>}
                    {b.player_account.clan_id && <div><span className="text-white/40">الكلان: </span>{b.player_account.clan_id}</div>}
                    <div><span className="text-white/40">النقاط: </span>{b.player_account.points || 0}</div>
                  </div>
                )}
                {b.details && (
                  <div className="text-sm text-white/70 whitespace-pre-wrap">{b.details}</div>
                )}
                {b.proof_image && (
                  <img src={b.proof_image} alt="proof" className="rounded max-h-72 border b-soft" />
                )}
                <div className="text-[10px] text-white/30 flex justify-between">
                  <span>أضيف بواسطة: {b.added_by_username}</span>
                  <span>{new Date(b.created_at).toLocaleString("ar")}</span>
                </div>
              </article>
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}
