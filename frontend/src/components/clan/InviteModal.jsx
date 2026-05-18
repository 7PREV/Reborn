export default function InviteModal({ search, results, onSearch, onInvite, onClose }) {
  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-black/70 backdrop-blur-xl p-4">
      <div className="bg-surface border b-soft rounded-xl p-6 w-full max-w-md space-y-4">
        <h2 className="font-display font-black text-2xl">دعوة لاعب</h2>
        <input
          value={search}
          onChange={(e) => onSearch(e.target.value)}
          placeholder="ابحث باسم المستخدم..."
          data-testid="invite-search"
          className="w-full bg-background border b-soft rounded-md px-4 py-3 outline-none"
        />
        <div className="max-h-64 overflow-y-auto space-y-2">
          {results.map((u) => (
            <div key={u.id} className="flex items-center gap-3 p-2 rounded hover:bg-white/5">
              <div className="h-8 w-8 rounded bg-white/5 grid place-items-center text-gold-500">
                {u.username[0].toUpperCase()}
              </div>
              <div className="flex-1">{u.username}</div>
              <button data-testid={`invite-user-${u.id}`} onClick={() => onInvite(u.id)} className="px-3 py-1 rounded bg-gold-500 text-black text-sm font-bold">
                دعوة
              </button>
            </div>
          ))}
          {search && results.length === 0 && (
            <div className="text-center text-white/40 py-4 text-sm">لا توجد نتائج</div>
          )}
        </div>
        <div className="text-right">
          <button onClick={onClose} className="px-4 py-2 rounded-md hover:bg-white/5">إغلاق</button>
        </div>
      </div>
    </div>
  );
}
