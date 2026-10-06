import { useState, useCallback, useEffect, useRef } from 'react'
import { Link } from 'react-router-dom'
import { useDropzone } from 'react-dropzone'
import { Upload, Image as ImageIcon, Film, X, AlertCircle, Loader2, ShieldCheck, History } from 'lucide-react'
import api, { mediaUrl as scanMediaUrl, downloadReport } from '../api/client'
import Logo from '../components/layout/Logo'
import Gauge from '../components/ui/Gauge'
import VerdictBadge from '../components/ui/VerdictBadge'
import ScanNotes from '../components/ui/ScanNotes'

const MAX_SIZE = 200 * 1024 * 1024

export default function Scanner() {
  const [file, setFile] = useState(null)
  const [preview, setPreview] = useState(null)
  const [uploading, setUploading] = useState(false)
  const [status, setStatus] = useState('idle') // idle | uploading | analyzing | error | done
  const [errorMsg, setErrorMsg] = useState('')
  const [result, setResult] = useState(null)
  const [health, setHealth] = useState(null)
  const pollRef = useRef(null)
  const activeRef = useRef(true)
  useEffect(() => {
    activeRef.current = true
    api.get('/health').then(({ data }) => setHealth(data)).catch(() => setHealth({ status: 'offline' }))
    return () => { activeRef.current = false; clearTimeout(pollRef.current) }
  }, [])
  useEffect(() => () => { if (preview?.startsWith('blob:')) URL.revokeObjectURL(preview) }, [preview])

  const onDrop = useCallback((accepted) => {
    const f = accepted[0]
    if (!f) return
    if (f.size > MAX_SIZE) {
      setErrorMsg('File exceeds 200 MB limit.')
      return
    }
    setFile(f)
    setResult(null)
    setErrorMsg('')
    setStatus('idle')
    setPreview(URL.createObjectURL(f))
  }, [])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'image/jpeg': ['.jpg', '.jpeg'],
      'image/png': ['.png'],
      'image/webp': ['.webp'],
      'image/bmp': ['.bmp'],
      'video/mp4': ['.mp4'],
      'video/quicktime': ['.mov'],
      'video/x-msvideo': ['.avi'],
      'video/x-matroska': ['.mkv'],
      'video/webm': ['.webm'],
    },
    maxFiles: 1,
    multiple: false,
    maxSize: MAX_SIZE,
    disabled: uploading,
    onDropRejected: () => setErrorMsg('Choose a supported image or video below 200 MB.'),
  })

  const reset = () => {
    clearTimeout(pollRef.current)
    setFile(null)
    setPreview(null)
    setStatus('idle')
    setErrorMsg('')
    setResult(null)
  }

  const handleUpload = async () => {
    if (!file || uploading) return
    setUploading(true)
    setStatus('uploading')
    setErrorMsg('')
    setResult(null)
    try {
      const form = new FormData()
      form.append('file', file)
      const { data } = await api.post('/scans', form, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      if (!activeRef.current) return
      setStatus('analyzing')

      const started = Date.now()
      const poll = async () => {
        if (!activeRef.current) return
        try {
          if (Date.now() - started > 10 * 60 * 1000) throw new Error('Analysis timed out. Open the full report to check its status.')
          const { data: scan } = await api.get(`/scans/${data.id}`)
          if (!activeRef.current) return
          if (scan.status === 'completed') {
            setResult(scan)
            setStatus('done')
            setUploading(false)
          } else if (scan.status === 'failed') {
            setStatus('error')
            setErrorMsg(scan.error || 'Scan failed.')
            setUploading(false)
          } else {
            pollRef.current = setTimeout(poll, 1500)
          }
        } catch (err) {
          setStatus('error')
          setErrorMsg(err.message || 'Lost connection to the server.')
          setUploading(false)
        }
      }
      pollRef.current = setTimeout(poll, 500)
    } catch (err) {
      setStatus('error')
      const detail = err.response?.data?.detail
      setErrorMsg(Array.isArray(detail) ? detail.map(d => d.msg).join(', ') : detail || 'Upload failed.')
      setUploading(false)
    }
  }

  const fileType = file?.type?.startsWith('video') ? 'video' : 'image'
  const mediaUrl = result ? scanMediaUrl(result) : ''

  const hasScore = result?.report?.ml_probability != null

  return (
    <div className="min-h-screen bg-fortexa-bg text-fortexa-text">
      <header className="border-b border-white/10 bg-fortexa-bg/80">
        <div className="mx-auto flex max-w-5xl items-center justify-between gap-4 px-4 py-4 lg:px-8">
          <Logo />
          <div className="flex items-center gap-5">
            <div role="status" className="hidden items-center gap-2 text-xs text-fortexa-muted sm:flex">
              <ShieldCheck size={14} className={health?.detection_engine?.status === 'ml-ai-image-classifier' ? 'text-fortexa-primary' : 'text-amber-300'} />
              {!health ? 'Connecting…' : health.status === 'offline' ? 'Offline' : health.database !== 'connected' ? 'Service unavailable' : health.detection_engine?.status === 'ml-ai-image-classifier' ? 'Ready' : 'Model unavailable'}
            </div>
            <Link to="/history" className="btn-secondary !px-3"><History size={16} /> Your Scans</Link>
          </div>
        </div>
      </header>

      {status === 'done' && result ? (
        <main className="mx-auto max-w-3xl animate-fade-in px-4 py-10 lg:px-8">
          <div className="card flex flex-col items-center text-center">
            <h1 className="mb-6 text-2xl font-bold">{result.verdict === 'inconclusive' ? 'Inconclusive Analysis' : 'Analysis Result'}</h1>
            {hasScore && <Gauge value={result.fake_probability || 0} size={200} />}
            {result.verdict && <div className="mt-4"><VerdictBadge verdict={result.verdict} /></div>}
            <p className="mt-3 max-w-full truncate text-sm text-fortexa-muted">{result.filename}</p>
            {!hasScore && <p className="mt-3 text-sm text-amber-300">
              {result.report?.warnings?.some(warning => warning.includes('insufficient visual detail'))
                ? 'Image is too small or has insufficient visual detail.'
                : 'Classification unavailable. Check the report for details.'}
            </p>}
          </div>
          <div className="card mt-6 !p-0 overflow-hidden">
            {result.media_type === 'video'
              ? <video src={mediaUrl} controls className="max-h-80 w-full bg-black" />
              : <img src={mediaUrl} alt="Uploaded" className="max-h-80 w-full object-contain bg-black" />}
          </div>
          <ScanNotes warnings={result.report?.warnings} isVideo={result.media_type === 'video'} />
          <div className="mt-6 flex flex-wrap justify-center gap-3">
            <Link to={`/results/${result.id}`} className="btn-secondary">Full Report</Link>
            <button onClick={() => downloadReport(result)} className="btn-secondary">Download Report</button>
            <button onClick={reset} className="btn-primary"><Upload size={16} /> Scan Another File</button>
          </div>
        </main>
      ) : (
        <main className="mx-auto max-w-3xl px-4 py-10 sm:py-16 lg:px-8">
          <div className="mb-8 text-center">
            <p className="mb-3 text-xs font-medium uppercase tracking-widest text-fortexa-primary">AI Image Detection</p>
            <h1 className="text-3xl font-bold tracking-tight sm:text-4xl">Scan Your Media</h1>
            <p className="mt-3 text-sm text-fortexa-muted">Check a photo or video for AI-generated content.</p>
          </div>
          {errorMsg && status !== 'error' && <p role="alert" className="mb-4 text-sm text-red-300">{errorMsg}</p>}
          {!file ? (
            <div {...getRootProps()} className={`glass card flex cursor-pointer flex-col items-center py-14 text-center transition-all ${isDragActive ? 'border-fortexa-primary/60 bg-fortexa-primary/10' : 'glass-hover'}`}>
              <input {...getInputProps()} />
              <div className="mb-5 rounded-2xl bg-fortexa-primary/10 p-4"><Upload size={32} className="text-fortexa-primary" /></div>
              <p className="text-lg font-semibold">{isDragActive ? 'Drop your file here' : 'Drag & drop a file'}</p>
              <p className="mt-2 text-sm text-fortexa-muted">or click to browse</p>
              <p className="mt-5 text-xs text-fortexa-muted">Images & videos · Up to 200 MB</p>
            </div>
          ) : (
            <div className="glass card">
              <div className="mb-4 flex items-center justify-between gap-3">
                <div className="flex min-w-0 items-center gap-3">
                  {fileType === 'image' ? <ImageIcon size={20} className="shrink-0 text-fortexa-primary" /> : <Film size={20} className="shrink-0 text-fortexa-primary" />}
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium">{file.name}</p>
                    <p className="text-xs text-fortexa-muted">{(file.size / 1024 / 1024).toFixed(1)} MB</p>
                  </div>
                </div>
                {!uploading && <button onClick={reset} aria-label="Remove selected file" className="shrink-0 p-2 text-fortexa-muted hover:text-red-400"><X size={18} /></button>}
              </div>
              {preview && (fileType === 'image'
                ? <img src={preview} alt="Preview" className="max-h-80 w-full rounded-xl object-contain bg-black" />
                : <video src={preview} controls className="max-h-80 w-full rounded-xl bg-black" />)}
              <div className="mt-5">
                {status === 'idle' && <button onClick={handleUpload} className="btn-primary w-full !py-3"><Upload size={16} /> Start Analysis</button>}
                {(status === 'uploading' || status === 'analyzing') && <div role="status" className="flex items-center justify-center gap-3 py-3">
                  <Loader2 size={18} className="animate-spin text-fortexa-primary" />
                  <span className="text-sm text-fortexa-muted">{status === 'uploading' ? 'Uploading…' : 'Analyzing…'}</span>
                </div>}
                {status === 'error' && <div role="alert" className="flex flex-wrap items-center gap-3 rounded-xl bg-red-500/10 p-4">
                  <AlertCircle size={18} className="shrink-0 text-red-400" />
                  <span className="min-w-0 flex-1 text-sm text-red-300">{errorMsg}</span>
                  <button onClick={reset} className="btn-secondary !py-1 !px-3">Try again</button>
                </div>}
              </div>
            </div>
          )}
          <ScanNotes evaluation={health?.detection_engine} retentionHours={health?.retention_hours || 24} />
        </main>
      )}

      <footer className="border-t border-white/10">
        <div className="mx-auto flex max-w-5xl flex-wrap items-center justify-between gap-4 px-4 py-6 text-xs text-fortexa-muted lg:px-8">
          <span>© {new Date().getFullYear()} Fortexa</span>
          <nav className="flex gap-5"><Link to="/privacy" className="hover:text-white">Privacy</Link><Link to="/terms" className="hover:text-white">Terms</Link></nav>
        </div>
      </footer>
    </div>
  )
}
