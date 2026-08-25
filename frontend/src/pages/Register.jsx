import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { User, Mail, Lock, ArrowLeft, Eye, EyeOff } from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import Logo from '../components/layout/Logo'
import Spinner from '../components/ui/Spinner'

export default function Register() {
  const { register, loading } = useAuth()
  const navigate = useNavigate()
  const [form, setForm] = useState({ username: '', full_name: '', email: '', password: '', confirm: '' })
  const [showPass, setShowPass] = useState(false)
  const [error, setError] = useState('')

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    if (!form.username || !form.email || !form.password || !form.confirm) {
      setError('Please fill in all required fields.')
      return
    }
    if (form.password !== form.confirm) {
      setError('Passwords do not match.')
      return
    }
    if (form.password.length < 8) {
      setError('Password must be at least 8 characters.')
      return
    }
    const res = await register({
      username: form.username.trim(),
      full_name: form.full_name.trim(),
      email: form.email.trim(),
      password: form.password,
    })
    if (res.ok) {
      navigate('/app')
    } else {
      setError(res.error || 'Registration failed.')
    }
  }

  const field = (key, label, placeholder, Icon, type = 'text', opts = {}) => (
    <div>
      <label className="mb-1.5 block text-sm font-medium text-fortexa-muted">{label}</label>
      <div className="relative">
        <Icon size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-fortexa-muted" />
        <input
          type={type}
          className={`input-base !pl-10 ${opts.toggle ? '!pr-10' : ''}`}
          placeholder={placeholder}
          value={form[key]}
          onChange={(e) => setForm({ ...form, [key]: e.target.value })}
          autoComplete={opts.autoComplete}
        />
        {opts.toggle && (
          <button
            type="button"
            onClick={() => setShowPass((v) => !v)}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-fortexa-muted hover:text-white"
          >
            {showPass ? <EyeOff size={16} /> : <Eye size={16} />}
          </button>
        )}
      </div>
    </div>
  )

  return (
    <div className="bg-hero-glow relative flex min-h-screen items-center justify-center px-4 py-10">
      <div className="bg-grid absolute inset-0" />
      <div className="relative w-full max-w-md">
        <div className="mb-8 text-center">
          <div className="flex justify-center">
            <Logo size="lg" />
          </div>
          <p className="mt-3 text-sm text-fortexa-muted">Create your account and start verifying media.</p>
        </div>

        <div className="glass card !p-8 animate-slide-up">
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              {field('username', 'Username *', 'johndoe', User, 'text', { autoComplete: 'username' })}
              {field('full_name', 'Full name', 'John Doe', User, 'text', { autoComplete: 'name' })}
            </div>
            {field('email', 'Email address *', 'you@example.com', Mail, 'email', { autoComplete: 'email' })}
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              {field('password', 'Password *', '••••••••', Lock, showPass ? 'text' : 'password', { autoComplete: 'new-password', toggle: true })}
              {field('confirm', 'Confirm password *', '••••••••', Lock, showPass ? 'text' : 'password', { autoComplete: 'new-password' })}
            </div>

            {error && (
              <div className="rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-2.5 text-sm text-red-400">
                {error}
              </div>
            )}

            <button type="submit" disabled={loading} className="btn-primary w-full !py-3">
              {loading ? <Spinner size={18} /> : null}
              {loading ? 'Creating account…' : 'Create Account'}
            </button>
          </form>

          <div className="mt-6 flex items-center justify-between text-sm">
            <Link to="/" className="inline-flex items-center gap-1.5 text-fortexa-muted hover:text-white">
              <ArrowLeft size={14} /> Back home
            </Link>
            <span className="text-fortexa-muted">
              Have an account?{' '}
              <Link to="/login" className="font-medium text-fortexa-primary hover:text-fortexa-secondary">
                Sign in
              </Link>
            </span>
          </div>
        </div>
      </div>
    </div>
  )
}