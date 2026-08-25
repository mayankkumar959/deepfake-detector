export default function StatCard({ icon: Icon, label, value, sub, color = 'text-fortexa-primary', delay = 0 }) {
  return (
    <div className="glass glass-hover card !p-5 animate-slide-up" style={{ animationDelay: `${delay}ms` }}>
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm text-fortexa-muted">{label}</p>
          <p className="mt-2 text-3xl font-bold tracking-tight">{value}</p>
          {sub && <p className="mt-1 text-xs text-fortexa-muted">{sub}</p>}
        </div>
        <div className={`rounded-xl bg-white/5 p-3 border border-white/10 ${color}`}>
          <Icon size={22} />
        </div>
      </div>
    </div>
  )
}