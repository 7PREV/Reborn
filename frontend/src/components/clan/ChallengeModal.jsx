export default function ChallengeModal({ clan, allClans, opponent, onOpponentChange, onClose, onSubmit }) {
  const readyClans = allClans.filter((c) => c.id !== clan.id);
  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-black/70 backdrop-blur-xl p-4">
      <form onSubmit={onSubmit} className="bg-surface border b-soft rounded-xl p-6 w-full max-w-md space-y-4" data-testid="challenge-form">
        <h2 className="font-display font-black text-2xl">تحدي كلان (Call of Duty • BO3)</h2>
        <div className="text-[11px] text-emerald-400 flex items-center gap-1.5">
          <span className="inline-block w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
          الكلانات الجاهزة الآن (تحضير أخضر) ({readyClans.length})
        </div>
        <select
          value={opponent}
          onChange={(e) => onOpponentChange(e.target.value)}
          required
          data-testid="opponent-select"
          className="w-full bg-background border b-soft rounded-md px-4 py-3 outline-none"
        >
          <option value="">— اختر الكلان الخصم —</option>
          {readyClans.map((c) => (
            <option key={c.id} value={c.id}>{c.name} [{c.tag}] • {c.attendance?.count || 0}/6</option>
          ))}
        </select>
        <p className="text-xs text-white/50">سيتم إرسال طلب تحدٍ. تبدأ المباراة فقط بعد قبول قائد الكلان الخصم.</p>
        <div className="flex gap-2 justify-end">
          <button type="button" onClick={onClose} className="px-4 py-2 rounded-md hover:bg-white/5">إلغاء</button>
          <button data-testid="submit-challenge" type="submit" className="px-5 py-2 rounded-md bg-destructive text-white font-bold hover:bg-destructive/90">إرسال طلب التحدي</button>
        </div>
      </form>
    </div>
  );
}
