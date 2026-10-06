import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { ArrowLeft, Trash2, RefreshCw, ScanFace, Image, Film, ChevronLeft, ChevronRight } from 'lucide-react'
import api, { handleError } from '../api/client'
import VerdictBadge from '../components/ui/VerdictBadge'

export default function ScanHistory() {
  const [items, setItems] = useState([])
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [deleting, setDeleting] = useState(null)
  const [page, setPage] = useState(1)
  const [total, setTotal] = useState(0)
  const [reload, setReload] = useState(0)
  const pageSize = 12
  useEffect(() => {
    const controller = new AbortController()
    setLoading(true)
    setError('')
    api.get('/scans', { params: { page, page_size: pageSize }, signal: controller.signal })
      .then(({ data }) => {
        if (controller.signal.aborted) return
        setItems(data.items)
        setTotal(data.total)
        if (page > 1 && !data.items.length) setPage(value => value - 1)
      })
      .catch(err => { if (!controller.signal.aborted) setError(handleError(err)) })
      .finally(() => { if (!controller.signal.aborted) setLoading(false) })
    return () => controller.abort()
  }, [page, reload])
  async function remove(id) {
    if (!window.confirm('Delete this scan, its uploaded file and report permanently?')) return
    setDeleting(id)
    try {
      await api.delete(`/scans/${id}`)
      setItems(previous => previous.filter(item => item.id !== id))
      setReload(value => value + 1)
    } catch (err) { setError(handleError(err)) }
    finally { setDeleting(null) }
  }
  return (
    <main className="mx-auto min-h-screen max-w-5xl px-4 py-10">
      <Link to="/" className="mb-6 inline-flex items-center gap-2 text-fortexa-muted"><ArrowLeft size={16} /> Scanner</Link>
      <div className="mb-6 flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold">Your Scan History</h1>
        </div>
        <button className="btn-secondary" disabled={loading || deleting !== null} onClick={() => setReload(value => value + 1)}><RefreshCw size={16} className={loading ? 'animate-spin' : ''} /> Refresh</button>
      </div>
      <p className="mb-6 text-xs text-fortexa-muted">Private to this browser · Scans expire automatically.</p>
      {error && <p role="alert" className="mb-4 text-red-300">{error}</p>}
      {loading && <p className="text-fortexa-muted">Loading scans…</p>}
      {!loading && !error && !items.length && (
        <div className="card flex flex-col items-center gap-4 py-16 text-center">
          <div className="rounded-2xl bg-fortexa-primary/10 p-5 text-fortexa-primary"><ScanFace size={36} /></div>
          <h2 className="text-xl font-semibold">No scans yet</h2>
          <Link className="btn-primary" to="/">Analyze a file</Link>
        </div>
      )}
      <div className="space-y-3" aria-busy={loading}>
        {items.map(scan => (
          <div key={scan.id} className="card flex flex-wrap items-center justify-between gap-4">
            {scan.media_type === 'video' ? <Film size={22} className="text-fortexa-primary" /> : <Image size={22} className="text-fortexa-primary" />}
            <Link to={`/results/${scan.id}`} className="min-w-0 flex-1 hover:text-fortexa-primary transition-colors">
              <p className="truncate font-semibold">{scan.filename}</p>
              <p className="mt-1 text-xs text-fortexa-muted">{scan.media_type} · {scan.status} · {new Date(scan.created_at).toLocaleString()}</p>
            </Link>
            {scan.verdict && <VerdictBadge verdict={scan.verdict} />}
            <button className="btn-secondary !px-3 hover:!text-red-300" aria-label={`Delete ${scan.filename}`} disabled={deleting !== null || loading || ['pending', 'processing'].includes(scan.status)} onClick={() => remove(scan.id)}><Trash2 size={16} /></button>
          </div>
        ))}
      </div>
      {total > 0 && <div className="mt-6 flex flex-wrap items-center justify-between gap-3 text-sm text-fortexa-muted">
        <span>{total} scans · Page {page} of {Math.max(1, Math.ceil(total / pageSize))}</span>
        <div className="flex gap-2">
          <button className="btn-secondary !px-3" aria-label="Previous page" disabled={loading || deleting !== null || page <= 1} onClick={() => setPage(value => value - 1)}><ChevronLeft size={18} /></button>
          <button className="btn-secondary !px-3" aria-label="Next page" disabled={loading || deleting !== null || page * pageSize >= total} onClick={() => setPage(value => value + 1)}><ChevronRight size={18} /></button>
        </div>
      </div>}
    </main>
  )
}
