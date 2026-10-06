import { useState, useCallback, useEffect, useRef } from 'react'
import { Link } from 'react-router-dom'
import { useDropzone } from 'react-dropzone'
import { Upload, Image as ImageIcon, Film, X, AlertCircle, Loader2, ShieldCheck, History, Menu, FileText, Lock } from 'lucide-react'
import api, { mediaUrl as scanMediaUrl, downloadReport } from '../api/client'
import Logo from '../components/layout/Logo'
import Gauge from '../components/ui/Gauge'
import VerdictBadge from '../components/ui/VerdictBadge'
import ScanNotes from '../components/ui/ScanNotes'

const MAX_SIZE = 200 * 1024 * 1024
const ACTIVE_SCAN_KEY = 'fortexa_active_scan'
function savedScan() {
  try {
    const scan = JSON.parse(sessionStorage.getItem(ACTIVE_SCAN_KEY))
    return typeof scan?.id === 'string' && Number.isFinite(scan.started) ? scan : null
  } catch { return null }
}
const sectionLinks = [
  ['detect', 'Detect'], ['features', 'Features'], ['how', 'How it works'], ['faq', 'FAQ'],
]
const features = [
  { icon: ImageIcon, title: 'Image detection', text: 'Check photos of people, objects and scenes.' },
  { icon: Film, title: 'Video checks', text: 'Analyze sampled frames. Video detection is experimental.' },
  { icon: FileText, title: 'Downloadable reports', text: 'Save your results as a report.' },
  { icon: Lock, title: 'Private history', text: 'View and manage scans from this browser.' },
]
const faqs = [
  ['What does it detect?', 'AI-generated versus real photos—not every kind of Photoshop edit. A face is not required.'],
  ['Does WhatsApp compression make a photo fake?', 'No. Compression does not change whether an image was originally real or AI-generated.'],
  ['Can I scan videos?', 'Yes, using sampled frames. Audio and motion are not analyzed.'],
  ['Are the results guaranteed?', 'No. The model can make mistakes, especially on unfamiliar AI generators.'],
  ['Where are my scans?', 'Open Your Scans in the same browser. Scans expire automatically, or you can delete them sooner.'],
]

