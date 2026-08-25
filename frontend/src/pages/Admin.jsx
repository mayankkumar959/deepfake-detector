import { useState, useEffect, useCallback } from 'react'
import { Users, ShieldCheck, Shield, UserX, UserCheck, Database, AlertTriangle } from 'lucide-react'
import api from '../api/client'
import PageHeader from '../components/ui/PageHeader'
import StatCard from '../components/ui/StatCard'
import Spinner from '../components/ui/Spinner'
import { useToast } from '../components/ui/Toast'
import { useAuth } from '../context/AuthContext'

function formatDate(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })
}

export default function Admin() {
  const toast = useToast()
  const { user: currentUser } = useAuth()
  const [users, setUsers] = useState([])
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(true)

  const fetchData = useCallback(async () => {
    try {
      const [u, s] = await Promise.all([
        api.get('/admin/users'),
        api.get('/admin/stats'),
      ])
      setUsers(u.data)
      setStats(s.data)
    } catch {
      toast.error('Failed to load admin data.')
    } finally {
      setLoading(false)
    }
  }, [toast])

  useEffect(() => {
    fetchData()
  }, [fetchData])

  const toggleActive = async (target) => {
    try {
      const { data } = await api.patch(`/admin/users/${target.id}`, { is_active: !target.is_active })
      setUsers((prev) => prev.map((u) => (u.id === data.id ? data : u)))
      toast.success(`${target.username} ${data.is_active ? 'activated' : 'deactivated'}.`)
    } catch {
      toast.error('Failed to update user.')
    }
  }

  const setRole = async (target, role) => {
    try {
      const { data } = await api.patch(`/admin/users/${target.id}`, { role })
      setUsers((prev) => prev.map((u) => (u.id === data.id ? data : u)))
      toast.success(`${target.username} is now ${role}.`)
    } catch {
      toast.error('Failed to update role.')
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24">
        <Spinner size={28} />
      </div>
    )
  }

  return (
    <div>
      <PageHeader title="User Management" description="Admin console — manage platform users and roles." />

      {/* Stats */}
      <div className="mb-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard icon={Users} label="Total Users" value={stats?.total_users ?? 0} color="text-fortexa-primary" />
        <StatCard icon={Database} label="Total Scans" value={stats?.total_scans ?? 0} color="text-sky-400" delay={80} />
        <StatCard icon={ShieldCheck} label="Fake Detected" value={stats?.fake_detected ?? 0} color="text-red-400" delay={160} />
        <StatCard icon={AlertTriangle} label="Failed Scans" value={stats?.failed_scans ?? 0} color="text-amber-400" delay={240} />
      </div>
      {/* Users table */}
      <div className="card !p-0 overflow-hidden">
        <div className="overflow-x-auto scrollbar-thin">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-white/10 text-left text-xs uppercase tracking-wider text-fortexa-muted">
                <th className="px-5 py-3.5 font-medium">User</th>
                <th className="px-5 py-3.5 font-medium">Role</th>
                <th className="px-5 py-3.5 font-medium">Status</th>
                <th className="px-5 py-3.5 font-medium">Joined</th>
                <th className="px-5 py-3.5 font-medium text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => {
                const isSelf = u.id === currentUser?.id
                return (
                  <tr key={u.id} className="border-b border-white/5 hover:bg-white/5">
                    <td className="px-5 py-3.5">
                      <div className="flex items-center gap-3">
                        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-fortexa-primary to-fortexa-secondary text-xs font-bold">
                          {(u.full_name || u.username || 'U').charAt(0).toUpperCase()}
                        </div>
                        <div className="min-w-0">
                          <p className="font-medium truncate">{u.full_name || u.username}</p>
                          <p className="text-xs text-fortexa-muted truncate">@{u.username} · {u.email}</p>
                        </div>
                      </div>
                    </td>
                    <td className="px-5 py-3.5">
                      <select
                        value={u.role}
                        disabled={isSelf}
                        onChange={(e) => setRole(u, e.target.value)}
                        className={`input-base !w-28 !py-1.5 !text-xs ${isSelf ? 'opacity-50 cursor-not-allowed' : ''}`}
                      >
                        <option value="user">User</option>
                        <option value="admin">Admin</option>
                      </select>
                    </td>
                    <td className="px-5 py-3.5">
                      <span className={`badge ${u.is_active ? 'bg-emerald-500/15 text-emerald-400' : 'bg-red-500/15 text-red-400'}`}>
                        {u.is_active ? 'Active' : 'Inactive'}
                      </span>
                    </td>
                    <td className="px-5 py-3.5 text-fortexa-muted whitespace-nowrap">{formatDate(u.created_at)}</td>
                    <td className="px-5 py-3.5">
                      <div className="flex justify-end">
                        <button
                          disabled={isSelf}
                          onClick={() => toggleActive(u)}
                          className={`inline-flex items-center gap-1.5 rounded-lg border border-white/10 bg-white/5 px-2.5 py-1.5 text-xs transition-all ${
                            isSelf ? 'opacity-40 cursor-not-allowed' : 'hover:bg-white/10'
                          }`}
                          title={u.is_active ? 'Deactivate' : 'Activate'}
                        >
                          {u.is_active ? <UserX size={13} /> : <UserCheck size={13} />}
                          {u.is_active ? 'Deactivate' : 'Activate'}
                        </button>
                      </div>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
