import { useState } from 'react'
import { User as UserIcon, KeyRound, Save, ShieldCheck } from 'lucide-react'
import api from '../api/client'
import { useAuth } from '../context/AuthContext'
import PageHeader from '../components/ui/PageHeader'
import Spinner from '../components/ui/Spinner'
import { useToast } from '../components/ui/Toast'

export default function Settings() {
  const { user, updateUser } = useAuth()
  const toast = useToast()
  const [profile, setProfile] = useState({
    username: user?.username || '',
    full_name: user?.full_name || '',
  })
  const [password, setPassword] = useState({ current_password: '', new_password: '', confirm: '' })
  const [savingProfile, setSavingProfile] = useState(false)
  const [savingPassword, setSavingPassword] = useState(false)

  const saveProfile = async (e) => {
    e.preventDefault()
    setSavingProfile(true)
    try {
      const { data } = await api.put('/auth/me', {
        username: profile.username.trim(),
        full_name: profile.full_name.trim(),
      })
      updateUser(data)
      toast.success('Profile updated.')
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to update profile.')
    } finally {
      setSavingProfile(false)
    }
  }

  const changePassword = async (e) => {
    e.preventDefault()
    if (password.new_password !== password.confirm) {
      toast.error('Passwords do not match.')
      return
    }
    if (password.new_password.length < 6) {
      toast.error('New password must be at least 6 characters.')
      return
    }
    setSavingPassword(true)
    try {
      await api.post('/auth/change-password', {
        current_password: password.current_password,
        new_password: password.new_password,
      })
      toast.success('Password changed successfully.')
      setPassword({ current_password: '', new_password: '', confirm: '' })
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to change password.')
    } finally {
      setSavingPassword(false)
    }
  }

return (
    <div>
      <PageHeader title="Settings" description="Manage your profile and account security." />

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Profile */}
        <div className="card">
          <div className="mb-5 flex items-center gap-3">
            <div className="rounded-xl bg-fortexa-primary/15 border border-fortexa-primary/20 p-2.5 text-fortexa-primary">
              <UserIcon size={18} />
            </div>
            <div>
              <h3 className="text-lg font-semibold">Profile Information</h3>
              <p className="text-xs text-fortexa-muted">Update your display name and username.</p>
            </div>
          </div>

          <form onSubmit={saveProfile} className="space-y-4">
            <div>
              <label className="mb-1.5 block text-sm font-medium text-fortexa-muted">Full name</label>
              <input
                className={input}
                value={profile.full_name}
                onChange={(e) => setProfile({ ...profile, full_name: e.target.value })}
                placeholder="John Doe"
              />
            </div>
            <div>
              <label className="mb-1.5 block text-sm font-medium text-fortexa-muted">Username</label>
              <input
                className={input}
                value={profile.username}
                onChange={(e) => setProfile({ ...profile, username: e.target.value })}
              />
            </div>
            <div>
              <label className="mb-1.5 block text-sm font-medium text-fortexa-muted">Email</label>
              <input className={`${input} opacity-60 cursor-not-allowed`} value={user?.email} readOnly disabled />
              <p className="mt-1 text-xs text-fortexa-muted">Email cannot be changed.</p>
            </div>
            <button type="submit" disabled={savingProfile} className="btn-primary">
              {savingProfile ? <Spinner size={16} /> : <Save size={16} />}
              {savingProfile ? 'Saving…' : 'Save Profile'}
            </button>
          </form>
        </div>
        {/* Security */}
        <div className="card">
          <div className="mb-5 flex items-center gap-3">
            <div className="rounded-xl bg-fortexa-secondary/15 border border-fortexa-secondary/20 p-2.5 text-fortexa-secondary">
              <KeyRound size={18} />
            </div>
            <div>
              <h3 className="text-lg font-semibold">Change Password</h3>
              <p className="text-xs text-fortexa-muted">Use at least 6 characters for your new password.</p>
            </div>
          </div>

          <form onSubmit={changePassword} className="space-y-4">
            <div>
              <label className="mb-1.5 block text-sm font-medium text-fortexa-muted">Current password</label>
              <input
                type="password"
                className={input}
                value={password.current_password}
                onChange={(e) => setPassword({ ...password, current_password: e.target.value })}
                autoComplete="current-password"
              />
            </div>
            <div>
              <label className="mb-1.5 block text-sm font-medium text-fortexa-muted">New password</label>
              <input
                type="password"
                className={input}
                value={password.new_password}
                onChange={(e) => setPassword({ ...password, new_password: e.target.value })}
                autoComplete="new-password"
              />
            </div>
            <div>
              <label className="mb-1.5 block text-sm font-medium text-fortexa-muted">Confirm new password</label>
              <input
                type="password"
                className={input}
                value={password.confirm}
                onChange={(e) => setPassword({ ...password, confirm: e.target.value })}
                autoComplete="new-password"
              />
            </div>
            <button type="submit" disabled={savingPassword} className="btn-primary">
              {savingPassword ? <Spinner size={16} /> : <KeyRound size={16} />}
              {savingPassword ? 'Updating…' : 'Update Password'}
            </button>
          </form>

          <div className="mt-6 rounded-xl border border-white/10 bg-white/5 p-4">
            <div className="flex items-center gap-2 text-sm">
              <ShieldCheck size={16} className="text-fortexa-success" />
              <span className="font-medium">Account role: <span className="capitalize">{user?.role}</span></span>
            </div>
            <p className="mt-1 text-xs text-fortexa-muted">
              Passwords are hashed with PBKDF2-SHA256 (600,000 iterations) and never stored in plain text.
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
  const input = 'input-base'
