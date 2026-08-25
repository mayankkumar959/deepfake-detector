import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  ScanSearch, Camera, Video, AlertTriangle, ShieldCheck, HelpCircle,
  TrendingUp, Activity, Plus, BarChart3, Clock,
} from 'lucide-react'
import api from '../api/client'
import StatCard from '../components/ui/StatCard'
import VerdictBadge from '../components/ui/VerdictBadge'
import Spinner from '../components/ui/Spinner'
import EmptyState from '../components/ui/EmptyState'
import PageHeader from '../components/ui/PageHeader'

export default function Dashboard() {
  const navigate = useNavigate()
  const [stats, setStats] = useState(null)
  const [trends, setTrends] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([
      api.get('/dashboard/summary'),
      api.get('/dashboard/trends?days=7'),
    ])
      .then(([s, t]) => {
        setStats(s.data)
        setTrends(t.data)
      })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24">
        <Spinner size={28} />
      </div>
    )
  }

  const maxTrend = Math.max(...trends.map((d) => d.total), 1)

return (
    <div>
      <PageHeader
        title="Dashboard"
        description="Overview of your forensic analysis activity."
        actions={
          <button onClick={() => navigate('/app/scan')} className="btn-primary">
            <Plus size={16} /> New Scan
          </button>
        }
      />

      {/* Stats */}
      <div className="mb-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard icon={ScanSearch} label="Total Scans" value={stats.total_scans} sub={`${stats.today_scans} today`} color="text-fortexa-primary" delay={0} />
        <StatCard icon={AlertTriangle} label="Fake Detected" value={stats.fake_detected} color="text-red-400" delay={80} />
        <StatCard icon={ShieldCheck} label="Real Detected" value={stats.real_detected} color="text-emerald-400" delay={160} />
        <StatCard icon={HelpCircle} label="Inconclusive" value={stats.inconclusive} color="text-amber-400" delay={240} />
      </div>
      {/* Trends chart */}
      {trends.length > 0 && (
        <div className="card mb-8">
          <h3 className="mb-4 text-lg font-semibold flex items-center gap-2">
            <TrendingUp size={18} className="text-fortexa-primary" />
            7-Day Trend
          </h3>
          <div className="relative h-48">
            <div className="absolute inset-0 flex items-end gap-2">
              {trends.map((d) => {
                const h = Math.max((d.total / maxTrend) * 100, 4)
                const fakeH = maxTrend > 0 ? (d.fake / d.total) * h : 0
                const realH = maxTrend > 0 ? (d.real / d.total) * h : 0
                return (
                  <div key={d.date} className="flex-1 flex flex-col items-center justify-end gap-0.5 h-full">
                    <div className="w-full flex flex-col-reverse" style={{ height: `${h}%` }}>
                      {fakeH > 0 && (
                        <div className="w-full rounded-t bg-red-500/70" style={{ height: `${fakeH}%` }} title={`${d.fake} fake`} />
                      )}
                      {realH > 0 && (
                        <div className="w-full bg-emerald-500/70" style={{ height: `${realH}%` }} title={`${d.real} real`} />
                      )}
                    </div>
                    <span className="text-[10px] text-fortexa-muted mt-1">{d.date.slice(5)}</span>
                  </div>
                )
              })}
            </div>
          </div>
          <div className="mt-4 flex items-center gap-4 text-xs text-fortexa-muted">
            <span className="flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded bg-red-500/70" /> Fake</span>
            <span className="flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded bg-emerald-500/70" /> Real</span>
          </div>
        </div>
      )}

      {/* Recent scans */}
      <div>
        <h3 className="mb-4 text-lg font-semibold">Recent Scans</h3>
        {stats.recent_scans?.length > 0 ? (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {stats.recent_scans.map((s) => (
              <button
                key={s.id}
                onClick={() => navigate(`/app/results/${s.id}`)}
                className="glass glass-hover card !p-4 text-left transition-all"
              >
                <div className="mb-3 flex items-center justify-between">
                  <span className="badge bg-white/10 text-fortexa-muted text-[10px]">
                    {s.media_type === 'image' ? <Camera size={12} /> : <Video size={12} />}
                    {s.media_type}
                  </span>
                  {s.verdict && <VerdictBadge verdict={s.verdict} size="sm" />}
                </div>
                <p className="truncate text-sm font-medium">{s.filename}</p>
                <div className="mt-2 flex items-center gap-3 text-[11px] text-fortexa-muted">
                  {s.status === 'completed' ? (
                    <>
                      <span className="flex items-center gap-1"><Activity size={11} /> {Math.round(s.fake_probability * 100)}%</span>
                      <span className="flex items-center gap-1"><Clock size={11} /> {s.duration_ms ? `${s.duration_ms}ms` : '—'}</span>
                    </>
                  ) : (
                    <span className="badge bg-amber-500/20 text-amber-300">{s.status}</span>
                  )}
                </div>
              </button>
            ))}
          </div>
        ) : (
          <EmptyState
            icon={ScanSearch}
            title="No scans yet"
            description="Upload your first photo or video to start detecting deepfakes."
            action={
              <button onClick={() => navigate('/app/scan')} className="btn-primary">
                <Plus size={16} /> Analyze Media
              </button>
            }
          />
        )}
      </div>
    </div>
  )
}