import { Link } from 'react-router-dom'
import {
  ScanFace, Image as ImageIcon, Film, BrainCircuit, ShieldCheck, Gauge,
  Activity, Zap, Lock, ArrowRight, Sparkles, Layers, ServerCog, FileSearch,
} from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import Logo from '../components/layout/Logo'

const features = [
  {
    icon: ImageIcon,
    title: 'Photo Forensics',
    desc: 'Multi-signal analysis of still images — ELA, frequency spectrum, noise inconsistency, blending seams and illumination mismatch.',
  },
  {
    icon: Film,
    title: 'Video Analysis',
    desc: 'Frame-by-frame temporal deepfake detection with timeline visualization, face tracking and flicker/stability scoring.',
  },
  {
    icon: BrainCircuit,
    title: 'PyTorch ML Engine',
    desc: 'Train your own detector with the built-in PyTorch pipeline and Hugging Face transformers, blended with forensic heuristics.',
  },
  {
    icon: Gauge,
    title: 'Confidence Scoring',
    desc: 'Every result ships with a fake probability, confidence level, risk classification and a full per-signal breakdown.',
  },
  {
    icon: Lock,
    title: 'Enterprise Security',
    desc: 'JWT + optional OAuth authentication, role-based access control, and private per-user scan storage.',
  },
  {
    icon: ServerCog,
    title: 'Background Processing',
    desc: 'Redis + Celery async pipeline with a transparent inline fallback — scans never block the interface.',
  },
]

const steps = [
  { icon: FileSearch, step: '01', title: 'Upload Media', desc: 'Drop a photo or video. The platform automatically detects the media type and queues analysis.' },
  { icon: Activity, step: '02', title: 'Forensic Analysis', desc: 'The ML + forensic engine evaluates multiple tampering signals across faces and frames.' },
  { icon: ShieldCheck, step: '03', title: 'Get Verdict', desc: 'Receive a clear verdict, confidence gauge, per-signal breakdown and visual heatmaps.' },
]

const tech = [
  'PyTorch', 'Transformers', 'FastAPI', 'React', 'Tailwind CSS',
  'PostgreSQL', 'Redis', 'Celery', 'JWT / OAuth', 'Docker-ready',
]

