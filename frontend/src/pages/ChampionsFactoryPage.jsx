import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Award, Crown, Loader2, Medal, Search, Sparkles, Trophy } from "lucide-react";
import api, { formatApiErrorDetail } from "../api";

// ─── Page ─────────────────────────────────────────────────────────────────────
function getSortTimestamp(value) {
  const dt = new Date(value || 0);
  return Number.isNaN(dt.getTime()) ? 0 : dt.getTime();
}

function formatDate(value) {
  if (!value) return "—";
  const dt = new Date(value);
  if (Number.isNaN(dt.getTime())) return String(value);
  return dt.toLocaleDateString("ar", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

function WinnerCard({ item, variant }) {
  const clan = item.clan || { id: null, name: "كلان غير معروف", tag: "---", is_plus: false };
  const isTournament = variant === "tournament";

  return (
    <Link
      to={clan.id ? `/clans/${clan.id}` : "/clans"}
      className={`group block overflow-hidden rounded-[1.75rem] border bg-slate-950/90 text-right transition-transform duration-300 hover:-translate-y-1 ${
        isTournament
          ? "animate-gold-glow border-royalGold-500/70 shadow-[0_0_34px_rgba(203,213,225,0.14)]"
          : "border-white/10 shadow-[0_0_24px_rgba(0,0,0,0.2)]"
      }`}
    >
      <div
        className={`h-1 w-full ${
          isTournament
            ? "bg-gradient-to-r from-transparent via-royalGold-500 to-transparent"
            : "bg-gradient-to-r from-transparent via-white/20 to-transparent"
        }`}
      />

      <div className={`p-5 ${isTournament ? "bg-gradient-to-b from-royalGold-500/10 via-transparent to-transparent" : "bg-gradient-to-b from-white/[0.03] to-transparent"}`}>
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className={`inline-flex items-center gap-2 rounded-full border px-3 py-1 text-[10px] font-bold uppercase tracking-[0.25em] ${isTournament ? "border-royalGold-500/30 bg-royalGold-500/10 text-royalGold-400" : "border-white/10 bg-white/[0.03] text-white/45"}`}>
              {isTournament ? <Trophy size={11} /> : <Award size={11} />}
              {isTournament ? "قسم البطولات" : "قسم الدوريات"}
            </div>

            <h3 className="mt-4 text-xl font-black text-white">{item.eventName}</h3>
            <p className="mt-1 text-sm leading-6 text-slate-400">{item.eventMeta}</p>
          </div>

          <div
            className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl border ${
              isTournament
                ? "border-royalGold-500/30 bg-royalGold-500/10 text-royalGold-400"
                : "border-white/10 bg-white/[0.03] text-white/70"
            }`}
          >
            {isTournament ? <Trophy size={18} /> : <Medal size={18} />}
          </div>
        </div>
      </div>

      <div className="border-t border-white/6 p-5">
        <div className="flex items-center gap-4">
          <div
            className={`flex h-14 w-14 items-center justify-center rounded-2xl border font-black ${
              isTournament
                ? "border-royalGold-500/30 bg-royalGold-500/10 text-royalGold-400"
                : "border-white/10 bg-white/[0.03] text-white"
            }`}
          >
            {clan.tag.slice(0, 2).toUpperCase()}
          </div>

          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <p className="truncate text-lg font-bold text-white">{clan.name}</p>
              {clan.is_plus && <Crown size={14} className="text-royalGold-500" />}
            </div>
            <p className="mt-0.5 text-xs uppercase tracking-widest text-white/40">
              [{clan.tag}] • {item.statusLabel}
            </p>
          </div>

          <div className="text-left">
            <p className="text-xs text-white/35">{item.dateLabel}</p>
            <p className={`mt-1 text-sm font-semibold ${isTournament ? "text-royalGold-400" : "text-slate-200"}`}>
              {item.badgeLabel}
            </p>
          </div>
        </div>
      </div>

      <div className={`flex items-center justify-between border-t px-5 py-3 text-xs ${isTournament ? "border-royalGold-500/10 bg-royalGold-500/5" : "border-white/6 bg-white/[0.02]"}`}>
        <span className="text-white/45">{item.detailLeft}</span>
        <span className={isTournament ? "text-royalGold-400" : "text-white/70"}>{item.detailRight}</span>
      </div>
    </Link>
  );
}

function EmptySection({ title, description }) {
  return (
    <div className="rounded-[1.5rem] border border-dashed border-white/10 bg-white/[0.02] p-8 text-center">
      <p className="text-lg font-bold text-white">{title}</p>
      <p className="mx-auto mt-2 max-w-xl text-sm leading-7 text-white/45">{description}</p>
    </div>
  );
}

export default function ChampionsFactoryPage() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [tournamentWinners, setTournamentWinners] = useState(() => []);
  const [leagueWinners, setLeagueWinners] = useState(() => []);
  const [searchTerm, setSearchTerm] = useState("");
  const [debouncedSearchTerm, setDebouncedSearchTerm] = useState("");

  useEffect(() => {
    const id = setTimeout(() => {
      setDebouncedSearchTerm(searchTerm.trim());
    }, 250);
    return () => clearTimeout(id);
  }, [searchTerm]);

  useEffect(() => {
    let alive = true;

    async function loadData() {
      setLoading(true);
      setError("");
      try {
        const params = debouncedSearchTerm ? { q: debouncedSearchTerm } : undefined;
        const { data } = await api.get("/champions-factory", { params });

        const tournaments = (data?.tournaments || []).map((t) => ({
          id: t.id,
          eventName: t.event_name,
          eventMeta: t.event_meta,
          statusLabel: t.status_label,
          dateLabel: formatDate(t.date_label),
          sortKey: getSortTimestamp(t.sort_key || t.date_label),
          badgeLabel: t.badge_label,
          detailLeft: t.detail_left,
          detailRight: t.detail_right,
          clan: t.clan,
        })).sort((a, b) => b.sortKey - a.sortKey);

        const leagues = (data?.leagues || []).map((l) => ({
          id: l.id,
          eventName: l.event_name,
          eventMeta: l.event_meta,
          statusLabel: l.status_label,
          dateLabel: formatDate(l.date_label),
          sortKey: getSortTimestamp(l.sort_key || l.date_label),
          badgeLabel: l.badge_label,
          detailLeft: l.detail_left,
          detailRight: l.detail_right,
          clan: l.clan,
        })).sort((a, b) => b.sortKey - a.sortKey);

        if (!alive) return;
        setTournamentWinners(Array.isArray(tournaments) ? tournaments : []);
        setLeagueWinners(Array.isArray(leagues) ? leagues : []);
      } catch (err) {
        if (!alive) return;
        setTournamentWinners([]);
        setLeagueWinners([]);
        setError(formatApiErrorDetail(err?.response?.data?.detail ?? err?.message));
      } finally {
        if (alive) setLoading(false);
      }
    }

    loadData();
    return () => {
      alive = false;
    };
  }, [debouncedSearchTerm]);

  const stats = useMemo(
    () => [
      { label: "إجمالي التتويجات", value: tournamentWinners.length + leagueWinners.length, icon: Crown, tone: "gold" },
      { label: "أبطال الدوريات", value: leagueWinners.length, icon: Award, tone: "silver" },
      { label: "أبطال البطولات", value: tournamentWinners.length, icon: Trophy, tone: "champion" },
    ],
    [tournamentWinners.length, leagueWinners.length],
  );

  return (
    <div className="min-h-screen bg-background" dir="rtl">
      <section className="relative overflow-hidden border-b border-white/6 bg-gradient-to-b from-slate-900 to-background px-4 py-14 sm:px-6 lg:px-8">
        <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
          <div className="h-[360px] w-[620px] rounded-full bg-royalGold-500/5 blur-[120px]" />
        </div>

        <div className="relative mx-auto max-w-5xl text-center">
          <span className="inline-flex items-center gap-2 rounded-full border border-royalGold-500/30 bg-royalGold-500/10 px-4 py-1 text-xs font-semibold uppercase tracking-[0.2em] text-royalGold-400">
            <Sparkles size={11} className="fill-royalGold-400 text-royalGold-400" />
            الأبطال
          </span>
          <h1 className="mt-4 font-display text-4xl font-black leading-tight text-white sm:text-5xl">
            الأبطال
          </h1>
          <p className="mx-auto mt-4 max-w-3xl text-base leading-8 text-slate-400">
            هنا تُعرض الكلانات المتوَّجة فعليًا في البطولات والدوريات.
          </p>

          <div className="mt-8 grid gap-4 sm:grid-cols-3">
            {stats.map((stat) => (
              <div key={stat.label} className="rounded-2xl border border-white/8 bg-white/[0.03] p-4 text-right">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <p className="text-xs uppercase tracking-[0.2em] text-white/35">{stat.label}</p>
                    <p className="mt-2 text-2xl font-black text-white">{stat.value}</p>
                  </div>
                  <div className={`flex h-11 w-11 items-center justify-center rounded-2xl border ${
                    stat.tone === "gold"
                      ? "border-royalGold-500/30 bg-royalGold-500/10 text-royalGold-400 shadow-[0_0_10px_rgba(203,213,225,0.2)]"
                      : stat.tone === "champion"
                        ? "border-slate-200/60 bg-slate-200/10 text-slate-200 drop-shadow-[0_0_10px_rgba(226,232,240,0.5)]"
                      : stat.tone === "silver"
                        ? "border-gray-300/30 bg-gray-300/10 text-gray-300 shadow-[0_0_8px_rgba(229,231,235,0.24)]"
                        : "border-slate-500/40 bg-slate-500/10 text-slate-400 shadow-[0_0_8px_rgba(148,163,184,0.24)]"
                  }`}>
                    <stat.icon size={18} />
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      <div className="mx-auto max-w-7xl px-4 py-12 sm:px-6 lg:px-8">
        <div className="mb-8 rounded-2xl border border-royalGold-500/20 bg-gradient-to-b from-royalGold-500/8 to-white/[0.02] p-4 sm:p-5">
          <label htmlFor="champions-search" className="mb-2 block text-xs uppercase tracking-[0.22em] text-white/45">
            بحث في الأبطال
          </label>
          <div className="relative">
            <Search size={16} className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-royalGold-300" />
            <input
              id="champions-search"
              data-testid="champions-search-input"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="ابحث باسم الكلان أو البطولة..."
              className="w-full rounded-xl border border-royalGold-500/25 bg-background/70 py-3 pr-10 pl-4 text-sm text-white placeholder:text-white/35 outline-none transition focus:border-royalGold-400/45 focus:ring-2 focus:ring-royalGold-400/20"
            />
          </div>
          <div className="mt-2 text-[11px] text-white/45">
            النتائج: {tournamentWinners.length + leagueWinners.length}
          </div>
        </div>

        {error && (
          <div className="mb-6 rounded-2xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300">
            {error}
          </div>
        )}

        {loading ? (
          <div className="grid min-h-[240px] place-items-center rounded-3xl border border-white/8 bg-white/[0.02] text-white/45">
            <div className="flex items-center gap-3">
              <Loader2 className="h-5 w-5 animate-spin text-royalGold-400" />
              جاري تحميل الأبطال...
            </div>
          </div>
        ) : (
          <div className="space-y-12">
            <section>
              <div className="mb-5 flex items-end justify-between gap-4">
                <div>
                  <div className="inline-flex items-center gap-2 rounded-full border border-royalGold-500/30 bg-royalGold-500/10 px-3 py-1 text-[10px] font-bold uppercase tracking-[0.22em] text-royalGold-400">
                    <Trophy size={11} /> قسم البطولات
                  </div>
                  <h2 className="mt-3 text-2xl font-black text-white">أبطال البطولات</h2>
                  <p className="mt-1 text-sm text-slate-400">كل بطاقة هنا تُظهر الكلان مع البطولة التي فاز بها.</p>
                </div>
                <p className="hidden text-xs uppercase tracking-[0.25em] text-white/35 md:block">
                  {tournamentWinners.length} بطل
                </p>
              </div>

              {tournamentWinners.length > 0 ? (
                <div className="grid gap-6 lg:grid-cols-2">
                  {tournamentWinners.map((item) => (
                    <WinnerCard key={item.id} item={item} variant="tournament" />
                  ))}
                </div>
              ) : (
                <EmptySection
                  title={debouncedSearchTerm ? "لا توجد نتائج مطابقة" : "لا توجد بطولات مكتملة بعد"}
                  description={debouncedSearchTerm ? "جرّب كلمة بحث مختلفة باسم كلان أو بطولة." : "عندما يتم تتويج بطولة فعلية، ستظهر هنا الكلانات الفائزة مع بطاقة أنيقة واضحة."}
                />
              )}
            </section>

            <section>
              <div className="mb-5 flex items-end justify-between gap-4">
                <div>
                  <div className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/[0.03] px-3 py-1 text-[10px] font-bold uppercase tracking-[0.22em] text-white/45">
                    <Award size={11} /> قسم الدوريات
                  </div>
                  <h2 className="mt-3 text-2xl font-black text-white">أبطال الدوريات</h2>
                  <p className="mt-1 text-sm text-slate-400">بطاقات الدوريات تبقى أنيقة وهادئة بدون الإطار الذهبي.</p>
                </div>
                <p className="hidden text-xs uppercase tracking-[0.25em] text-white/35 md:block">
                  {leagueWinners.length} بطل
                </p>
              </div>

              {leagueWinners.length > 0 ? (
                <div className="grid gap-6 lg:grid-cols-2">
                  {leagueWinners.map((item) => (
                    <WinnerCard key={item.id} item={item} variant="league" />
                  ))}
                </div>
              ) : (
                <EmptySection
                  title={debouncedSearchTerm ? "لا توجد نتائج مطابقة" : "لا توجد أبطال دوريات بعد"}
                  description={debouncedSearchTerm ? "جرّب كلمة بحث مختلفة باسم كلان أو بطولة." : "ستظهر هنا الكلانات التي أنهت الموسم وتوِّجت بلقب الدوري مع عرض بصري هادئ ونظيف."}
                />
              )}
            </section>
          </div>
        )}
      </div>
    </div>
  );
}
