import { useState, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { useDropzone } from 'react-dropzone'
import {
  Upload, Image as ImageIcon, Film, X, AlertCircle, Loader2, ShieldCheck,
  ScanFace, BrainCircuit, Gauge as GaugeIcon, Lock, Zap, FileSearch, ChevronDown,
  ArrowRight, Activity, Layers,
} from 'lucide-react'
import api from '../api/client'
import Logo from '../components/layout/Logo'
import Gauge from '../components/ui/Gauge'
import VerdictBadge from '../components/ui/VerdictBadge'

const MAX_SIZE = 200 * 1024 * 1024 // 200 MB

const features = [
  {
    icon: ImageIcon,
    title: 'Photo Forensics',
    desc: 'Multi-signal analysis of still images — ELA, frequency spectrum, noise inconsistency, blending seams and illumination mismatch.',
  },
  {
    icon: Film,
    title: 'Video Analysis',
    desc: 'Frame-by-frame temporal detection with timeline visualization, face tracking and flicker/stability scoring.',
  },
  {
    icon: BrainCircuit,
    title: 'ML Engine',
    desc: 'Deep-learning inference blended with classical forensic heuristics for a hybrid verdict you can trust.',
  },
  {
    icon: GaugeIcon,
    title: 'Confidence Scoring',
    desc: 'Every scan ships with a fake probability, confidence level, risk classification and per-signal breakdown.',
  },
  {
    icon: Lock,
    title: 'Private by Design',
    desc: 'No account needed, no tracking cookies, no data selling. Uploads expire automatically.',
  },
  {
    icon: Zap,
    title: 'Instant Results',
    desc: 'Background processing pipeline returns a full forensic report in seconds — never blocks your browser.',
  },
]

const steps = [
  { icon: FileSearch, step: '01', title: 'Upload Media', desc: 'Drop a photo or video. The platform auto-detects media type and queues analysis.' },
  { icon: Activity, step: '02', title: 'Forensic Analysis', desc: 'The ML + heuristic engine evaluates multiple tampering signals across faces and frames.' },
  { icon: ShieldCheck, step: '03', title: 'Get Verdict', desc: 'Receive a clear percentage score, confidence gauge, signal breakdown and heatmap.' },
]

const faqs = [
  {
    q: 'What is a deepfake?',
    a: 'A deepfake is synthetic or manipulated media created using artificial intelligence — typically swapping faces, generating realistic faces of people who do not exist, or animating someone to say things they never said. Fortexa looks for the statistical fingerprints these generation pipelines leave behind.',
  },
  {
    q: 'How accurate is the detection?',
    a: 'Accuracy varies by content type, compression level and manipulation quality. The engine reports a confidence value alongside every verdict so you can judge how much to trust each result. Treat all output as a strong signal, not legal proof.',
  },
  {
    q: 'What file types are supported?',
    a: 'Images: JPG, PNG, WebP. Videos: MP4, MOV, AVI, MKV, WebM — up to 200 MB per file. Larger files are rejected before upload begins.',
  },
  {
    q: 'Do I need to create an account?',
    a: 'No. Fortexa works without registration. Upload, get your result via a unique link, done. No email, no password, no tracking.',
  },
  {
    q: 'What happens to my uploaded files?',
    a: 'Files are stored temporarily on the server only to run the analysis and show you the result. They are not shared with anyone and expire automatically. See our Privacy Policy for details.',
  },
  {
    q: 'Can this be used as evidence?',
    a: 'No. This is an educational and research tool. While results indicate likelihood of manipulation, they should never be used as sole evidence in legal, employment or disciplinary decisions.',
  },
]

function FaqItem({ q, a }) {
  const [open, setOpen] = useState(false)
  return (
    <div className="glass glass-hover rounded-2xl">
      <button
        onClick={() => setOpen(!open)}
        className="flex w-full items-center justify-between gap-4 px-6 py-4 text-left"
      >
        <span className="text-sm font-semibold">{q}</span>
        <ChevronDown size={18} className={`shrink-0 text-fortexa-muted transition-transform duration-300 ${open ? 'rotate-180' : ''}`} />
      </button>
      {open && (
        <p className="animate-fade-in px-6 pb-5 text-sm leading-relaxed text-fortexa-muted">{a}</p>
      )}
    </div>
  )
}

export default function Scanner() {
  const [file, setFile] = useState(null)
  const [preview, setPreview] = useState(null)
  const [uploading, setUploading] = useState(false)
  const [status, setStatus] = useState('idle') // idle | uploading | analyzing | error | done
  const [errorMsg, setErrorMsg] = useState('')
  const [result, setResult] = useState(null)

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
    if (f.type.startsWith('image/')) {
      const reader = new FileReader()
      reader.onload = (e) => setPreview(e.target.result)
      reader.readAsDataURL(f)
    } else {
      setPreview(URL.createObjectURL(f))
    }
  }, [])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'image/jpeg': ['.jpg', '.jpeg'],
      'image/png': ['.png'],
      'image/webp': ['.webp'],
      'video/mp4': ['.mp4'],
      'video/quicktime': ['.mov', '.qt'],
      'video/x-msvideo': ['.avi'],
      'video/x-matroska': ['.mkv'],
      'video/webm': ['.webm'],
    },
    maxFiles: 1,
    multiple: false,
  })

  const reset = () => {
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
      setStatus('analyzing')

      const poll = setInterval(async () => {
        try {
          const { data: scan } = await api.get(`/scans/${data.id}`)
          if (scan.status === 'completed') {
            clearInterval(poll)
            setResult(scan)
            setStatus('done')
            setUploading(false)
          } else if (scan.status === 'failed') {
            clearInterval(poll)
            setStatus('error')
            setErrorMsg(scan.error || 'Scan failed.')
            setUploading(false)
          }
        } catch {
          clearInterval(poll)
          setStatus('error')
          setErrorMsg('Lost connection to the server.')
          setUploading(false)
        }
      }, 1500)
    } catch (err) {
      setStatus('error')
      const detail = err.response?.data?.detail
      setErrorMsg(Array.isArray(detail) ? detail.map(d => d.msg).join(', ') : detail || 'Upload failed.')
      setUploading(false)
    }
  }

  const fileType = file?.type?.startsWith('video') ? 'video' : 'image'
  const mediaUrl = result ? `/api/scans/${result.id}/media/${result.filename}` : ''

  return (
    <div className="min-h-screen bg-fortexa-bg text-fortexa-text">
      {/* ── Header ─────────────────────────────────────────── */}
      <header className="sticky top-0 z-40 border-b border-white/10 bg-fortexa-bg/80 backdrop-blur-xl">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-4 lg:px-8">
          <Logo />
          <nav className="hidden items-center gap-8 text-sm text-fortexa-muted md:flex">
            <a href="#detect" className="hover:text-white transition-colors">Detect</a>
            <a href="#features" className="hover:text-white transition-colors">Features</a>
            <a href="#how" className="hover:text-white transition-colors">How it works</a>
            <a href="#faq" className="hover:text-white transition-colors">FAQ</a>
          </nav>
          <div className="hidden items-center gap-2 text-xs text-fortexa-muted sm:flex">
            <ShieldCheck size={14} className="text-fortexa-primary" />
            Engine Online
          </div>
        </div>
      </header>

      {/* ══ RESULT VIEW ═════════════════════════════════════ */}
      {status === 'done' && result && (
        <section className="mx-auto max-w-5xl animate-fade-in px-4 py-14 lg:px-8">
          <div className="card flex flex-col items-center py-12">
            <Gauge value={result.fake_probability || 0} size={220} />
            <div className="mt-6 flex items-center gap-3">
              {result.verdict && <VerdictBadge verdict={result.verdict} />}
              <span className="text-sm text-fortexa-muted">
                Confidence: {Math.round((result.confidence || 0) * 100)}%
              </span>
            </div>
            <h2 className="mt-3 text-2xl font-bold capitalize">
              {(result.risk_label || result.risk_level || '')} Risk Detected
            </h2>
            <p className="mt-1 truncate text-sm text-fortexa-muted">{result.filename}</p>
          </div>

          <div className="mt-8 grid gap-6 md:grid-cols-2">
            <div className="card !p-0 overflow-hidden">
              {fileType === 'video' ? (
                <video src={mediaUrl} controls className="h-64 w-full object-cover bg-black" />
              ) : (
                <img src={mediaUrl} alt="Uploaded" className="h-64 w-full object-cover bg-black" />
              )}
              <div className="grid grid-cols-2 gap-x-6 gap-y-2 p-5 text-sm">
                <div className="flex justify-between"><span className="text-fortexa-muted">Fake</span><span>{Math.round((result.fake_probability || 0) * 100)}%</span></div>
                <div className="flex justify-between"><span className="text-fortexa-muted">Real</span><span>{Math.round((result.real_probability || 0) * 100)}%</span></div>
                <div className="flex justify-between"><span className="text-fortexa-muted">Method</span><span>{result.method}</span></div>
                <div className="flex justify-between"><span className="text-fortexa-muted">Analysis Time</span><span>{result.duration_ms ? `${(result.duration_ms / 1000).toFixed(1)}s` : '—'}</span></div>
              </div>
            </div>

            <div className="card !p-0 overflow-hidden">
              <img
                src={`/api/scans/${result.id}/media/heatmap.jpg`}
                alt="Forensic Heatmap"
                className="h-64 w-full object-contain bg-black"
                onError={(e) => { e.target.style.display = 'none' }}
              />
              <div className="p-5 text-xs text-fortexa-muted">
                Forensic heatmap highlighting manipulated regions detected by the engine.
              </div>
            </div>
          </div>

          <div className="mt-8 flex justify-center">
            <button onClick={reset} className="btn-primary !px-8 !py-3 !text-base">
              <Upload size={18} /> Scan Another File
            </button>
          </div>
        </section>
      )}

      {/* ══ MAIN LANDING ════════════════════════════════════ */}
      {status !== 'done' && (
        <>
          {/* Hero */}
          <section className="bg-hero-glow relative overflow-hidden border-b border-white/10">
            <div className="bg-grid absolute inset-0" />
            <div className="relative mx-auto max-w-7xl px-4 pb-16 pt-16 text-center lg:px-8 lg:pt-24">
              <div className="mx-auto mb-6 inline-flex items-center gap-2 rounded-full border border-fortexa-primary/30 bg-fortexa-primary/10 px-4 py-1.5 text-xs font-medium text-emerald-300">
                <ScanFace size={14} />
                AI-Powered Media Forensics · Free & No Sign-Up
              </div>
              <h1 className="mx-auto max-w-4xl text-4xl font-extrabold leading-tight tracking-tight sm:text-5xl lg:text-6xl">
                Is It Real? <span className="text-gradient">Find Out in Seconds.</span>
              </h1>
              <p className="mx-auto mt-6 max-w-2xl text-lg text-fortexa-muted">
                Fortexa exposes AI-generated and manipulated photos & videos using six forensic
                signal detectors plus a hybrid machine-learning engine — completely free.
              </p>
              <div className="mx-auto mt-8 grid max-w-2xl grid-cols-2 gap-4 sm:grid-cols-4">
                {[
                  { v: '6+', l: 'Forensic Signals' },
                  { v: 'Hybrid', l: 'ML + Heuristic' },
                  { v: '0₹', l: 'Cost Forever' },
                  { v: '0', l: 'Accounts Needed' },
                ].map((s) => (
                  <div key={s.l} className="rounded-2xl border border-white/10 bg-white/[0.03] p-4 backdrop-blur-xl">
                    <p className="text-xl font-extrabold text-gradient sm:text-2xl">{s.v}</p>
                    <p className="mt-1 text-[11px] text-fortexa-muted sm:text-xs">{s.l}</p>
                  </div>
                ))}
              </div>
            </div>
          </section>

          {/* Upload section */}
          <section id="detect" className="mx-auto max-w-6xl scroll-mt-20 px-4 py-16 lg:px-8">
            <div className="mb-10 text-center">
              <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">Scan Your Media</h2>
              <p className="mx-auto mt-3 max-w-xl text-sm text-fortexa-muted">
                Drop any photo or video below — no sign-up, no payment, instant forensic report.
              </p>
            </div>

            <div className="grid gap-8 lg:grid-cols-2">
              {/* Drop zone / file card */}
              <div>
                {!file ? (
                  <div
                    {...getRootProps()}
                    className={`glass card flex h-full cursor-pointer flex-col items-center justify-center py-20 text-center transition-all ${
                      isDragActive ? 'border-fortexa-primary/60 bg-fortexa-primary/10 scale-[1.01]' : 'glass-hover'
                    }`}
                  >
                    <input {...getInputProps()} />
                    <div className="mb-6 rounded-2xl bg-gradient-to-br from-fortexa-primary/25 to-fortexa-secondary/15 p-5 shadow-lg shadow-fortexa-primary/20">
                      <Upload size={40} className="text-fortexa-primary" />
                    </div>
                    <p className="text-lg font-semibold">
                      {isDragActive ? 'Drop your file here' : 'Drag & drop media here'}
                    </p>
                    <p className="mt-1 text-sm text-fortexa-muted">
                      or click to browse · JPG, PNG, WebP, MP4, MOV, AVI, MKV, WebM
                    </p>
                    <p className="mt-2 text-xs text-fortexa-muted/60">Max file size: 200 MB</p>
                  </div>
                ) : (
                  <div className="glass card h-full">
                    <div className="mb-4 flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <div className="rounded-xl bg-white/5 p-2.5">
                          {fileType === 'image'
                            ? <ImageIcon size={20} className="text-emerald-400" />
                            : <Film size={20} className="text-lime-400" />}
                        </div>
                        <div>
                          <p className="max-w-[240px] truncate text-sm font-medium">{file.name}</p>
                          <p className="text-xs text-fortexa-muted">{(file.size / 1024 / 1024).toFixed(1)} MB</p>
                        </div>
                      </div>
                      {!uploading && (
                        <button onClick={reset} className="text-fortexa-muted hover:text-red-400">
                          <X size={18} />
                        </button>
                      )}
                    </div>

                    {preview && (fileType === 'image' ? (
                      <img src={preview} alt="Preview" className="max-h-64 w-full rounded-xl object-cover" />
                    ) : (
                      <video src={preview} controls className="max-h-64 w-full rounded-xl bg-black" />
                    ))}

                    <div className="mt-5 flex items-center gap-3">
                      {status === 'idle' && (
                        <button onClick={handleUpload} className="btn-primary flex-1 !py-3">
                          <Upload size={16} /> Start Analysis
                        </button>
                      )}
                      {(status === 'uploading' || status === 'analyzing') && (
                        <div className="flex w-full items-center justify-center gap-3 rounded-xl bg-white/5 py-3">
                          <Loader2 size={18} className="animate-spin text-fortexa-primary" />
                          <span className="text-sm text-fortexa-muted">
                            {status === 'uploading' ? 'Uploading…' : 'Running forensic analysis…'}
                          </span>
                        </div>
                      )}
                      {status === 'error' && (
                        <div className="flex w-full items-center gap-3 rounded-xl bg-red-500/10 py-3 px-4">
                          <AlertCircle size={18} className="shrink-0 text-red-400" />
                          <span className="truncate text-sm text-red-300">{errorMsg}</span>
                          <button onClick={reset} className="ml-auto shrink-0 btn-secondary !py-1 !px-3 text-xs">Try again</button>
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </div>

              {/* Info panel */}
              <div className="space-y-6">
                <div className="card">
                  <h3 className="mb-4 text-lg font-semibold">How scanning works</h3>
                  <ol className="space-y-4">
                    {steps.map((s) => (
                      <li key={s.step} className="flex gap-4">
                        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-fortexa-primary/15 text-fortexa-primary">
                          <s.icon size={17} />
                        </span>
                        <div>
                          <p className="text-sm font-semibold">{s.title}</p>
                          <p className="text-xs leading-relaxed text-fortexa-muted">{s.desc}</p>
                        </div>
                      </li>
                    ))}
                  </ol>
                </div>
                <div className="card">
                  <h3 className="mb-3 text-lg font-semibold">Supported formats</h3>
                  <div className="grid grid-cols-2 gap-3 text-sm">
                    <div className="rounded-xl bg-white/[0.03] p-3">
                      <p className="mb-2 text-xs font-medium uppercase tracking-wide text-emerald-400">Images</p>
                      <div className="flex flex-wrap gap-1.5">
                        {['JPG', 'PNG', 'WebP'].map((f) => (
                          <span key={f} className="rounded-md border border-white/10 bg-white/5 px-2 py-0.5 text-xs text-fortexa-muted">{f}</span>
                        ))}
                      </div>
                    </div>
                    <div className="rounded-xl bg-white/[0.03] p-3">
                      <p className="mb-2 text-xs font-medium uppercase tracking-wide text-lime-400">Videos</p>
                      <div className="flex flex-wrap gap-1.5">
                        {['MP4', 'MOV', 'AVI', 'MKV', 'WebM'].map((f) => (
                          <span key={f} className="rounded-md border border-white/10 bg-white/5 px-2 py-0.5 text-xs text-fortexa-muted">{f}</span>
                        ))}
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </section>

          {/* Features */}
          <section id="features" className="scroll-mt-20 border-y border-white/10 bg-fortexa-card/30">
            <div className="mx-auto max-w-7xl px-4 py-20 lg:px-8">
              <div className="mb-14 text-center">
                <h2 className="text-3xl font-bold sm:text-4xl">Built for Serious Forensics</h2>
                <p className="mx-auto mt-3 max-w-2xl text-sm text-fortexa-muted">
                  Every scan runs through a multi-layer detection pipeline that surfaces exactly why a verdict was reached.
                </p>
              </div>
              <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
                {features.map((f, i) => (
                  <div key={f.title} className="glass glass-hover card animate-slide-up" style={{ animationDelay: `${i * 60}ms` }}>
                    <div className="mb-4 inline-flex rounded-xl border border-fortexa-primary/20 bg-gradient-to-br from-fortexa-primary/20 to-fortexa-secondary/10 p-3 text-fortexa-primary">
                      <f.icon size={22} />
                    </div>
                    <h3 className="text-lg font-semibold">{f.title}</h3>
                    <p className="mt-2 text-sm leading-relaxed text-fortexa-muted">{f.desc}</p>
                  </div>
                ))}
              </div>
            </div>
          </section>

          {/* How it works */}
          <section id="how" className="mx-auto max-w-7xl scroll-mt-20 px-4 py-20 lg:px-8">
            <div className="mb-14 text-center">
              <h2 className="text-3xl font-bold sm:text-4xl">Three Steps to a Verdict</h2>
              <p className="mx-auto mt-3 max-w-2xl text-sm text-fortexa-muted">
                From upload to a fully explainable forensic report in seconds.
              </p>
            </div>
            <div className="grid gap-8 md:grid-cols-3">
              {steps.map((s) => (
                <div key={s.step} className="relative rounded-2xl border border-white/10 bg-white/[0.03] p-7">
                  <span className="absolute right-6 top-6 text-5xl font-extrabold text-white/5">{s.step}</span>
                  <div className="mb-4 inline-flex rounded-xl border border-white/10 bg-white/5 p-3 text-fortexa-secondary">
                    <s.icon size={22} />
                  </div>
                  <h3 className="text-lg font-semibold">{s.title}</h3>
                  <p className="mt-2 text-sm leading-relaxed text-fortexa-muted">{s.desc}</p>
                </div>
              ))}
            </div>

            {/* Tech strip */}
            <div className="mt-14 text-center">
              <div className="mb-6 flex items-center justify-center gap-2 text-xs font-medium uppercase tracking-widest text-fortexa-muted">
                <Layers size={13} /> Technology Stack
              </div>
              <div className="flex flex-wrap items-center justify-center gap-2.5">
                {['PyTorch', 'Transformers', 'FastAPI', 'React', 'Tailwind CSS', 'OpenCV', 'SQLite', 'JWT-ready API'].map((t) => (
                  <span key={t} className="rounded-full border border-white/10 bg-white/5 px-4 py-2 text-xs font-medium text-fortexa-muted transition-all hover:border-fortexa-primary/40 hover:text-white">
                    {t}
                  </span>
                ))}
              </div>
            </div>
          </section>

          {/* FAQ */}
          <section id="faq" className="scroll-mt-20 border-y border-white/10 bg-fortexa-card/30">
            <div className="mx-auto max-w-3xl px-4 py-20 lg:px-8">
              <div className="mb-12 text-center">
                <h2 className="text-3xl font-bold sm:text-4xl">Frequently Asked Questions</h2>
                <p className="mx-auto mt-3 max-w-xl text-sm text-fortexa-muted">
                  Everything you need to know about the platform.
                </p>
              </div>
              <div className="space-y-3">
                {faqs.map((f) => <FaqItem key={f.q} {...f} />)}
              </div>
            </div>
          </section>

          {/* CTA */}
          <section className="mx-auto max-w-7xl px-4 py-20 lg:px-8">
            <div className="relative overflow-hidden rounded-3xl border border-fortexa-primary/30 bg-gradient-to-br from-fortexa-primary/20 via-fortexa-card/60 to-fortexa-secondary/15 p-12 text-center">
              <div className="bg-grid absolute inset-0 opacity-40" />
              <div className="relative">
                <ScanFace className="mx-auto mb-4 text-fortexa-primary" size={40} />
                <h2 className="text-3xl font-bold">Ready to verify media with confidence?</h2>
                <p className="mx-auto mt-3 max-w-xl text-sm text-fortexa-muted">
                  Scroll up, drop a file, and get your forensic report — free forever.
                </p>
                <a href="#detect" className="btn-primary mt-8 !px-8 !py-3.5 !text-base">
                  Start Scanning Free <ArrowRight size={18} />
                </a>
              </div>
            </div>
          </section>
        </>
      )}

      {/* ── Footer ─────────────────────────────────────────── */}
      <footer className="border-t border-white/10 py-10">
        <div className="mx-auto flex max-w-7xl flex-col items-center justify-between gap-6 px-4 text-sm text-fortexa-muted sm:flex-row lg:px-8">
          <Logo size="sm" />
          <nav className="flex flex-wrap items-center justify-center gap-x-6 gap-y-2">
            <a href="#features" className="hover:text-white">Features</a>
            <a href="#faq" className="hover:text-white">FAQ</a>
            <Link to="/terms" className="hover:text-white">Terms of Service</Link>
            <Link to="/privacy" className="hover:text-white">Privacy Policy</Link>
          </nav>
        </div>
        <p className="mt-6 text-center text-xs text-fortexa-muted/50">
          © {new Date().getFullYear()} Fortexa · Deepfake Detection Platform · Final Year Project
        </p>
      </footer>
    </div>
  )
}