export default function Landing() {
  const { user } = useAuth()
  const ctaTarget = user ? '/app' : '/register'

  return (
    <div className="min-h-screen bg-fortexa-bg text-fortexa-text">
      {/* ── Nav ─────────────────────────────────────────── */}
      <header className="sticky top-0 z-40 border-b border-white/10 bg-fortexa-bg/80 backdrop-blur-xl">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-4 lg:px-8">
          <Logo />
          <nav className="hidden items-center gap-8 text-sm text-fortexa-muted md:flex">
            <a href="#features" className="hover:text-white transition-colors">Features</a>
            <a href="#how" className="hover:text-white transition-colors">How it works</a>
            <a href="#tech" className="hover:text-white transition-colors">Technology</a>
          </nav>
          <div className="flex items-center gap-3">
            {user ? (
              <Link to="/app" className="btn-primary">Go to Dashboard <ArrowRight size={16} /></Link>
            ) : (
              <>
                <Link to="/login" className="btn-secondary">Sign in</Link>
                <Link to="/register" className="btn-primary">Get Started</Link>
              </>
            )}
          </div>
        </div>
      </header>

      {/* ── Hero ────────────────────────────────────────── */}
      <section className="bg-hero-glow relative overflow-hidden">
        <div className="bg-grid absolute inset-0" />
        <div className="relative mx-auto max-w-7xl px-4 pb-20 pt-24 text-center lg:px-8 lg:pt-32">
          <div className="mx-auto mb-6 inline-flex items-center gap-2 rounded-full border border-fortexa-primary/30 bg-fortexa-primary/10 px-4 py-1.5 text-xs font-medium text-indigo-300">
            <Sparkles size={14} />
            AI-Powered Media Forensics Platform
          </div>
          <h1 className="mx-auto max-w-4xl text-4xl font-extrabold leading-tight tracking-tight sm:text-5xl lg:text-6xl">
            Detect Deepfakes in <span className="text-gradient">Photos & Videos</span> with Enterprise-Grade Forensics
          </h1>
          <p className="mx-auto mt-6 max-w-2xl text-lg text-fortexa-muted">
            Fortexa combines a PyTorch deep-learning engine with six forensic
            signal detectors to expose manipulated media — fast, explainable and accurate.
          </p>
          <div className="mt-10 flex flex-col items-center justify-center gap-4 sm:flex-row">
            <Link to={ctaTarget} className="btn-primary !px-8 !py-3.5 !text-base">
              Start Scanning Free <ArrowRight size={18} />
            </Link>
            <a href="#how" className="btn-secondary !px-8 !py-3.5 !text-base">
              See How It Works
            </a>
          </div>
{/* ── Features ────────────────────────────────────── */}
      <section id="features" className="mx-auto max-w-7xl px-4 py-20 lg:px-8">
        <div className="mb-14 text-center">
          <h2 className="text-3xl font-bold sm:text-4xl">Built for Serious Forensic Analysis</h2>
          <p className="mx-auto mt-3 max-w-2xl text-fortexa-muted">
            Every scan runs through a multi-layer detection pipeline that surfaces exactly
            why a verdict was reached.
          </p>
        </div>
        <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {features.map((f, i) => (
            <div key={f.title} className="glass glass-hover card animate-slide-up" style={{ animationDelay: `${i * 60}ms` }}>
              <div className="mb-4 inline-flex rounded-xl bg-gradient-to-br from-fortexa-primary/20 to-fortexa-secondary/10 p-3 text-fortexa-primary border border-fortexa-primary/20">
                <f.icon size={22} />
              </div>
              <h3 className="text-lg font-semibold">{f.title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-fortexa-muted">{f.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* ── How it works ────────────────────────────────── */}
      <section id="how" className="border-y border-white/10 bg-fortexa-card/30">
        <div className="mx-auto max-w-7xl px-4 py-20 lg:px-8">
          <div className="mb-14 text-center">
            <h2 className="text-3xl font-bold sm:text-4xl">Three Steps to a Verdict</h2>
            <p className="mx-auto mt-3 max-w-2xl text-fortexa-muted">
              From upload to a fully explainable forensic report in seconds.
            </p>
          </div>
          <div className="grid gap-8 md:grid-cols-3">
            {steps.map((s) => (
              <div key={s.step} className="relative rounded-2xl border border-white/10 bg-fortexa-bg/50 p-7">
                <span className="absolute right-6 top-6 text-4xl font-extrabold text-white/5">{s.step}</span>
                <div className="mb-4 inline-flex rounded-xl bg-white/5 p-3 text-fortexa-secondary border border-white/10">
                  <s.icon size={22} />
                </div>
                <h3 className="text-lg font-semibold">{s.title}</h3>
                <p className="mt-2 text-sm leading-relaxed text-fortexa-muted">{s.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

          <p className="mt-6 text-sm text-fortexa-muted/70">No credit card required · Train your own models · Full API access</p>
        </div>

        {/* Stats strip */}
        <div className="relative mx-auto max-w-7xl px-4 pb-16 lg:px-8">
          <div className="grid grid-cols-2 gap-4 rounded-2xl border border-white/10 bg-fortexa-card/50 p-6 backdrop-blur-xl md:grid-cols-4">
            {[
              { value: '6+', label: 'Forensic Signals' },
              { value: 'Photo + Video', label: 'Media Support' },
              { value: 'ML + Heuristic', label: 'Hybrid Engine' },
              { value: '100%', label: 'Owned Data' },
            ].map((s) => (
              <div key={s.label} className="text-center">
                <p className="text-2xl font-bold text-gradient">{s.value}</p>
                <p className="mt-1 text-sm text-fortexa-muted">{s.label}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Tech stack ──────────────────────────────────── */}
      <section id="tech" className="mx-auto max-w-7xl px-4 py-20 lg:px-8">
        <div className="text-center">
          <h2 className="text-3xl font-bold">A Modern, Production-Grade Stack</h2>
          <p className="mx-auto mt-3 max-w-xl text-fortexa-muted">
            Enterprise architecture that scales from your laptop to the cloud —
            no Docker required to run locally.
          </p>
          <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
            {tech.map((t) => (
              <span key={t} className="rounded-full border border-white/10 bg-white/5 px-4 py-2 text-sm font-medium text-fortexa-muted hover:border-fortexa-primary/40 hover:text-white transition-all">
                {t}
              </span>
            ))}
          </div>
          <div className="mx-auto mt-12 flex max-w-3xl flex-col gap-4 sm:flex-row">
            <div className="flex-1 rounded-2xl border border-white/10 bg-fortexa-card/50 p-6 text-left">
              <Layers className="mb-3 text-fortexa-primary" size={22} />
              <h3 className="font-semibold">Runs Without Docker</h3>
              <p className="mt-1 text-sm text-fortexa-muted">
                One-click start scripts launch backend + frontend locally. PostgreSQL, Redis and
                Celery are optional upgrades — SQLite + inline workers keep it Docker-free.
              </p>
            </div>
            <div className="flex-1 rounded-2xl border border-white/10 bg-fortexa-card/50 p-6 text-left">
              <Zap className="mb-3 text-fortexa-secondary" size={22} />
              <h3 className="font-semibold">Train Your Own Models</h3>
              <p className="mt-1 text-sm text-fortexa-muted">
                A built-in PyTorch training pipeline lets you fine-tune the detector on your own
                real/fake dataset and hot-swap the artifact into production.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* ── CTA ─────────────────────────────────────────── */}
      <section className="mx-auto max-w-7xl px-4 pb-20 lg:px-8">
        <div className="relative overflow-hidden rounded-3xl border border-fortexa-primary/30 bg-gradient-to-br from-fortexa-primary/20 via-fortexa-card/60 to-fortexa-secondary/20 p-12 text-center">
          <div className="bg-grid absolute inset-0 opacity-40" />
          <div className="relative">
            <ScanFace className="mx-auto mb-4 text-fortexa-primary" size={40} />
            <h2 className="text-3xl font-bold">Ready to verify media with confidence?</h2>
            <p className="mx-auto mt-3 max-w-xl text-fortexa-muted">
              Join Fortexa and get a full forensic workstation for deepfake detection today.
            </p>
            <Link to={ctaTarget} className="btn-primary mt-8 !px-8 !py-3.5 !text-base">
              {user ? 'Open Dashboard' : 'Create Free Account'} <ArrowRight size={18} />
            </Link>
          </div>
        </div>
      </section>

      {/* ── Footer ──────────────────────────────────────── */}
      <footer className="border-t border-white/10 py-8">
        <div className="mx-auto flex max-w-7xl flex-col items-center justify-between gap-4 px-4 text-sm text-fortexa-muted sm:flex-row lg:px-8">
          <Logo size="sm" />
          <p>© {new Date().getFullYear()} Fortexa · Final Year Project · Deepfake Detection Platform</p>
          <div className="flex items-center gap-4">
            <a href="#" className="hover:text-white">Docs</a>
            <a href="#" className="hover:text-white">API</a>
            <a href="#" className="hover:text-white">Support</a>
          </div>
        </div>
      </footer>
    </div>
  )
}

