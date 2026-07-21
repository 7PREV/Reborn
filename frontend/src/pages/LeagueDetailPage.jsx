import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ChevronRight, Crown, Edit, ListOrdered, Loader2, Plus, Save, ScrollText, Trash2, Trophy, X } from "lucide-react";
import api, { formatApiErrorDetail } from "../api";
import { toast } from "sonner";
import { useAuth } from "../AuthContext";

async function fileToDataUrl(file) {
  return await new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result || ""));
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}

function LeagueDetailPageLegacy() {
  const QUALIFY_TOP = 4;
  const { id } = useParams();
  const { user } = useAuth();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [league, setLeague] = useState(null);
  const [standings, setStandings] = useState([]);
  const [leagueRules, setLeagueRules] = useState([]);
  const [activeTab, setActiveTab] = useState("standings");
  const [rulesLoaded, setRulesLoaded] = useState(false);
  const [rulesLoading, setRulesLoading] = useState(false);
  const [editingRule, setEditingRule] = useState(null);
  const [creatingRule, setCreatingRule] = useState(false);
  const [savingRule, setSavingRule] = useState(false);
  const [form, setForm] = useState({ title: "", body: "", order: 1, images: [] });

  const isStaff = user?.role === "admin" || user?.role === "owner";

  const loadLeagueDetails = useCallback(async () => {
    if (!id) return;
    setLoading(true);
    setError("");
    try {
      const { data } = await api.get(`/leagues/${id}/leaderboard`);
      setLeague(data?.league || null);
      setStandings(Array.isArray(data?.standings) ? data.standings : []);
    } catch (err) {
      setLeague(null);
      setStandings([]);
      setError(formatApiErrorDetail(err?.response?.data?.detail ?? err?.message));
    } finally {
      setLoading(false);
    }
  }, [id]);

  const loadRules = useCallback(async () => {
    if (!id) return;
    setRulesLoading(true);
    try {
      const { data } = await api.get(`/leagues/${id}/rules`);
      const normalized = Array.isArray(data)
        ? data.map((rule) => ({
            ...rule,
            images: Array.isArray(rule?.images)
              ? rule.images.filter((img) => typeof img === "string" && img)
              : rule?.image
                ? [rule.image]
                : [],
          }))
        : [];
      setLeagueRules(normalized);
    } catch {
      setLeagueRules([]);
    } finally {
      setRulesLoading(false);
    }
  }, [id]);

  useEffect(() => {
    (async () => {
      await loadLeagueDetails();
    })();
  }, [loadLeagueDetails]);

  useEffect(() => {
    if (activeTab !== "rules" || rulesLoaded) return;
    (async () => {
      await loadRules();
      setRulesLoaded(true);
    })();
  }, [activeTab, rulesLoaded, loadRules]);

  const rulesImages = useMemo(
    () => leagueRules.flatMap((rule) => (Array.isArray(rule.images) ? rule.images : [])),
    [leagueRules],
  );

  const startCreateRule = () => {
    setCreatingRule(true);
    setEditingRule(null);
    setForm({ title: "", body: "", order: leagueRules.length + 1, images: [] });
  };

  const startEditRule = (rule) => {
    setCreatingRule(false);
    setEditingRule(rule.id);
    const images = Array.isArray(rule.images)
      ? rule.images
      : rule.image
        ? [rule.image]
        : [];
    setForm({
      title: rule.title || "",
      body: rule.body || "",
      order: Number(rule.order || 1),
      images,
    });
  };

  const cancelRuleForm = () => {
    setCreatingRule(false);
    setEditingRule(null);
    setForm({ title: "", body: "", order: 1, images: [] });
  };

  const onPickImages = async (e) => {
    const files = Array.from(e.target.files || []);
    if (!files.length) return;
    const convertedList = [];
    for (const file of files) {
      if (file.size > 3_000_000) {
        toast.error(`الصورة ${file.name} كبيرة (الحد 3MB)`);
        continue;
      }
      // eslint-disable-next-line no-await-in-loop
      const converted = await fileToDataUrl(file);
      if (converted) convertedList.push(converted);
    }
    if (!convertedList.length) return;
    setForm((prev) => ({ ...prev, images: [...prev.images, ...convertedList] }));
    e.target.value = "";
  };

  const removeImageAt = (idx) => {
    setForm((prev) => ({ ...prev, images: prev.images.filter((_, i) => i !== idx) }));
  };

  const saveRule = async (e) => {
    e.preventDefault();
    setSavingRule(true);
    try {
      const payload = {
        title: form.title,
        body: form.body,
        order: Number(form.order || 1),
        images: form.images,
      };
      if (editingRule) {
        await api.put(`/leagues/${id}/rules/${editingRule}`, payload);
        toast.success("تم تحديث القاعدة");
      } else {
        await api.post(`/leagues/${id}/rules`, payload);
        toast.success("تمت إضافة القاعدة");
      }
      cancelRuleForm();
      await loadRules();
      await loadLeagueDetails();
    } catch (err) {
      toast.error(formatApiErrorDetail(err?.response?.data?.detail));
    } finally {
      setSavingRule(false);
    }
  };

  const deleteRule = async (ruleId) => {
    // eslint-disable-next-line no-alert
    if (!confirm("حذف القاعدة؟")) return;
    try {
      await api.delete(`/leagues/${id}/rules/${ruleId}`);
      toast.success("تم حذف القاعدة");
      await loadRules();
      await loadLeagueDetails();
    } catch (err) {
      toast.error(formatApiErrorDetail(err?.response?.data?.detail));
    }
  };

  return (
    <div className="space-y-6" dir="rtl">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h1 className="font-display font-black text-3xl md:text-4xl flex items-center gap-3">
            <Trophy className="text-gold-500" /> {league?.name || "تفاصيل الدوري"}
          </h1>
          {league?.game && <p className="text-white/50 mt-1">{league.game}</p>}
        </div>
        <Link
          to="/leagues"
          className="text-xs text-white/60 hover:text-gold-500 inline-flex items-center gap-1"
        >
          <ChevronRight size={14} /> العودة للدوريات
        </Link>
      </div>

      <div className="flex justify-end">
        <div className="w-full sm:w-auto">
          <div className="inline-flex items-center bg-gradient-to-l from-surface/95 via-surface to-background/90 border border-royalGold-500/20 rounded-2xl p-1.5 shadow-[0_6px_30px_rgba(0,0,0,0.35)] backdrop-blur-sm">
            <button
              onClick={() => setActiveTab("standings")}
              className={`px-5 py-2.5 rounded-xl text-sm inline-flex items-center gap-2 transition-all duration-200 border ${
                activeTab === "standings"
                  ? "bg-gradient-to-l from-royalGold-700 via-royalGold-600 to-royalGold-500 text-white font-extrabold border-royalGold-300/40 shadow-[0_0_15px_rgba(203,213,225,0.22)]"
                  : "text-gray-400 border-transparent hover:text-white hover:bg-white/5"
              }`}
              data-testid="league-tab-standings"
            >
              <ListOrdered size={15} /> ترتيب الكلانات
            </button>
            <button
              onClick={() => setActiveTab("rules")}
              className={`px-5 py-2.5 rounded-xl text-sm inline-flex items-center gap-2 transition-all duration-200 border ${
                activeTab === "rules"
                  ? "bg-gradient-to-l from-royalGold-700 via-royalGold-600 to-royalGold-500 text-white font-extrabold border-royalGold-300/40 shadow-[0_0_15px_rgba(203,213,225,0.22)]"
                  : "text-gray-400 border-transparent hover:text-white hover:bg-white/5"
              }`}
              data-testid="league-tab-rules"
            >
              <ScrollText size={15} /> القوانين
            </button>
          </div>
          <div className="mt-2 h-px w-full bg-gradient-to-l from-transparent via-royalGold-500/50 to-transparent" />
        </div>
      </div>

      {loading && (
        <div className="bg-surface border b-soft rounded-xl p-10 text-center text-white/50 inline-flex items-center gap-2">
          <Loader2 className="h-4 w-4 animate-spin" /> جاري تحميل بيانات الدوري...
        </div>
      )}

      {!loading && error && (
        <div className="bg-rose-500/10 border border-rose-500/30 rounded-xl p-4 text-rose-300">
          {error}
        </div>
      )}

      {!loading && !error && activeTab === "standings" && (
        <section className="bg-surface border b-soft rounded-xl overflow-hidden" data-testid="league-detail-standings">
          <div className="px-5 py-4 border-b b-soft">
            <h2 className="font-display font-black text-xl">ترتيب الكلانات</h2>
            <p className="text-xs text-white/45 mt-1">أول 4 مراكز تتأهل إلى بطولة السوبر رايفلز.</p>
          </div>

          {standings.length === 0 ? (
            <div className="p-8 text-white/45 text-sm">لا توجد بيانات ترتيب حتى الآن.</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-right text-sm" data-testid="league-standings-table">
                <thead className="bg-white/5 text-[10px] uppercase tracking-widest text-white/50">
                  <tr>
                    <th className="py-3 px-4 w-12">#</th>
                    <th className="py-3 px-4">الكلان</th>
                    <th className="py-3 px-4 w-24 text-center">فوز/خسارة</th>
                    <th className="py-3 px-4 w-20 text-end">النقاط</th>
                    <th className="py-3 px-4 w-40 text-end">التأهل</th>
                  </tr>
                </thead>
                <tbody>
                  {standings.map((r, idx) => {
                    const qualified = idx < QUALIFY_TOP;
                    return (
                      <tr
                        key={r.clan_id}
                        data-testid={`league-standings-row-${r.clan_id}`}
                        className={`border-t b-soft transition hover:bg-white/5 ${qualified ? "bg-emerald-500/10" : ""}`}
                        style={
                          qualified
                            ? {
                                boxShadow:
                                  "inset 0 0 0 1px rgba(16,185,129,0.35), inset 0 0 26px rgba(16,185,129,0.18)",
                              }
                            : undefined
                        }
                      >
                        <td className="py-3 px-4">
                          {idx === 0 ? (
                            <span className="inline-grid place-items-center h-8 w-8 rounded-md bg-gradient-to-b from-royalGold-200 via-royalGold-400 to-royalGold-700 text-white shadow-[0_0_14px_rgba(203,213,225,0.3)]">
                              <Crown size={14} className="inline-block" />
                            </span>
                          ) : idx === 1 ? (
                            <span className="inline-grid place-items-center h-8 w-8 rounded-md bg-gradient-to-b from-gray-100 via-gray-300 to-gray-500 text-black shadow-[0_0_12px_rgba(229,231,235,0.3)] font-display font-black">
                              2
                            </span>
                          ) : idx === 2 ? (
                            <span className="inline-grid place-items-center h-8 w-8 rounded-md bg-gradient-to-b from-slate-200 via-slate-400 to-slate-600 text-white shadow-[0_0_12px_rgba(148,163,184,0.32)] font-display font-black">
                              3
                            </span>
                          ) : (
                            <span className={qualified ? "text-emerald-300 font-semibold" : "text-white/40"}>{idx + 1}</span>
                          )}
                        </td>
                        <td className="py-3 px-4">
                          <Link
                            to={`/clans/${r.clan_id}`}
                            className={`inline-flex items-center gap-2 rounded-md px-2 py-1 hover:text-gold-500 ${qualified ? "text-emerald-300 border border-emerald-400/40" : ""}`}
                            style={
                              qualified
                                ? {
                                    boxShadow:
                                      "0 0 12px rgba(16,185,129,0.45), 0 0 24px rgba(16,185,129,0.2)",
                                  }
                                : undefined
                            }
                          >
                            <span className="text-[10px] text-gold-500">[{r.clan_tag}]</span>
                            <span className="font-semibold">{r.clan_name}</span>
                          </Link>
                        </td>
                        <td className="py-3 px-4 text-center text-xs">
                          <span className="text-emerald-400">{r.wins}</span>
                          <span className="text-white/30 mx-1">/</span>
                          <span className="text-rose-400">{r.losses}</span>
                        </td>
                        <td className={`py-3 px-4 text-end font-bold ${qualified ? "text-emerald-300" : "text-gold-500"}`}>{r.points}</td>
                        <td className="py-3 px-4 text-end">
                          {qualified ? (
                            <span
                              className="text-[10px] uppercase tracking-widest text-emerald-300 border border-emerald-400/40 rounded px-2 py-1"
                              style={{ boxShadow: "0 0 10px rgba(16,185,129,0.35)" }}
                            >
                              مؤهل لبطولة السوبر رايفلز
                            </span>
                          ) : null}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </section>
      )}

      {!loading && !error && activeTab === "rules" && (
        <section className="bg-surface border b-soft rounded-xl overflow-hidden" data-testid="league-detail-rules">
          <div className="px-5 py-4 border-b b-soft flex items-center justify-between gap-3">
            <h2 className="font-display font-black text-xl">القوانين</h2>
            {isStaff && (
              <button
                onClick={startCreateRule}
                className="px-3 py-2 rounded-md bg-gold-500 text-black text-sm font-bold hover:bg-gold-400 inline-flex items-center gap-1"
                data-testid="league-add-rule-btn"
              >
                <Plus size={14} /> قاعدة جديدة
              </button>
            )}
          </div>
          <div className="p-5 space-y-5">
            {(creatingRule || editingRule) && isStaff && (
              <form onSubmit={saveRule} className="rounded-xl border b-soft bg-background/35 p-4 space-y-3" data-testid="league-rule-form">
                <input
                  required
                  value={form.title}
                  onChange={(e) => setForm((p) => ({ ...p, title: e.target.value }))}
                  placeholder="عنوان القاعدة"
                  className="w-full bg-background border b-soft rounded-md px-3 py-2 outline-none focus:border-gold-500/40"
                />
                <textarea
                  value={form.body}
                  onChange={(e) => setForm((p) => ({ ...p, body: e.target.value }))}
                  placeholder="وصف القاعدة"
                  rows={3}
                  className="w-full bg-background border b-soft rounded-md px-3 py-2 outline-none focus:border-gold-500/40 resize-none"
                />
                <input
                  type="number"
                  value={form.order}
                  onChange={(e) => setForm((p) => ({ ...p, order: Number(e.target.value) }))}
                  className="w-28 bg-background border b-soft rounded-md px-3 py-2 outline-none focus:border-gold-500/40"
                />
                <label className="inline-flex items-center gap-2 px-3 py-2 rounded-md border b-soft bg-background hover:border-gold-500/35 cursor-pointer text-sm">
                  <Plus size={14} /> رفع صور
                  <input type="file" accept="image/*" multiple className="hidden" onChange={onPickImages} />
                </label>
                {form.images.length > 0 && (
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
                    {form.images.map((img, idx) => (
                      <div key={`form-rule-img-${idx}`} className="relative rounded-md border b-soft overflow-hidden bg-black/20">
                        <img src={img} alt={`rule-${idx}`} className="h-24 w-full object-cover" />
                        <button
                          type="button"
                          onClick={() => removeImageAt(idx)}
                          className="absolute top-1 left-1 h-6 w-6 rounded bg-black/70 text-white/90 grid place-items-center hover:bg-destructive"
                        >
                          <X size={12} />
                        </button>
                      </div>
                    ))}
                  </div>
                )}
                <div className="flex items-center gap-2">
                  <button type="submit" disabled={savingRule} className="px-4 py-2 rounded-md bg-gold-500 text-black font-bold hover:bg-gold-400 inline-flex items-center gap-1 disabled:opacity-60">
                    <Save size={14} /> {savingRule ? "..." : "حفظ"}
                  </button>
                  <button type="button" onClick={cancelRuleForm} className="px-4 py-2 rounded-md hover:bg-white/5 inline-flex items-center gap-1">
                    <X size={14} /> إلغاء
                  </button>
                </div>
              </form>
            )}

            {rulesLoading ? (
              <div className="text-white/45 text-sm inline-flex items-center gap-2">
                <Loader2 className="h-4 w-4 animate-spin" /> جاري تحميل القوانين...
              </div>
            ) : leagueRules.length > 0 ? (
              <div className="space-y-3" data-testid="league-rules-cards">
                {leagueRules.map((rule, idx) => (
                  <article key={rule.id} className="relative rounded-xl border border-white/10 bg-surface p-4 overflow-hidden">
                    <div className="absolute inset-y-0 right-0 w-1 bg-gradient-to-b from-gold-500/70 via-gold-500/35 to-transparent" />
                    <div className="flex flex-row-reverse items-start gap-3">
                      <div className="h-9 w-9 shrink-0 rounded bg-gold-500/10 text-gold-500 border border-gold-500/30 grid place-items-center font-display font-black shadow-[0_0_14px_rgba(245,158,11,0.2)]">
                        {idx + 1}
                      </div>
                      <div className="flex-1 min-w-0">
                        <h3 className="font-display font-black text-base text-white truncate">{rule.title}</h3>
                        <p className="text-sm text-white/65 mt-1 leading-7 whitespace-pre-wrap">{rule.body || "—"}</p>
                        {Array.isArray(rule.images) && rule.images.length > 0 && (
                          <div className="mt-3 grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4">
                            {rule.images.map((img, imageIdx) => (
                              <img
                                key={`${rule.id}-img-${imageIdx}`}
                                src={img}
                                alt={`${rule.title}-${imageIdx + 1}`}
                                className="w-full h-40 object-cover rounded-md border b-soft bg-black/20"
                                loading="lazy"
                              />
                            ))}
                          </div>
                        )}
                      </div>
                      {isStaff && (
                        <div className="flex items-center gap-1">
                          <button onClick={() => startEditRule(rule)} className="p-2 rounded hover:bg-white/5 text-white/60" title="تعديل">
                            <Edit size={15} />
                          </button>
                          <button onClick={() => deleteRule(rule.id)} className="p-2 rounded hover:bg-destructive/10 text-destructive" title="حذف">
                            <Trash2 size={15} />
                          </button>
                        </div>
                      )}
                    </div>
                  </article>
                ))}
              </div>
            ) : (
              <div className="text-white/45 text-sm">لا توجد قواعد مضافة لهذا الدوري.</div>
            )}

            {rulesImages.length > 0 ? (
              <div className="border-t b-soft pt-4">
                <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4">
                  {rulesImages.map((img, idx) => (
                    <img
                      key={`league-rule-image-${idx}`}
                      src={img}
                      alt={`صورة قوانين الدوري ${idx + 1}`}
                      className="w-full h-40 object-cover rounded-lg border b-soft bg-black/20"
                      loading="lazy"
                    />
                  ))}
                </div>
              </div>
            ) : (
              <div className="text-white/45 text-sm">لا توجد صور قوانين مرفوعة لهذا الدوري.</div>
            )}
          </div>
        </section>
      )}
    </div>
  );
}

export default function LeagueDetailPage() {
  return <LeagueDetailPageLegacy />;
}
