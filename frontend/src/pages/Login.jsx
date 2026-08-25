import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Mail, Lock, LogIn, ArrowLeft, Eye, EyeOff } from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import Logo from '../components/layout/Logo'
import Spinner from '../components/ui/Spinner'

export default function Login() {
  const { login, loading } = useAuth()
  const navigate = useNavigate()
  const [form, setForm] = useState({ email: '', password: '' })
  const [showPass, setShowPass] = useState(false)
  const [error, setError] = useState('')

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    if (!form.email || !form.password) {
      setError('Please fill in all fields.')
      return
    }
    const res = await login(form.email.trim(), form.password)
    if (res.ok) {
      navigate('/app')
    } else {
      setError(res.error || 'Invalid credentials.')
    }
  }

  return (
    <div className="bg-hero-glow relative flex min-h-screen items-center justify-center px-4">
      <div className="bg-grid absolute inset-0" />
      <div className="relative w-full max-w-md">
        <div className="mb-8 text-center">
          <div className="flex justify-center">
            <Logo size="lg" />
          </div>
          <p className="mt-3 text-sm text-fortexa-muted">Welcome back — sign in to your forensic workstation.</p>
        </div>

        <div className="glass card !p-8 animate-slide-up">
          <form onSubmit={handleSubmit} className="space-y-5">
            <div>
              <label className="mb-1.5 block text-sm font-medium text-fortexa-muted">Email address</label>
              <div className="relative">
                <Mail size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-fortexa-muted" />
                <input
                  type="email"
                  className="input-base !pl-10"
                  placeholder="you@example.com"
                  value={form.email}
                  onChange={(e) => setForm({ ...form, email: e.target.value })}
                  autoComplete="email"
                />
              </div>
            </div>

            <div>
              <label className="mb-1.5 block text-sm font-medium text-fortexa-muted">Password</label>
              <div className="relative">
                <Lock size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-fortexa-muted" />
                <input
                  type={showPass ? 'text' : 'password'}
                  className="input-base !pl-10 !pr-10"
                  placeholder="••••••••"
                  value={form.password}
                  onChange={(e) => setForm({ ...form, password: e.target.value })}
                  autoComplete="current-password"
                />
                <button
                  type="button"
                  onClick={() => setShowPass((v) => !v)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-fortexa-muted hover:text-white"
                >
                  {showPass ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </div>

            {error && (
              <div className="rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-2.5 text-sm text-red-400">
                {error}
              </div>
            )}

            <button type="submit" disabled={loading} className="btn-primary w-full !py-3">
              {loading ? <Spinner size={18} /> : <LogIn size={18} />}
              {loading ? 'Signing in…' : 'Sign In'}
            </button>
          </form>

          <div className="mt-6 flex items-center justify-between text-sm">
            <Link to="/" className="inline-flex items-center gap-1.5 text-fortexa-muted hover:text-white">
              <ArrowLeft size={14} /> Back home
            </Link>
            <span className="text-fortexa-muted">
              New here?{' '}
              <Link to="/register" className="font-medium text-fortexa-primary hover:text-fortexa-secondary">
                Create an account
              </Link>
            </span>
          </div>
        </div>
      </div>
    </div>
  )
}