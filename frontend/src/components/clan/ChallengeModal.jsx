export default function ChallengeModal({ clan, allClans, opponent, onOpponentChange, onClose, onSubmit }) {
  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-black/70 backdrop-blur-xl p-4">
      <form onSubmit={onSubmit} className="bg-surface border b-soft rounded-xl p-6 w-full max-w-md space-y-4" data-testid="challenge-form">
        <h2 className="font-display font-black text-2xl">تحدي كلان (Call of Duty • BO3)</h2>
        <select
          value={opponent}
          onChange={(e) => onOpponentChange(e.target.value)}
          required
          data-testid="opponent-select"
          className="w-full bg-background border b-soft rounded-md px-4 py-3 outline-none"
        >
          <option value="">— اختر الكلان الخصم —</option>
          {allClans.filter((c) => c.id !== clan.id).map((c) => (
            <option key={c.id} value={c.id}>{c.name} [{c.tag}]</option>
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
