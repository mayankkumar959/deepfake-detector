export default function VideoTimeline({ entries = [] }) {
  return (
    <div className="flex gap-1.5 overflow-x-auto pb-2 scrollbar-thin">
      {entries.map(entry => {
        const score = entry.fake_probability
        const classified = entry.classified !== false
        const color = !classified ? 'rgba(148,163,184,0.35)' : score >= .6
          ? `rgba(239,68,68,${Math.max(.25, score)})`
          : score <= .4 ? `rgba(34,197,94,${Math.max(.25, 1 - score)})` : 'rgba(245,158,11,0.5)'
        return (
          <div key={entry.index} className="flex shrink-0 flex-col items-center gap-1" title={`${entry.time}s: ${classified ? `${Math.round(score * 100)}% fake model score` : 'No classification'}`}>
            <div className="h-20 w-10 rounded-lg border border-white/10" style={{ background: color }} />
            <span className="text-[10px] text-fortexa-muted">{entry.time}s</span>
          </div>
        )
      })}
    </div>
  )
}
