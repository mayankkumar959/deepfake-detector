import { useState, useEffect, useRef } from 'react'
import { useParams, Link } from 'react-router-dom'
import {
  ArrowLeft, Clock, Activity, Camera, Video, AlertTriangle,
  FileText, Flame, BarChart3, Zap,
} from 'lucide-react'
import api from '../api/client'
import Gauge from '../components/ui/Gauge'
import VerdictBadge from '../components/ui/VerdictBadge'
import Spinner from '../components/ui/Spinner'
import { useToast } from '../components/ui/Toast'

const signalColors = {
  suspicious: 'text-red-400',
  neutral: 'text-amber-400',
  normal: 'text-emerald-400',
}

export default function Results() {
  const { id } = useParams()
  const toast = useToast()
  const [scan, setScan] = useState(null)
  const [loading, setLoading] = useState(true)
  const [polling, setPolling] = useState(false)
  const pollRef = useRef(null)

  const fetchScan = async () => {
    try {
      const { data } = await api.get(`/scans/${id}`)
      setScan(data)
      if (data.status === 'pending' || data.status === 'processing') {
        setPolling(true)
        if (!pollRef.current) {
          pollRef.current = setInterval(fetchScan, 2000)
        }
      } else {
        setPolling(false)
        if (pollRef.current) {
          clearInterval(pollRef.current)
          pollRef.current = null
        }
      }
    } catch (err) {
      toast.error('Failed to load scan.')
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchScan()
    return () => {
      if (pollRef.current) clearInterval(pollRef.current)
    }
  }, [id])

  useEffect(() => {
    if (scan) setLoading(false)
  }, [scan])
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
        <p className="mt-1 text-sm text-fortexa-muted">Running forensic analysis. This may take a few seconds.</p>
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
  const mediaUrl = () => `/api/scans/${scan.id}/media/${scan.filename}`

  return (
    <div className="animate-fade-in">
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
            <span className="flex items-center gap-1.5">
              <Activity size={14} /> {scan.method}
            </span>
          </div>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        {/* Left: Gauge + media + heatmap */}
        <div className="space-y-6">
          <div className="card flex flex-col items-center">
            <Gauge value={scan.fake_probability || 0} size={180} />
            <div className="mt-4 text-center">
              <p className="text-sm font-medium">{report?.risk_label || '—'} Risk</p>
              <p className="text-xs text-fortexa-muted">Confidence: {Math.round((scan.confidence || 0) * 100)}%</p>
            </div>
          </div>

          <div className="card !p-0 overflow-hidden">
            {isVideo ? (
              <video src={mediaUrl()} controls className="w-full h-48 object-cover bg-black" />
            ) : (
              <img src={mediaUrl()} alt="Scan" className="w-full h-48 object-cover bg-black" />
            )}
            <div className="p-4 text-xs text-fortexa-muted">
              {isVideo ? 'Original video' : 'Original image'} ({scan.filename})
            </div>
          </div>

          <div className="card">
            <h3 className="mb-3 text-sm font-semibold flex items-center gap-2">
              <Flame size={16} className="text-fortexa-primary" /> Heatmap
            </h3>
            <img
              src={`/api/scans/${scan.id}/media/heatmap.jpg`}
              alt="Heatmap"
              className="w-full rounded-xl border border-white/10"
              onError={(e) => { e.target.style.display = 'none' }}
            />
            <p className="mt-2 text-xs text-fortexa-muted">Face detection overlay with probability annotation.</p>
          </div>
        </div>
        {/* Right: Signals + details */}
        <div className="space-y-6 lg:col-span-2">
          {/* Summary */}
          {report?.summary && (
            <div className="card">
              <h3 className="mb-3 text-sm font-semibold">Analysis Summary</h3>
              <p className="text-sm leading-relaxed text-fortexa-muted">{report.summary}</p>
            </div>
          )}

          {/* Signal bars */}
          {signals.length > 0 && (
            <div className="card">
              <h3 className="mb-4 text-sm font-semibold flex items-center gap-2">
                <BarChart3 size={16} className="text-fortexa-primary" /> Per-Signal Breakdown
              </h3>
              <div className="space-y-4">
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
                    <p className="mt-1 text-xs text-fortexa-muted/70">{s.description}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Video timeline */}
          {report?.timeline && report.timeline.length > 0 && (
            <div className="card">
              <h3 className="mb-4 text-sm font-semibold flex items-center gap-2">
                <Zap size={16} className="text-fortexa-primary" /> Frame Timeline
              </h3>
              <div className="flex gap-1.5 overflow-x-auto pb-2 scrollbar-thin">
                {report.timeline.map((t, i) => (
                  <div
                    key={i}
                    className="flex shrink-0 flex-col items-center gap-1"
                    title={`Frame ${t.frame}: ${Math.round(t.score * 100)}%`}
                  >
                    <div
                      className="w-10 h-20 rounded-lg border border-white/10"
                      style={{
                        background: t.score >= 0.6
                          ? `rgba(239, 68, 68, ${t.score})`
                          : t.score <= 0.4
                            ? `rgba(34, 197, 94, ${1 - t.score})`
                            : `rgba(245, 158, 11, ${t.score})`,
                      }}
                    />
                    <span className="text-[10px] text-fortexa-muted">{t.frame}</span>
                  </div>
                ))}
              </div>
              <p className="mt-2 text-xs text-fortexa-muted">
                Each bar represents a sampled frame. Red indicates higher fake probability, green indicates authentic.
              </p>
            </div>
          )}

          {/* Details */}
          <div className="card">
            <h3 className="mb-3 text-sm font-semibold">Detection Details</h3>
            <div className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm">
              {[
                ['Verdict', scan.verdict],
                ['Fake Probability', `${Math.round((scan.fake_probability || 0) * 100)}%`],
                ['Real Probability', `${Math.round((scan.real_probability || 0) * 100)}%`],
                ['Confidence', `${Math.round((scan.confidence || 0) * 100)}%`],
                ['Risk Level', report?.risk_label || '—'],
                ['Method', scan.method],
                ['Model', scan.model_used],
                ['Duration', scan.duration_ms ? `${scan.duration_ms}ms` : '—'],
                ['Face Count', report?.face_count ?? '—'],
                ['Frame Count', report?.frame_count ?? '—'],
                ['Analyzed Frames', report?.analyzed_frames ?? '—'],
                ['Duration (sec)', report?.duration_seconds ?? '—'],
              ].map(([label, value]) => (
                <div key={label} className="flex justify-between border-b border-white/5 py-1.5">
                  <span className="text-fortexa-muted">{label}</span>
                  <span className="font-medium">{value}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}