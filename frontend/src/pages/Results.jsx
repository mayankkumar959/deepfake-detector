import { useState, useEffect } from 'react'
import { useParams, Link } from 'react-router-dom'
import {
  ArrowLeft, Clock, Camera, Video, AlertTriangle,
  FileText, Flame, Zap,
} from 'lucide-react'
import api, { mediaUrl as scanMediaUrl, downloadReport, handleError } from '../api/client'
import Gauge from '../components/ui/Gauge'
import VerdictBadge from '../components/ui/VerdictBadge'
import Spinner from '../components/ui/Spinner'
import VideoTimeline from '../components/ui/VideoTimeline'
import ScanNotes from '../components/ui/ScanNotes'

const signalColors = {
  suspicious: 'text-red-400',
  neutral: 'text-amber-400',
  normal: 'text-emerald-400',
}

export default function Results() {
  const { id } = useParams()
  const [scan, setScan] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [retry, setRetry] = useState(0)
  useEffect(() => {
    const controller = new AbortController()
    let timer
    const deadline = Date.now() + 10 * 60 * 1000
    setScan(null)
    setError('')
    setLoading(true)
    async function fetchScan() {
      try {
        const { data } = await api.get(`/scans/${id}`, { signal: controller.signal })
        if (controller.signal.aborted) return
        setScan(data)
        setLoading(false)
        if (['pending', 'processing'].includes(data.status)) {
          if (Date.now() > deadline) setError('Processing is taking longer than expected. Retry to check again.')
          else timer = setTimeout(fetchScan, 2000)
        }
      } catch (err) {
        if (controller.signal.aborted) return
        setError(err.response?.status === 404 ? 'This scan was deleted, expired, or belongs to another browser session.' : handleError(err))
        setLoading(false)
      }
    }
    fetchScan()
    return () => { controller.abort(); clearTimeout(timer) }
  }, [id, retry])
  if (error) {
    return (
      <main className="mx-auto flex min-h-[60vh] max-w-lg flex-col items-center justify-center gap-4 px-6 text-center">
        <AlertTriangle size={36} className="text-amber-300" />
        <h1 className="text-2xl font-bold">Report unavailable</h1>
        <p role="alert" className="text-fortexa-muted">{error}</p>
        <div className="flex flex-wrap justify-center gap-3">
          <button className="btn-secondary" onClick={() => setRetry(value => value + 1)}>Retry</button>
          <Link to="/history" className="btn-primary">Your Scans</Link>
        </div>
      </main>
    )
  }
  if (loading) {
    return (
      <div className="flex items-center justify-center py-24">
        <Spinner size={28} />
      </div>
    )
  }

  if (!scan) {
    return (
      <div className="flex flex-col items-center py-24">
        <AlertTriangle size={36} className="text-fortexa-muted mb-4" />
        <p className="text-lg font-semibold">Scan not found</p>
        <Link to="/" className="btn-primary mt-4">Scan New Media</Link>
      </div>
    )
  }

  if (scan.status === 'pending' || scan.status === 'processing') {
    return (
      <div className="flex flex-col items-center py-24">
        <Spinner size={32} />
        <p className="mt-4 text-lg font-semibold">Scan in progress…</p>
      </div>
    )
  }

  if (scan.status === 'failed') {
    return (
      <div className="flex flex-col items-center py-24">
        <AlertTriangle size={36} className="text-red-400 mb-4" />
        <p className="text-lg font-semibold">Scan Failed</p>
        <p className="mt-1 max-w-md text-center text-sm text-fortexa-muted">{scan.error || 'An unknown error occurred.'}</p>
        <Link to="/" className="btn-primary mt-4">Try Again</Link>
      </div>
    )
  }

  const report = scan.report
  const signals = report?.signals || []
  const isVideo = scan.media_type === 'video'
  const mediaUrl = () => scanMediaUrl(scan)

  return (
    <div className="mx-auto max-w-7xl animate-fade-in px-4 py-10 lg:px-8">
      {/* Back */}
      <Link to="/" className="mb-4 inline-flex items-center gap-1.5 text-sm text-fortexa-muted hover:text-white">
        <ArrowLeft size={16} /> Scan New Media
      </Link>

      {/* Header */}
      <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <div className="flex items-center gap-3 mb-2">
            <h1 className="text-2xl font-bold tracking-tight">Scan Report</h1>
            {scan.verdict && <VerdictBadge verdict={scan.verdict} />}
          </div>
          <div className="flex flex-wrap items-center gap-4 text-sm text-fortexa-muted">
            <span className="flex items-center gap-1.5">
              {isVideo ? <Video size={14} /> : <Camera size={14} />}
              {scan.filename}
            </span>
            <span className="flex items-center gap-1.5">
              <FileText size={14} /> {(scan.file_size / 1024).toFixed(0)} KB
            </span>
            <span className="flex items-center gap-1.5">
              <Clock size={14} /> {scan.duration_ms ? `${scan.duration_ms}ms` : '—'}
            </span>
          </div>
        </div>
        <button className="btn-secondary" onClick={() => downloadReport(scan)}>Download Report</button>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        {/* Left: Gauge + media + heatmap */}
        <div className="space-y-6">
          <div className="card flex flex-col items-center">
            {report?.ml_probability != null ? <Gauge value={scan.fake_probability || 0} size={180} /> : <p className="text-sm text-fortexa-muted">No reliable score available</p>}
            <div className="mt-4 text-center">
              <p className="text-xs text-fortexa-muted">AI model score · not confidence</p>
            </div>
          </div>

          <div className="card !p-0 overflow-hidden">
            {isVideo ? (
              <video src={mediaUrl()} controls className="w-full h-48 object-cover bg-black" />
            ) : (
              <img src={mediaUrl()} alt="Scan" className="w-full h-48 object-cover bg-black" />
            )}
            <div className="p-4 text-xs text-fortexa-muted">
              {isVideo ? 'Original video' : 'Original image'}
            </div>
          </div>

          <details className="card">
            <summary className="cursor-pointer text-sm font-semibold">
              <Flame size={16} className="text-fortexa-primary" /> {isVideo ? 'Sampled Frame' : 'Score Annotation'}
            </summary>
            <img
              src={scanMediaUrl(scan, isVideo ? 'thumbnail.jpg' : 'heatmap.jpg')}
              alt={isVideo ? 'Sampled frame' : 'Score annotation'}
              className="mt-3 w-full rounded-xl border border-white/10"
              onError={(e) => { e.target.style.display = 'none' }}
            />
            <p className="mt-2 text-xs text-fortexa-muted">{isVideo ? 'A sampled frame from the video.' : 'Score overlay only; not a manipulation map.'}</p>
          </details>
        </div>
        {/* Right: Signals + details */}
        <div className="space-y-6 lg:col-span-2">
          <ScanNotes warnings={report?.warnings} isVideo={isVideo} />

          {/* Signal bars */}
          {signals.length > 0 && (
            <details className="card">
              <summary className="cursor-pointer text-sm font-semibold">
                Diagnostic signals
              </summary>
              <p className="mt-3 text-xs text-fortexa-muted">Supporting diagnostics, not proof of AI generation.</p>
              <div className="mt-4 space-y-4">
                {signals.map((s) => (
                  <div key={s.key}>
                    <div className="mb-1 flex items-center justify-between text-sm">
                      <span className="font-medium">{s.label}</span>
                      <span className={`text-xs font-medium ${signalColors[s.status] || 'text-fortexa-muted'}`}>
                        {Math.round(s.score * 100)}% · {s.status}
                      </span>
                    </div>
                    <div className="h-2 rounded-full bg-white/5 overflow-hidden">
                      <div
                        className="h-full rounded-full transition-all duration-700"
                        style={{
                          width: `${Math.round(s.score * 100)}%`,
                          background: s.score >= 0.6
                            ? 'linear-gradient(90deg, #f59e0b, #ef4444)'
                            : s.score <= 0.4
                              ? 'linear-gradient(90deg, #22c55e, #10b981)'
                              : 'linear-gradient(90deg, #f59e0b, #d97706)',
                        }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            </details>
          )}

          {/* Video timeline */}
          {report?.timeline && report.timeline.length > 0 && (
            <div className="card">
              <h3 className="mb-4 text-sm font-semibold flex items-center gap-2">
                <Zap size={16} className="text-fortexa-primary" /> Frame Timeline
              </h3>
              <VideoTimeline entries={report.timeline} />
              <p className="mt-2 text-xs text-fortexa-muted">
                Each bar is a sampled frame. Red/green show the model preference; grey means no classification was possible.
              </p>
            </div>
          )}

          <details className="card">
            <summary className="cursor-pointer text-sm font-semibold">Technical details</summary>
            <dl className="mt-3 space-y-2 text-sm">
              {[
                ['Model', scan.model_used],
                ['Method', scan.method],
                ['Analysis time', scan.duration_ms ? `${(scan.duration_ms / 1000).toFixed(1)}s` : '—'],
                ...(isVideo ? [
                  ['Frames sampled', report?.analyzed_frames ?? '—'],
                  ['Video length', report?.duration_seconds != null ? `${report.duration_seconds}s` : '—'],
                ] : []),
              ].map(([label, value]) => (
                <div key={label} className="flex flex-wrap justify-between gap-2 border-b border-white/5 py-1.5">
                  <dt className="text-fortexa-muted">{label}</dt>
                  <dd className="break-all font-medium">{value || '—'}</dd>
                </div>
              ))}
            </dl>
          </details>
        </div>
      </div>
    </div>
  )
}
