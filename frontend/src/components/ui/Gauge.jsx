export default function Gauge({ value, label = 'AI-generation score', verdict }) {
  if (typeof value !== 'number' || !Number.isFinite(value) || value < 0 || value > 1) {
    return <p className="text-sm text-fortexa-muted">Model scores unavailable</p>
  }
  const ai = Math.round(value * 100)
  const real = 100 - ai
  const uncertain = verdict === 'inconclusive'
  const signal = uncertain ? 'Needs review' : value >= 0.6 ? 'High AI signal' : value <= 0.4 ? 'Low AI signal' : 'Mixed AI signal'
  return (
    <div className="w-full max-w-md text-left" aria-label={`${label}: ${ai} out of 100. Real-image score: ${real} out of 100. ${signal}.`}>
      <p className="mb-4 text-center text-xs font-medium uppercase tracking-wider text-fortexa-muted">Classification scores</p>
      <div className="grid grid-cols-2 gap-3 sm:gap-4">
        <div className="rounded-xl border border-emerald-500/25 bg-emerald-500/5 p-3 sm:p-4">
          <p className="text-xs font-semibold text-emerald-300 sm:text-sm">Real-image score</p>
          <p className="mt-2 whitespace-nowrap text-xl font-bold text-emerald-400 sm:text-3xl">{real} / 100</p>
          <div className="mt-3 h-2 overflow-hidden rounded-full bg-white/10" role="meter" aria-label="Real-image score" aria-valuemin={0} aria-valuemax={100} aria-valuenow={real}>
            <div className="h-full rounded-full bg-emerald-500" style={{ width: `${real}%` }} />
          </div>
        </div>
        <div className="rounded-xl border border-red-500/25 bg-red-500/5 p-3 sm:p-4">
          <p className="text-xs font-semibold text-red-300 sm:text-sm">AI-generation score</p>
          <p className="mt-2 whitespace-nowrap text-xl font-bold text-red-400 sm:text-3xl">{ai} / 100</p>
          <div className="mt-3 h-2 overflow-hidden rounded-full bg-white/10" role="meter" aria-label="AI-generation score" aria-valuemin={0} aria-valuemax={100} aria-valuenow={ai}>
            <div className="h-full rounded-full bg-red-500" style={{ width: `${ai}%` }} />
          </div>
        </div>
      </div>
      <p className="mt-3 text-center text-sm text-fortexa-muted">
        {uncertain || (value > .4 && value < .6)
          ? 'A clear classification could not be established.'
          : value <= .4 ? 'Assessment: likely real photograph.' : 'Assessment: likely AI-generated image.'}
      </p>
      <p className="mt-2 text-center text-xs leading-relaxed text-fortexa-muted">Higher scores indicate stronger model support—not proof of authenticity.</p>
    </div>
  )
}
