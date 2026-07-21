import { useEffect, useMemo, useState } from "react";
import { Shield } from "lucide-react";

function resolveClanLogoUrl(raw) {
  const v = String(raw || "").trim();
  if (!v) return "";
  if (/^https?:\/\//i.test(v) || v.startsWith("data:") || v.startsWith("blob:")) return v;
  const backend = (process.env.REACT_APP_BACKEND_URL || "http://127.0.0.1:8000").replace(/\/$/, "");
  if (v.startsWith("/")) return `${backend}${v}`;
  return `${backend}/${v}`;
}

export default function ClanLogo({
  clan,
  className = "",
  fallbackIconSize = 20,
  fallbackIconClassName = "text-gold-500",
}) {
  const raw = clan?.logo_url || clan?.avatar || clan?.logo || "";
  const src = useMemo(() => resolveClanLogoUrl(raw), [raw]);
  const [broken, setBroken] = useState(false);

  useEffect(() => {
    setBroken(false);
  }, [src]);

  const showImage = !!src && !broken;

  return (
    <div className={className}>
      {showImage ? (
        <img
          src={src}
          alt=""
          className="h-full w-full object-cover"
          onError={() => setBroken(true)}
          draggable={false}
        />
      ) : (
        <Shield size={fallbackIconSize} className={fallbackIconClassName} />
      )}
    </div>
  );
}