export default function Scanner() {
  const [menuOpen, setMenuOpen] = useState(false)
  const [activeScan, setActiveScan] = useState(savedScan)
  const [file, setFile] = useState(null)
  const [preview, setPreview] = useState(null)
  const [uploading, setUploading] = useState(() => Boolean(activeScan))
  const [status, setStatus] = useState(() => activeScan ? 'analyzing' : 'idle')
  const [errorMsg, setErrorMsg] = useState('')
  const [result, setResult] = useState(null)
  const [health, setHealth] = useState(null)
  const activeRef = useRef(true)
  useEffect(() => {
    activeRef.current = true
    api.get('/health').then(({ data }) => setHealth(data)).catch(() => setHealth({ status: 'offline' }))
    return () => { activeRef.current = false }
  }, [])
  useEffect(() => () => { if (preview?.startsWith('blob:')) URL.revokeObjectURL(preview) }, [preview])
  useEffect(() => {
    try {
      if (activeScan) sessionStorage.setItem(ACTIVE_SCAN_KEY, JSON.stringify(activeScan))
      else sessionStorage.removeItem(ACTIVE_SCAN_KEY)
    } catch { /* Polling still works when tab storage is unavailable. */ }
    if (!activeScan) return
    const controller = new AbortController()
    let timer
    const poll = async () => {
      try {
        if (Date.now() - activeScan.started > 10 * 60 * 1000) throw new Error('Analysis is taking too long. Open Your Scans to check its status.')
        const { data: scan } = await api.get(`/scans/${activeScan.id}`, { signal: controller.signal })
        if (controller.signal.aborted) return
        if (scan.status === 'completed') {
          setResult(scan)
          setStatus('done')
          setUploading(false)
          setActiveScan(null)
        } else if (scan.status === 'failed') {
          throw new Error(scan.error || 'Scan failed.')
        } else {
          timer = setTimeout(poll, 1500)
        }
      } catch (err) {
        if (controller.signal.aborted) return
        setStatus('error')
        setErrorMsg(err.response?.status === 404 ? 'This scan is unavailable. Check Your Scans.' : err.message || 'Lost connection to the server.')
        setUploading(false)
        setActiveScan(null)
      }
    }
    poll()
    return () => { controller.abort(); clearTimeout(timer) }
  }, [activeScan])

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
    setActiveScan(null)
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
      setActiveScan({ id: data.id, started: Date.now() })
    } catch (err) {
      setStatus('error')
      const detail = err.response?.data?.detail
      setErrorMsg(Array.isArray(detail) ? detail.map(d => d.msg).join(', ') : detail || 'Upload failed.')
      setUploading(false)
    }
  }

  const fileType = file?.type?.startsWith('video') ? 'video' : 'image'
  const mediaUrl = result ? scanMediaUrl(result) : ''

  const hasScore = result?.report?.ml_probability != null && typeof result?.fake_probability === 'number' && Number.isFinite(result.fake_probability)
  const navigateSection = event => {
    setMenuOpen(false)
    if (status === 'done') {
      event.preventDefault()
      const hash = event.currentTarget.hash
      reset()
      requestAnimationFrame(() => {
        document.getElementById(hash.slice(1))?.scrollIntoView({ behavior: 'smooth' })
        window.history.replaceState(window.history.state, '', hash)
      })
    }
  }

  return (
    <div className="min-h-screen bg-fortexa-bg text-fortexa-text">
      <header className="sticky top-0 z-40 border-b border-white/10 bg-fortexa-bg/90 backdrop-blur-xl">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-4 lg:px-8">
          <Logo />
          <nav aria-label="Main navigation" className="hidden items-center gap-6 text-sm text-fortexa-muted md:flex">
            {sectionLinks.map(([id, label]) => <a key={id} href={`#${id}`} onClick={navigateSection} className="transition-colors hover:text-white">{label}</a>)}
          </nav>
          <div className="flex items-center gap-3">
            <div role="status" className="hidden items-center gap-2 text-xs text-fortexa-muted lg:flex">
              <ShieldCheck size={14} className={health?.detection_engine?.status === 'ml-ai-image-classifier' ? 'text-fortexa-primary' : 'text-amber-300'} />
              {!health ? 'Connecting…' : health.status === 'offline' ? 'Offline' : health.database !== 'connected' ? 'Service unavailable' : health.detection_engine?.status === 'ml-ai-image-classifier' ? 'Ready' : 'Model unavailable'}
            </div>
            <Link to="/history" className="btn-secondary !px-3"><History size={16} /> Your Scans</Link>
            <button aria-label={menuOpen ? 'Close navigation' : 'Open navigation'} aria-expanded={menuOpen} aria-controls="mobile-navigation" onClick={() => setMenuOpen(open => !open)} className="rounded-lg p-2 text-fortexa-muted hover:text-white md:hidden">
              {menuOpen ? <X size={20} /> : <Menu size={20} />}
            </button>
          </div>
        </div>
        {menuOpen && <nav id="mobile-navigation" aria-label="Mobile navigation" className="grid grid-cols-2 gap-2 border-t border-white/10 px-4 py-3 text-sm md:hidden">
          {sectionLinks.map(([id, label]) => <a key={id} href={`#${id}`} onClick={navigateSection} className="rounded-lg px-3 py-2 text-fortexa-muted hover:bg-white/5 hover:text-white">{label}</a>)}
        </nav>}
      </header>

      {status === 'done' && result ? (
        <main className="mx-auto max-w-3xl animate-fade-in px-4 py-10 lg:px-8">
          <div className="card flex flex-col items-center text-center">
            <h1 className="mb-6 text-2xl font-bold">{result.verdict === 'inconclusive' ? 'Inconclusive Analysis' : 'Analysis Result'}</h1>
            {result.verdict && <div className="mb-5"><VerdictBadge verdict={result.verdict} size="lg" /></div>}
            {hasScore && <Gauge value={result.fake_probability} verdict={result.verdict} size={200} />}
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
        <main id="detect" className="mx-auto max-w-3xl scroll-mt-24 px-4 py-10 sm:py-16 lg:px-8">
          <div className="mb-8 text-center">
            <p className="mb-3 text-xs font-medium uppercase tracking-widest text-fortexa-primary">AI Image Detection</p>
            <h1 className="text-3xl font-bold tracking-tight sm:text-4xl">Scan Your Media</h1>
            <p className="mt-3 text-sm text-fortexa-muted">Check a photo or video for AI-generated content.</p>
          </div>
          {errorMsg && status !== 'error' && <p role="alert" className="mb-4 text-sm text-red-300">{errorMsg}</p>}
          {!file && status !== 'analyzing' && status !== 'error' ? (
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
                    <p className="truncate text-sm font-medium">{file?.name || 'Your scan'}</p>
                    {file && <p className="text-xs text-fortexa-muted">{(file.size / 1024 / 1024).toFixed(1)} MB</p>}
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

      {status !== 'done' && <>
        <section id="features" className="scroll-mt-24 border-y border-white/10 bg-fortexa-card/30">
          <div className="mx-auto max-w-6xl px-4 py-12 lg:px-8">
            <h2 className="mb-6 text-center text-2xl font-bold">Features</h2>
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              {features.map(feature => <div key={feature.title} className="glass card">
                <feature.icon size={22} className="mb-4 text-fortexa-primary" />
                <h3 className="text-sm font-semibold">{feature.title}</h3>
                <p className="mt-2 text-sm text-fortexa-muted">{feature.text}</p>
              </div>)}
            </div>
          </div>
        </section>
        <section id="how" className="mx-auto max-w-5xl scroll-mt-24 px-4 py-12 lg:px-8">
          <h2 className="mb-6 text-center text-2xl font-bold">How it works</h2>
          <ol className="grid gap-4 sm:grid-cols-3">
            {[
              ['Upload', 'Choose a photo or video.'],
              ['Analyze', 'Run the AI-image check.'],
              ['Review', 'View the result or download a report.'],
            ].map(([title, text], index) => <li key={title} className="card">
              <span className="text-xs font-semibold text-fortexa-primary">0{index + 1}</span>
              <h3 className="mt-2 text-sm font-semibold">{title}</h3>
              <p className="mt-2 text-sm text-fortexa-muted">{text}</p>
            </li>)}
          </ol>
        </section>
        <section id="faq" className="scroll-mt-24 border-t border-white/10 bg-fortexa-card/30">
          <div className="mx-auto max-w-3xl px-4 py-12 lg:px-8">
            <h2 className="mb-6 text-center text-2xl font-bold">FAQ</h2>
            <div className="space-y-3">
              {faqs.map(([question, answer]) => <details key={question} className="glass rounded-xl px-5 py-4">
                <summary className="cursor-pointer text-sm font-semibold">{question}</summary>
                <p className="mt-3 text-sm leading-relaxed text-fortexa-muted">{answer}</p>
              </details>)}
            </div>
          </div>
        </section>
      </>}

      <footer className="border-t border-white/10">
        <div className="mx-auto flex max-w-5xl flex-wrap items-center justify-between gap-4 px-4 py-6 text-xs text-fortexa-muted lg:px-8">
          <span>© {new Date().getFullYear()} Fortexa</span>
          <nav className="flex gap-5"><Link to="/privacy" className="hover:text-white">Privacy</Link><Link to="/terms" className="hover:text-white">Terms</Link></nav>
        </div>
      </footer>
    </div>
  )
}
