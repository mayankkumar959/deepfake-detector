import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { Camera, Video, Trash2, ChevronLeft, ChevronRight, Search, History as HistoryIcon } from 'lucide-react'
import api from '../api/client'
import PageHeader from '../components/ui/PageHeader'
import VerdictBadge from '../components/ui/VerdictBadge'
import Spinner from '../components/ui/Spinner'
import EmptyState from '../components/ui/EmptyState'
import Modal from '../components/ui/Modal'
import { useToast } from '../components/ui/Toast'

const statusStyles = {
  completed: 'bg-emerald-500/15 text-emerald-400',
  pending: 'bg-sky-500/15 text-sky-400',
  processing: 'bg-amber-500/15 text-amber-400',
  failed: 'bg-red-500/15 text-red-400',
}

function formatDate(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleString(undefined, {
    month: 'short', day: 'numeric', year: 'numeric', hour: '2-digit', minute: '2-digit',
  })
}

export default function History() {
  const navigate = useNavigate()
  const toast = useToast()
  const [data, setData] = useState({ total: 0, page: 1, page_size: 20, items: [] })
  const [page, setPage] = useState(1)
  const [mediaType, setMediaType] = useState('')
  const [verdict, setVerdict] = useState('')
  const [loading, setLoading] = useState(true)
  const [deleteTarget, setDeleteTarget] = useState(null)
  const [deleting, setDeleting] = useState(false)

  const fetchScans = useCallback(async () => {
    setLoading(true)
    try {
      const params = new URLSearchParams({ page, page_size: 20 })
      if (mediaType) params.set('media_type', mediaType)
      if (verdict) params.set('verdict', verdict)
      const { data } = await api.get(`/scans?${params.toString()}`)
      setData(data)
    } catch {
      toast.error('Failed to load scans.')
    } finally {
      setLoading(false)
    }
  }, [page, mediaType, verdict])

  useEffect(() => {
    fetchScans()
  }, [fetchScans])

  const handleDelete = async () => {
    if (!deleteTarget) return
    setDeleting(true)
    try {
      await api.delete(`/scans/${deleteTarget.id}`)
      toast.success('Scan deleted.')
      setDeleteTarget(null)
      fetchScans()
    } catch {
      toast.error('Failed to delete scan.')
    } finally {
      setDeleting(false)
    }
  }

  const totalPages = Math.max(1, Math.ceil(data.total / data.page_size))

  return (
    <div>
      <PageHeader title="Scan History" description="All your past deepfake analyses." />

      {/* Filters */}
      <div className="mb-6 flex flex-wrap items-center gap-3">
        <div className="relative">
          <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-fortexa-muted" />
          <input
            className="input-base !w-52 !pl-9"
            placeholder="Search filename…"
            value=""
            onChange={() => {}}
            readOnly
          />
        </div>
        <select className="input-base !w-36" value={mediaType} onChange={(e) => { setMediaType(e.target.value); setPage(1) }}>
          <option value="">All types</option>
          <option value="image">Images</option>
          <option value="video">Videos</option>
        </select>
        <select className="input-base !w-40" value={verdict} onChange={(e) => { setVerdict(e.target.value); setPage(1) }}>
          <option value="">All verdicts</option>
          <option value="fake">Fake</option>
          <option value="real">Real</option>
          <option value="inconclusive">Inconclusive</option>
        </select>
        <span className="ml-auto text-sm text-fortexa-muted">{data.total} total scans</span>
      </div>
      {/* Table */}
      <div className="card !p-0 overflow-hidden">
        {loading ? (
          <div className="flex justify-center py-16">
            <Spinner size={26} />
          </div>
        ) : data.items.length === 0 ? (
          <EmptyState
            icon={HistoryIcon}
            title="No scans found"
            description="Upload media to start building your scan history."
            action={
              <button onClick={() => navigate('/app/scan')} className="btn-primary">
                Analyze Media
              </button>
            }
          />
        ) : (
          <div className="overflow-x-auto scrollbar-thin">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-white/10 text-left text-xs uppercase tracking-wider text-fortexa-muted">
                  <th className="px-5 py-3.5 font-medium">File</th>
                  <th className="px-5 py-3.5 font-medium">Type</th>
                  <th className="px-5 py-3.5 font-medium">Verdict</th>
                  <th className="px-5 py-3.5 font-medium">Probability</th>
                  <th className="px-5 py-3.5 font-medium">Status</th>
                  <th className="px-5 py-3.5 font-medium">Date</th>
                  <th className="px-5 py-3.5 font-medium text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((s) => (
                  <tr
                    key={s.id}
                    onClick={() => s.status === 'completed' && navigate(`/app/results/${s.id}`)}
                    className={`border-b border-white/5 transition-colors ${s.status === 'completed' ? 'cursor-pointer hover:bg-white/5' : ''}`}
                  >
                    <td className="px-5 py-3.5">
                      <span className="flex items-center gap-2.5">
                        <span className="rounded-lg bg-white/5 border border-white/10 p-1.5">
                          {s.media_type === 'image'
                            ? <Camera size={14} className="text-sky-400" />
                            : <Video size={14} className="text-purple-400" />}
                        </span>
                        <span className="font-medium max-w-[180px] truncate">{s.filename}</span>
                      </span>
                    </td>
                    <td className="px-5 py-3.5 capitalize text-fortexa-muted">{s.media_type}</td>
                    <td className="px-5 py-3.5">
                      {s.verdict ? <VerdictBadge verdict={s.verdict} size="sm" /> : <span className="text-fortexa-muted">—</span>}
                    </td>
                    <td className="px-5 py-3.5 text-fortexa-muted">
                      {s.fake_probability != null ? `${Math.round(s.fake_probability * 100)}% fake` : '—'}
                    </td>
                    <td className="px-5 py-3.5">
                      <span className={`badge ${statusStyles[s.status] || 'bg-white/10 text-fortexa-muted'}`}>
                        {s.status}
                      </span>
                    </td>
                    <td className="px-5 py-3.5 text-fortexa-muted whitespace-nowrap">{formatDate(s.created_at)}</td>
                    <td className="px-5 py-3.5">
                      <div className="flex justify-end gap-2">
                        {s.status === 'completed' && (
                          <button
                            onClick={(e) => { e.stopPropagation(); navigate(`/app/results/${s.id}`) }}
                            className="text-fortexa-primary hover:text-fortexa-secondary text-xs font-medium"
                          >
                            View
                          </button>
                        )}
                        <button
                          onClick={(e) => { e.stopPropagation(); setDeleteTarget(s) }}
                          className="text-fortexa-muted hover:text-red-400"
                        >
                          <Trash2 size={15} />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {/* Pagination */}
        {data.total > data.page_size && (
          <div className="flex items-center justify-between border-t border-white/10 px-5 py-3.5">
            <span className="text-sm text-fortexa-muted">
              Page {data.page} of {totalPages}
            </span>
            <div className="flex gap-2">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page <= 1}
                className="btn-secondary !px-3 !py-1.5 !text-xs"
              >
                <ChevronLeft size={14} /> Prev
              </button>
              <button
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page >= totalPages}
                className="btn-secondary !px-3 !py-1.5 !text-xs"
              >
                Next <ChevronRight size={14} />
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Delete confirmation */}
      <Modal open={!!deleteTarget} onClose={() => setDeleteTarget(null)} title="Delete scan">
        <p className="text-sm text-fortexa-muted">
          Are you sure you want to delete the scan for <span className="font-medium text-white">{deleteTarget?.filename}</span>?
          This permanently removes the scan record and all associated files.
        </p>
        <div className="mt-6 flex justify-end gap-3">
          <button className="btn-secondary" onClick={() => setDeleteTarget(null)}>Cancel</button>
          <button className="btn-danger" onClick={handleDelete} disabled={deleting}>
            {deleting ? <Spinner size={16} /> : <Trash2 size={16} />}
            {deleting ? 'Deleting…' : 'Delete'}
          </button>
        </div>
      </Modal>
    </div>
  )
}
