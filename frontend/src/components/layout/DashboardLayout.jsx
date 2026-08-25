import { useState } from 'react'
import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import {
  LayoutDashboard, ScanSearch, History, Settings, Users, LogOut, Menu, X,
  ShieldCheck, FileVideo, FileImage,
} from 'lucide-react'
import { useAuth } from '../../context/AuthContext'
import Logo from './Logo'

const navItems = [
  { to: '/app', label: 'Dashboard', icon: LayoutDashboard, end: true },
  { to: '/app/scan', label: 'Analyze Media', icon: ScanSearch },
  { to: '/app/history', label: 'Scan History', icon: History },
  { to: '/app/settings', label: 'Settings', icon: Settings },
]

export default function DashboardLayout() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const [sidebarOpen, setSidebarOpen] = useState(false)

  const handleLogout = () => {
    logout()
    navigate('/')
  }

  const Sidebar = (
    <div className="flex h-full flex-col">
      <div className="px-5 py-6">
        <Logo />
      </div>
      <nav className="flex-1 space-y-1 px-3">
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.end}
            onClick={() => setSidebarOpen(false)}
            className={({ isActive }) =>
              `flex items-center gap-3 rounded-xl px-4 py-2.5 text-sm font-medium transition-all ${
                isActive
                  ? 'bg-gradient-to-r from-fortexa-primary/20 to-fortexa-secondary/10 text-white border border-fortexa-primary/30'
                  : 'text-fortexa-muted hover:text-white hover:bg-white/5 border border-transparent'
              }`
            }
          >
            <item.icon size={18} />
            {item.label}
          </NavLink>
        ))}
        {user?.role === 'admin' && (
          <NavLink
            to="/app/admin"
            onClick={() => setSidebarOpen(false)}
            className={({ isActive }) =>
              `flex items-center gap-3 rounded-xl px-4 py-2.5 text-sm font-medium transition-all ${
                isActive
                  ? 'bg-gradient-to-r from-fortexa-primary/20 to-fortexa-secondary/10 text-white border border-fortexa-primary/30'
                  : 'text-fortexa-muted hover:text-white hover:bg-white/5 border border-transparent'
              }`
            }
          >
            <Users size={18} />
            User Management
          </NavLink>
        )}
      </nav>
      <div className="border-t border-white/10 p-4">
        <div className="flex items-center gap-3 rounded-xl bg-white/5 p-3">
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-fortexa-primary to-fortexa-secondary text-sm font-bold">
            {(user?.full_name || user?.username || 'U').charAt(0).toUpperCase()}
          </div>
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-medium">{user?.full_name || user?.username}</p>
            <p className="truncate text-xs text-fortexa-muted">{user?.email}</p>
          </div>
          <button onClick={handleLogout} className="text-fortexa-muted hover:text-red-400" title="Log out">
            <LogOut size={16} />
          </button>
        </div>
      </div>
    </div>
  )

  return (
    <div className="flex min-h-screen bg-fortexa-bg">
      {/* Desktop sidebar */}
      <aside className="fixed inset-y-0 left-0 z-40 hidden w-64 border-r border-white/10 bg-fortexa-card/50 backdrop-blur-xl lg:block">
        {Sidebar}
      </aside>

      {/* Mobile sidebar */}
      {sidebarOpen && (
        <div className="fixed inset-0 z-50 lg:hidden">
          <div className="absolute inset-0 bg-black/70" onClick={() => setSidebarOpen(false)} />
          <aside className="absolute inset-y-0 left-0 w-64 border-r border-white/10 bg-fortexa-card">
            <button onClick={() => setSidebarOpen(false)} className="absolute right-3 top-4 text-fortexa-muted">
              <X size={20} />
            </button>
            {Sidebar}
          </aside>
        </div>
      )}

      <div className="flex-1 lg:pl-64">
        {/* Top bar */}
        <header className="sticky top-0 z-30 flex items-center justify-between border-b border-white/10 bg-fortexa-bg/80 px-4 py-3 backdrop-blur-xl lg:px-8">
          <div className="flex items-center gap-3">
            <button onClick={() => setSidebarOpen(true)} className="text-fortexa-muted lg:hidden">
              <Menu size={22} />
            </button>
            <div className="flex items-center gap-2 text-sm text-fortexa-muted">
              <ShieldCheck size={16} className="text-fortexa-success" />
              <span>Detection Engine Online</span>
            </div>
          </div>
          <div className="flex items-center gap-4">
            <span className="hidden items-center gap-2 rounded-lg bg-white/5 border border-white/10 px-3 py-1.5 text-xs text-fortexa-muted sm:flex">
              <FileImage size={14} /> Photo
              <span className="mx-1 text-white/20">|</span>
              <FileVideo size={14} /> Video
            </span>
            <div className="flex items-center gap-2">
              <span className="hidden text-sm font-medium sm:block">{user?.username}</span>
              <div className="flex h-8 w-8 items-center justify-center rounded-full bg-gradient-to-br from-fortexa-primary to-fortexa-secondary text-xs font-bold">
                {(user?.full_name || user?.username || 'U').charAt(0).toUpperCase()}
              </div>
            </div>
          </div>
        </header>

        <main className="p-4 lg:p-8">
          <Outlet />
        </main>
      </div>
    </div>
  )
}