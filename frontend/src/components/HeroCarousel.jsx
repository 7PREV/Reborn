import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import api from "../api";

const FALLBACK = [{
  id: "default",
  title: "Rivals",
  subtitle: "تابع المباريات الحية، شارك في التحديات، وكوّن كلانك الخاص.",
  image: "/9502F1FD-9141-4DCB-BEA5-052AEE6D991F.png",
  link: null,
}];

export default function HeroCarousel() {
  const [banners, setBanners] = useState(FALLBACK);
  const [idx, setIdx] = useState(0);

  useEffect(() => {
    api.get("/banners").then((r) => {
      if (r.data?.length > 0) setBanners(r.data);
    }).catch(() => {});
  }, []);

  useEffect(() => {
    if (banners.length <= 1) return;
    const t = setInterval(() => setIdx((i) => (i + 1) % banners.length), 5000);
    return () => clearInterval(t);
  }, [banners.length]);

  const current = banners[idx] || FALLBACK[0];
  const inner = (
    <div className="relative overflow-hidden rounded-xl border b-soft grain h-[300px] md:h-[420px]" data-testid="hero-banner">
      <img
        src={current.image}
        alt={current.title}
        className="absolute inset-0 w-full h-full object-cover opacity-90 transition-opacity duration-700"
        key={current.id}
      />
      <div className="absolute inset-0 bg-gradient-to-l from-[#0a0a0bcc] via-[#0a0a0b55] to-[#0a0a0b00]" />
      <div className="absolute inset-x-0 bottom-0 h-1/2 bg-gradient-to-t from-[#0a0a0b] to-transparent" />
      <div className="relative p-8 md:p-14 h-full flex flex-col justify-end">
        <div className="text-xs uppercase tracking-[0.3em] text-gold-500 mb-3">
          {current.link ? "إعلان" : "بطولات • كلانات • مجد"}
        </div>
        <h1 className="font-display font-black text-3xl md:text-4xl lg:text-5xl leading-[1.05] max-w-3xl">
          {current.title}
        </h1>
        {current.subtitle && (
          <p className="mt-5 text-white/70 max-w-xl text-base md:text-lg">{current.subtitle}</p>
        )}
        {!current.link && (
          <div className="mt-7 flex gap-3 flex-wrap">
            <Link to="/tournaments" className="px-5 py-3 rounded-md bg-gold-500 text-black font-bold hover:bg-gold-400 transition">
              البطولات
            </Link>
            <Link to="/clans" className="px-5 py-3 rounded-md border b-soft hover:bg-white/5 transition">
              استكشف الكلانات
            </Link>
          </div>
        )}
      </div>

      {banners.length > 1 && (
        <div className="absolute bottom-4 left-1/2 -translate-x-1/2 flex gap-1.5 z-10">
          {banners.map((b, i) => (
            <button
              key={b.id}
              onClick={(e) => { e.preventDefault(); setIdx(i); }}
              data-testid={`hero-dot-${i}`}
              className={`h-1.5 rounded-full transition-all ${
                i === idx ? "w-6 bg-gold-500" : "w-1.5 bg-white/30"
              }`}
              aria-label={`Slide ${i + 1}`}
            />
          ))}
        </div>
      )}
    </div>
  );

  if (current.link) {
    return (
      <a href={current.link} target="_blank" rel="noopener noreferrer" className="block">
        {inner}
      </a>
    );  
  }
  return inner;
}
