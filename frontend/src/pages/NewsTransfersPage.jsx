import { useCallback, useEffect, useMemo, useState } from "react";
import { ArrowRightLeft, RefreshCw, ScrollText, Sparkles } from "lucide-react";
import api from "../api";

const KIND_STYLE = {
  admin: "bg-gold-500/15 text-gold-500 border-gold-500/30",
  "match-start": "bg-destructive/15 text-rose-300 border-destructive/30",
  "match-score": "bg-indigo-500/15 text-indigo-300 border-indigo-500/30",
  "match-final": "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
  transfer_market: "bg-sky-500/15 text-sky-300 border-sky-500/30",
  system_profile: "bg-violet-500/15 text-violet-300 border-violet-500/30",
};

function fmtDate(value) {
  if (!value) return "—";
  try {
    return new Date(value).toLocaleString("ar");
  } catch {
    return value;
  }
}

function KindBadge({ kind }) {
  const cls = KIND_STYLE[kind] || "bg-white/10 text-white/70 border-white/20";
  return (
    <span className={`rounded-full border px-2.5 py-1 text-[10px] uppercase tracking-wider ${cls}`}>
      {kind || "news"}
    </span>
  );
}

function TransferClan({ clan, fallback }) {
  return (
    <div className="flex items-center gap-2 min-w-0">
      <div className="h-10 w-10 rounded-lg border border-white/10 bg-background/70 overflow-hidden grid place-items-center">
        {clan?.logo ? (
          <img src={clan.logo} alt={clan?.name || fallback} className="h-full w-full object-cover" />
        ) : (
          <span className="text-xs text-white/30">CLAN</span>
        )}
      </div>
      <div className="min-w-0">
        <div className="font-bold truncate">{clan?.name || fallback}</div>
        <div className="text-[11px] text-white/40">[{clan?.tag || "---"}]</div>
      </div>
    </div>
  );
}

export default function NewsTransfersPage() {
  const [tab, setTab] = useState("news");
  const [news, setNews] = useState([]);
  const [transfers, setTransfers] = useState([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [newsRes, transferRes] = await Promise.all([
        api.get("/news", { params: { limit: 100 } }),
        api.get("/transfers", { params: { limit: 100 } }),
      ]);
      setNews(newsRes.data || []);
      setTransfers(transferRes.data || []);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load().catch(() => {});
  }, [load]);

  const headline = useMemo(() => {
    const latest = news[0];
    if (!latest) return "تابع آخر أخبار المنصة والانتقالات لحظة بلحظة";
    return latest.title;
  }, [news]);

  return (
    <div className="space-y-6">
      <section className="relative overflow-hidden rounded-2xl border b-soft bg-surface p-6 md:p-8">
        <div className="absolute inset-0 bg-gradient-to-l from-gold-500/10 via-transparent to-transparent pointer-events-none" />
        <div className="relative flex items-start justify-between gap-4 flex-wrap">
          <div>
            <h1 className="font-display font-black text-3xl md:text-4xl flex items-center gap-3">
              <ScrollText className="text-gold-500" /> الأخبار والانتقالات
            </h1>
            <p className="text-white/55 mt-2 text-sm md:text-base">{headline}</p>
          </div>
          <button
            onClick={() => load()}
            className="px-3 py-2 rounded-lg border b-soft hover:bg-white/5 text-sm inline-flex items-center gap-2"
          >
            <RefreshCw size={14} /> تحديث
          </button>
        </div>
      </section>

      <div className="flex justify-end">
        <div className="w-full sm:w-auto">
          <div className="inline-flex items-center bg-gradient-to-l from-surface/95 via-surface to-background/90 border border-royalGold-500/20 rounded-2xl p-1.5 shadow-[0_6px_30px_rgba(0,0,0,0.35)] backdrop-blur-sm">
            <button
              onClick={() => setTab("news")}
              className={`px-5 py-2.5 rounded-xl text-sm inline-flex items-center gap-2 transition-all duration-200 border ${
                tab === "news"
                  ? "bg-gradient-to-l from-royalGold-700 via-royalGold-600 to-royalGold-500 text-white font-extrabold border-royalGold-300/40 shadow-[0_0_15px_rgba(203,213,225,0.22)]"
                  : "text-gray-400 border-transparent hover:text-white hover:bg-white/5"
              }`}
            >
              موجز الأخبار
            </button>
            <button
              onClick={() => setTab("transfers")}
              className={`px-5 py-2.5 rounded-xl text-sm inline-flex items-center gap-2 transition-all duration-200 border ${
                tab === "transfers"
                  ? "bg-gradient-to-l from-royalGold-700 via-royalGold-600 to-royalGold-500 text-white font-extrabold border-royalGold-300/40 shadow-[0_0_15px_rgba(203,213,225,0.22)]"
                  : "text-gray-400 border-transparent hover:text-white hover:bg-white/5"
              }`}
            >
              سوق الانتقالات
            </button>
          </div>
          <div className="mt-2 h-px w-full bg-gradient-to-l from-transparent via-royalGold-500/50 to-transparent" />
        </div>
      </div>

      {loading ? (
        <div className="grid gap-3">
          <div className="h-24 rounded-xl bg-surface border b-soft animate-pulse" />
          <div className="h-24 rounded-xl bg-surface border b-soft animate-pulse" />
          <div className="h-24 rounded-xl bg-surface border b-soft animate-pulse" />
        </div>
      ) : tab === "news" ? (
        <section className="space-y-3">
          {news.length === 0 ? (
            <div className="rounded-xl border b-soft bg-surface p-10 text-center text-white/45">لا توجد أخبار حالياً.</div>
          ) : news.map((item) => (
            <article key={item.id} className="rounded-xl border b-soft bg-surface p-4 md:p-5">
              <div className="flex items-center justify-between gap-3 flex-wrap">
                <KindBadge kind={item.kind} />
                <span className="text-xs text-white/40">{fmtDate(item.created_at)}</span>
              </div>
              <h3 className="mt-3 text-base md:text-lg font-black font-display">{item.title}</h3>
              {item.body ? <p className="mt-2 text-sm text-white/65 leading-6">{item.body}</p> : null}
              {item.kind === "match-score" && (
                <div className="mt-3 inline-flex items-center gap-1.5 text-xs text-indigo-300/90">
                  <Sparkles size={12} /> تحديث مباشر للنتيجة
                </div>
              )}
            </article>
          ))}
        </section>
      ) : (
        <section className="space-y-3">
          {transfers.length === 0 ? (
            <div className="rounded-xl border b-soft bg-surface p-10 text-center text-white/45">لا توجد انتقالات حديثة.</div>
          ) : transfers.map((t) => (
            <article key={t.id} className="rounded-xl border b-soft bg-surface p-4 md:p-5">
              <div className="flex items-start justify-between gap-3 flex-wrap">
                <div>
                  <h3 className="font-display font-black text-lg">{t.username || "لاعب"}</h3>
                  <p className="text-xs text-white/45 mt-1">قضى في ناديه السابق: {t.duration_label || "—"}</p>
                </div>
                <span className="text-xs text-white/40">{fmtDate(t.created_at)}</span>
              </div>

              <div className="mt-4 grid md:grid-cols-[1fr_auto_1fr] gap-3 items-center">
                <TransferClan clan={t.old_clan} fallback="النادي السابق" />
                <div className="mx-auto h-10 w-10 rounded-full border border-sky-500/30 bg-sky-500/10 grid place-items-center text-sky-300">
                  <ArrowRightLeft size={16} />
                </div>
                <TransferClan clan={t.new_clan} fallback="النادي الجديد" />
              </div>
            </article>
          ))}
        </section>
      )}
    </div>
  );
}
